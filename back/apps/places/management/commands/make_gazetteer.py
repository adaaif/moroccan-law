"""The places' list (PL1 of the places review, 1 Nov 2026): every state, gone state, Moroccan region, province,
city and commune, with the names a reader types and the spellings the Bulletin prints, written to
apps/places/data/places.json from what is kept:

- the UN's M49 page (CORPUS_DIR/sources/places/m49_overview.html): each state's Arabic, French and English name;
- Natural Earth 5.1 in its Morocco edition (…/naturalearth_ne_10m_admin_0_countries_mar.geojson): where a state's
  name sits on the map;
- census decree 2.24.1009 (BO 7356, 28 Nov 2024) as its pages were read: the 12 regions, 75 prefectures and provinces
  and their communes, in Arabic and French, with code, population and foreigners;
- GeoNames (geonames_MA.zip, geonames_EH.zip, CC BY 4.0): where a Moroccan place is;
- apps/places/data/curated.yaml: what a person adds (the Bulletin's spellings, the words that need a place word,
  old names, slugs).

Run it when one of them changes; `build_places` then reads places.json. $0, no network."""
import csv
import html
import io
import json
import re
import unicodedata
import zipfile
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.places.services.names import fold

DATA = Path(__file__).resolve().parents[2] / 'data'
CENSUS = '/akn/ma/act/decret/2-24-1009'
CODE = re.compile(r'^\d{2}\.\d{3}(?:\.\d{2}(?:\.\d{1,2}(?:\.\d)?)?)?$')
REGION_CODE = re.compile(r'^\d{2}$')
NUM = re.compile(r'^[\d,]+$')
AR = re.compile(r'[؀-ۿ]')
# A state's short name that is also a word: never a form of its own («دولة قطر» stays, «قطر» does not).
NEVER = {'قطر', 'عمان', 'مالي', 'بنين', 'البنين', 'سيلان', 'موريس', 'الجماهيرية'}
PREFIXES = ('جمهورية ', 'مملكة ', 'دولة ', 'سلطنة ', 'امارة ', 'دوقية ')


def slugify(text: str) -> str:
    t = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', t.replace("'", '')).strip('-')


def latin(text: str) -> str:
    return ' '.join(slugify(text).split('-'))


def m49(path: Path) -> dict:
    """{ISO3: {en, fr, ar, region: [continent, sub-region, intermediate]}} from the page's six tables."""
    page = path.read_text(encoding='utf-8')
    out = {}
    for lang in ('EN', 'FR', 'AR'):
        start = page.index(f'id = "downloadTable{lang}"')
        part = page[start:page.index('</table>', start)]
        for row in re.findall(r'<tr>(.*?)</tr>', part, re.S):
            cells = [html.unescape(re.sub(r'<[^>]+>', '', c)).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)]
            if len(cells) >= 12 and re.fullmatch(r'[A-Z]{3}', cells[11] or ''):
                one = out.setdefault(cells[11], {})
                one[lang.lower()] = cells[8]
                one.setdefault('region', [cells[3], cells[5], cells[7]])
    return out


def label_points(path: Path) -> dict:
    out = {}
    for f in json.loads(path.read_text())['features']:
        p = f['properties']
        for key in (p.get('ADM0_A3'), p.get('ISO_A3'), p.get('ISO_A3_EH')):
            if key and key != '-99':
                out.setdefault(key, (round(p['LABEL_Y'], 3), round(p['LABEL_X'], 3)))
    return out


def census_rows() -> list[dict]:
    """The decree's tables as read on its pages: one row per unit, its code, Arabic and French names, population and
    foreigners. A two-digit number is a code only in the code's column (a province's 96 foreigners once read as one)."""
    from apps.corpus.models import Text
    from apps.sources.models import Page

    issue = Text.objects.select_related('first_published_in').get(akn_uri=CENSUS).first_published_in
    rows = {}
    for text in Page.objects.filter(document_id=issue.document_id).order_by('index').values_list('text', flat=True):
        if 'Code géographique' not in text and 'الرمز الجغرافي' not in text:
            continue
        for line in text.splitlines():
            if not line.startswith('|') or '---' in line:
                continue
            cells = [c.strip().strip('*').strip() for c in line.strip('|').split('|')]
            code = next((c for c in cells if CODE.match(c)), None)
            if not code and cells and (REGION_CODE.match(cells[0]) or REGION_CODE.match(cells[-1])):
                code = cells[0] if REGION_CODE.match(cells[0]) else cells[-1]
            ar = next((c for c in cells if AR.search(c) and not re.search(r'\d', c)), None)
            fr = next((c for c in cells if re.search(r'[A-Za-z]', c) and not AR.search(c)), None)
            if not code or not ar or 'الوسط' in ar or (fr and 'milieu' in fr):
                continue
            nums = [int(c.replace(',', '')) for c in cells if NUM.match(c) and c != code]
            pop = foreign = None
            for i in range(len(nums) - 2):
                if nums[i] + nums[i + 1] == nums[i + 2]:
                    pop, foreign = nums[i + 2], nums[i + 1]
                    break
                if nums[i + 2] + nums[i + 1] == nums[i]:   # a table printed from the other side
                    pop, foreign = nums[i], nums[i + 1]
                    break
            rows.setdefault(code, {'code': code, 'ar': ar, 'fr': fr or '', 'pop': pop, 'foreign': foreign})
    return list(rows.values())


def geonames(*zips: Path) -> tuple[dict, dict]:
    """Populated places by folded Arabic name and by Latin name: [(population, lat, lon)], biggest first."""
    by_ar, by_latin = {}, {}
    for path in zips:
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.endswith('.txt') and 'readme' not in n)
            for r in csv.reader(io.TextIOWrapper(z.open(name), encoding='utf-8'), delimiter='\t'):
                if len(r) < 15 or r[6] != 'P':
                    continue
                spot = (int(r[14] or 0), round(float(r[4]), 4), round(float(r[5]), 4), r[2])
                for alt in r[3].split(','):
                    if AR.search(alt):
                        by_ar.setdefault(fold(alt), []).append(spot)
                for alt in (r[1], r[2]):
                    by_latin.setdefault(latin(alt), []).append(spot)
    for table in (by_ar, by_latin):
        for spots in table.values():
            spots.sort(reverse=True)
    return by_ar, by_latin


class Command(BaseCommand):
    help = 'Write apps/places/data/places.json from the kept sources and curated.yaml ($0).'

    def handle(self, *args, **opts):
        kept = Path(settings.CORPUS_DIR) / 'sources' / 'places'
        cur = yaml.safe_load((DATA / 'curated.yaml').read_text(encoding='utf-8'))
        places = self.countries(cur['countries'], m49(kept / 'm49_overview.html'),
                                label_points(kept / 'naturalearth_ne_10m_admin_0_countries_mar.geojson'))
        places += self.morocco(cur['morocco'], census_rows(), *geonames(kept / 'geonames_MA.zip', kept / 'geonames_EH.zip'))
        slugs = [p['slug'] for p in places]
        doubles = {s for s in slugs if slugs.count(s) > 1}
        if doubles:
            raise SystemExit(f'slugs twice: {sorted(doubles)}')
        (DATA / 'places.json').write_text(json.dumps(places, ensure_ascii=False, indent=0, sort_keys=True))
        kinds = {}
        for p in places:
            kinds[p['kind']] = kinds.get(p['kind'], 0) + 1
        self.stdout.write(f'{len(places)} places: {kinds}; without a position: '
                          f'{sum(1 for p in places if p["kind"] in ("city", "country") and p.get("lat") is None)}')

    def countries(self, cur, names, points) -> list[dict]:
        out, slug_of = [], {}
        for iso, n in sorted({**names, **dict(cur['extra'].items())}.items()):
            if iso in cur['skip']:
                continue
            extra = cur['extra'].get(iso, {})
            en = extra.get('en') or re.sub(r'\s*\(.*?\)', '', n['en'])
            slug = extra.get('slug') or cur['slugs'].get(iso) or slugify(en)
            forms = [n['ar'], *cur['forms'].get(iso, []), *extra.get('forms', [])]
            for f in list(forms):
                for p in PREFIXES:
                    short = fold(f)[len(fold(p)):] if fold(f).startswith(fold(p)) else ''
                    # «الجمهورية الفرنسية» never gives «الفرنسية»: an adjective is a language, a currency, a people.
                    if short and short not in {fold(x) for x in NEVER} and len(short) > 3 and not re.fullmatch(r'ال\S+يه', short):
                        forms.append(short)
            forms = [f for f in dict.fromkeys(fold(f) for f in forms) if f not in {fold(x) for x in NEVER}]
            lat, lon = points.get(iso, (None, None))
            slug_of[iso] = slug
            out.append({'slug': slug, 'kind': 'country', 'code': iso, 'ar': n['ar'], 'fr': n['fr'], 'en': en,
                        'region': '/'.join(x for x in n['region'] if x), 'forms': forms, 'ctx': iso in cur['ctx'],
                        'needs': [fold(f) for f in cur['needs'].get(iso, [])],
                        'latin': sorted({latin(n['fr']), latin(en), *cur['latin'].get(iso, [])}), 'lat': lat, 'lon': lon})
            if iso in cur['since']:
                out[-1]['since'] = str(cur['since'][iso])
        for slug, g in cur['gone'].items():
            lat, lon = points.get(g['successor'], (None, None))
            out.append({'slug': slug, 'kind': 'gone', 'code': '', 'ar': g['ar'], 'fr': g['fr'], 'en': g['en'], 'region': '',
                        'forms': list(dict.fromkeys(fold(f) for f in g['forms'])), 'ctx': False, 'successor': slug_of[g['successor']],
                        'latin': sorted({latin(g['fr']), latin(g['en'])}), 'lat': lat, 'lon': lon})
            if g.get('since'):
                out[-1]['since'] = str(g['since'])
        return out

    def morocco(self, cur, rows, by_ar, by_latin) -> list[dict]:
        fix = {fold(k): v for k, v in cur['fix'].items()}
        ctx = {fold(x) for x in cur['ctx']}
        extra_forms = {fold(k): v for k, v in cur['forms'].items()}
        old = {fold(k): v for k, v in cur['old'].items()}
        lat_words = {fold(k): v for k, v in cur['latin'].items()}
        names = {fold(k): v for k, v in cur['names'].items()}
        hand = {fold(k): v for k, v in cur['positions'].items()}
        since = {fold(k): str(v) for k, v in cur.get('since', {}).items()}
        regions, provinces, communes = {}, {}, []
        for r in rows:
            ar = r['ar']
            for wrong, right in cur['fix'].items():     # a reading slip inside the cell («جماعة خريكة»)
                ar = ar.replace(wrong, right)
            ar = ' '.join(ar.split())
            fr = fix.get(r['fr'].lower(), r['fr'])
            seg = r['code'].split('.')
            if len(seg) == 1 and ar.startswith('جهة'):
                name = ar[3:].strip()
                regions[r['code']] = {'slug': 'region-' + slugify(re.sub(r'^Région (de |d\')?', '', fr)), 'kind': 'region',
                                      'code': r['code'], 'ar': name, 'fr': re.sub(r'^Région (de |d\'|du )?', '', fr), 'pop': r['pop']}
            elif len(seg) == 2 and ar.startswith(('إقليم', 'عمالة')):
                word = 'عمالة' if ar.startswith('عمالة') else 'إقليم'
                name = ar[len(word):].strip()
                bare = re.sub(r'^(Province|Préfecture)( de | d\'| du | des )', '', fr).strip()
                provinces[r['code']] = {'slug': ('prefecture-' if word == 'عمالة' else 'province-') + slugify(bare), 'kind': 'province',
                                        'code': r['code'], 'ar': name, 'fr': bare, 'word': word, 'pop': r['pop'], 'foreign': r['foreign']}
            elif len(seg) == 4 and ar.startswith('جماعة'):
                name = ar[5:].strip()
                bare = re.sub(r'^Commune( de | d\'| du | des )', '', fr).strip() or name
                communes.append({'code': r['code'], 'ar': name, 'fr': bare, 'urban': seg[2] == '01', 'pop': r['pop'],
                                 'foreign': r['foreign']})
        out = []
        for reg in regions.values():
            reg.update(forms=[fold(reg['ar'])], ctx=True, latin=[latin(reg['fr'])])
            out.append(reg)
        city_names = {fold(c['ar']) for c in communes if c['urban']}
        for code, p in provinces.items():
            p['parent'] = regions.get(code[:2], {}).get('slug', '')
            p.update(forms=[fold(p['ar'])], ctx=True, latin=[latin(p['fr'])])
            p['town'] = fold(p['ar']) if fold(p['ar']) in city_names else ''
            out.append(p)
        taken = {p['slug'] for p in out}
        city_slug = {}
        for c in sorted(communes, key=lambda c: (not c['urban'], -(c['pop'] or 0))):
            f = fold(c['ar'])
            spot = (by_ar.get(f) or by_latin.get(latin(c['fr'])) or [(None, None, None, '')])[0]
            if f in hand:
                spot = (None, *hand[f], spot[3])
            if not re.search('[A-Za-z]', c['fr']):
                c['fr'] = names.get(f) or spot[3] or c['fr']   # a row whose French cell was not read
            slug = slugify(c['fr']) or 'commune-' + c['code'].replace('.', '-')
            if slug in taken:
                slug = f'{slug}-{slugify(provinces.get(c["code"][:6], {}).get("fr", c["code"]))}'
            taken.add(slug)
            forms = [f, *(fold(x) for x in extra_forms.get(f, []))]
            # A name that is also a man's name («بن أحمد», «ابن جرير», «مولاي يعقوب»: «محمد بن أحمد») needs a place word.
            needs = [x for x in forms if re.match(r'(ابن|بن|مولاي) ', x)]
            place = {'slug': slug, 'kind': 'city' if c['urban'] else 'commune', 'code': c['code'], 'ar': c['ar'], 'fr': c['fr'], 'needs': needs,
                     'parent': provinces.get(c['code'][:6], {}).get('slug', ''), 'pop': c['pop'], 'foreign': c['foreign'],
                     'forms': list(dict.fromkeys(forms)), 'old': [fold(x) for x in old.get(f, [])],
                     'ctx': (not c['urban']) or f in ctx, 'latin': sorted({latin(c['fr']), *lat_words.get(f, [])}),
                     'lat': spot[1], 'lon': spot[2]}
            if c['urban'] and f in since:
                place['since'] = since[f]
            if c['urban']:
                city_slug.setdefault(f, slug)
            out.append(place)
        for p in out:
            if p['kind'] == 'province' and p.get('town'):
                p['town'] = city_slug.get(p['town'], '')
        for e in cur['extra']:
            out.append({**e, 'code': '', 'forms': [fold(x) for x in e['forms']], 'ctx': bool(set(e['forms']) & set(cur['ctx'])), 'old': [],
                        'latin': [latin(e['fr']), latin(e['en'])], 'parent': ''})
        return out
