"""The count (PL2 of the places review, 1 Nov 2026): every Arabic text of the Bulletin's general edition and of
its conventions edition, its title and each of its articles, read once for every place of data/places.json.

A text is read in its words as published when the site holds them (its as_published Arabic version), else in its newest
Arabic version (`printed` false: the posts leave those out, the finder lists them). A text counts in the year of the
issue that first published it. Reports the Bulletin prints («تقرير …») are left out, as the words post leaves them.

Written as Mention rows (a place's first time in an article or a title), PlaceYear and Year rows (texts as printed, the
shares' denominators, PL4), and each place's number of texts, first mention and spellings. The rows are computed into a
file first and swapped in one transaction: readers keep the old rows until it commits. `manage.py build_places`, $0."""
import csv
import json
import re
from datetime import date
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from django.db import connection, transaction

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.places.models import Mention, Place, PlaceYear, Year
from apps.places.services.names import Matcher, kind_of
from apps.sources.models import Edition

DATA = Path(__file__).resolve().parent.parent / 'data' / 'places.json'
EDITIONS = (Edition.GENERAL_AR, Edition.CONVENTIONS_AR)
FOREIGN = ('country', 'gone')
COLUMNS = ('place_id', 'uri', 'eid', 'order', 'date', 'issue', 'edition', 'page', 'text_type', 'kind', 'form', 'at', 'printed', 'old')


def gazetteer() -> list[dict]:
    return json.loads(DATA.read_text(encoding='utf-8'))


def sync(rows: list[dict]) -> dict[str, Place]:
    """Place rows as places.json lists them: kept by slug, the others removed."""
    have = {p.slug: p for p in Place.objects.all()}
    fields = dict(kind='kind', name_ar='ar', name_fr='fr', name_en='en', code='code', region='region', parent='parent',
                  town='town', successor='successor', lat='lat', lon='lon', population='pop', foreigners='foreign',
                  forms='forms', old='old', latin='latin')
    new, changed = [], []
    for r in rows:
        values = {f: (r.get(k) if r.get(k) is not None else ('' if f not in ('lat', 'lon', 'population', 'foreigners') else None))
                  for f, k in fields.items()}
        values['old'] = values['old'] or []
        place = have.get(r['slug'])
        if place is None:
            new.append(Place(slug=r['slug'], **values))
        else:
            for f, v in values.items():
                setattr(place, f, v)
            changed.append(place)
    Place.objects.filter(slug__in=set(have) - {r['slug'] for r in rows}).delete()
    Place.objects.bulk_create(new, batch_size=1000)
    Place.objects.bulk_update(changed, list(fields), batch_size=500)
    return {p.slug: p for p in Place.objects.all()}


def _key(number, suffix) -> str:
    return f'{number}-{suffix}' if suffix else str(number)


_MARKS = re.compile('[\u0610-\u061A\u064B-\u065F\u0670\u0640]')


def _spelling(printed: str, clitic: str) -> str:
    """The name as printed, its clinging letter, harakat and elongations off («فرنســا» is «فرنسا»)."""
    printed = _MARKS.sub('', ' '.join(printed.split()))
    if not clitic:
        return printed
    if clitic == 'ل' and printed.startswith('لل'):
        return 'ال' + printed[2:]
    return printed[len(clitic):] if len(printed) > len(clitic) else printed


def build(log=print) -> dict:
    rows = gazetteer()
    matcher = Matcher(rows)
    family = {r['slug']: r['kind'] for r in rows}
    # A place counted from a day (curated.yaml `since`): before it, the name is another place's.
    since = {r['slug']: date.fromisoformat(r['since']) for r in rows if r.get('since')}
    places = sync(rows)

    texts = {}
    for tid, uri, ttype, title, day, number, suffix, edition, page in (
            Text.objects.filter(first_published_in__edition__in=EDITIONS)
            .exclude(title_ar__startswith='تقرير').exclude(title_ar__startswith='التقرير')
            .values_list('pk', 'akn_uri', 'type', 'title_ar', 'first_published_in__date', 'first_published_in__number',
                         'first_published_in__suffix', 'first_published_in__edition', 'first_published_page')):
        texts[tid] = (uri, ttype, title or '', day, _key(number, suffix), edition, page)
    # One version a text: as published when held (the earliest), else the newest.
    candidates = defaultdict(list)
    for vid, tid, consolidation, valid_from in (Version.objects.filter(text_id__in=texts.keys(), language='ar')
                                                .values_list('pk', 'text_id', 'consolidation', 'valid_from')):
        candidates[tid].append((consolidation == Consolidation.AS_PUBLISHED, valid_from or texts[tid][3], vid))
    best = {}
    for tid, vs in candidates.items():
        printed = [v for v in vs if v[0]]
        best[tid] = (min(printed)[2], True) if printed else (max(vs)[2], False)
    chosen = {v[0]: (tid, v[1]) for tid, v in best.items()}
    log(f'{len(texts)} texts, {len(chosen)} read ({sum(1 for v in chosen.values() if v[1])} as published)')

    named = defaultdict(set)              # text → places, any version
    printed_names = defaultdict(set)      # text → places, as printed
    first, spellings, forms_years = {}, defaultdict(Counter), defaultdict(dict)
    kinds_of = {}
    out = tempfile.NamedTemporaryFile('w', suffix='.tsv', delete=False, encoding='utf-8', newline='')
    writer = csv.writer(out, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
    written = 0

    def kinds(tid):
        if tid not in kinds_of:
            kinds_of[tid] = (kind_of(texts[tid][2], True), kind_of(texts[tid][2], False))
        return kinds_of[tid]

    def note(tid, printed, eid, order, body, found_all):
        nonlocal written
        uri, ttype, title, day, issue, edition, page = texts[tid]
        seen = set()
        for f in found_all:
            if f.slug in seen or (f.slug in since and day < since[f.slug]):
                continue
            seen.add(f.slug)
            pl = places[f.slug]
            foreign = family[f.slug] in FOREIGN
            printed_form = body[f.start:f.end]
            writer.writerow([pl.pk, uri, eid, order, day.isoformat(), issue, edition, page if page is not None else r'\N',
                             ttype, kinds(tid)[0 if foreign else 1], printed_form[:120].replace('\t', ' ').replace('\n', ' '),
                             f.start, 't' if printed else 'f', 't' if f.old else 'f'])
            written += 1
            named[tid].add(f.slug)
            if printed:
                printed_names[tid].add(f.slug)
                spelling = _spelling(printed_form, f.clitic)
                spellings[f.slug][spelling] += 1
                years = forms_years[f.slug].setdefault(spelling, [day.year, day.year])
                years[0], years[1] = min(years[0], day.year), max(years[1], day.year)
                mine = first.get(f.slug)
                if mine is None or (day.isoformat(), issue, page or 0, order) < (mine['date'], mine['issue'], mine['page'] or 0, mine['order']):
                    first[f.slug] = {'date': day.isoformat(), 'uri': uri, 'eid': eid, 'order': order, 'issue': issue,
                                     'edition': edition, 'page': page, 'form': printed_form[:120], 'at': f.start, 'title': title[:300]}

    for _vid, (tid, printed) in chosen.items():
        note(tid, printed, '', -1, texts[tid][2], matcher.find(texts[tid][2], title=True))
    articles = (Article.objects.filter(version_id__in=Version.objects.filter(language='ar', text__first_published_in__edition__in=EDITIONS))
                .order_by().values_list('version_id', 'eid', 'order', 'body').iterator(chunk_size=5000))
    read = 0
    for vid, eid, order, body in articles:
        mine = chosen.get(vid)
        if mine is None or not body:
            continue
        read += 1
        note(mine[0], mine[1], eid or '', order, body, matcher.find(body))
        if read % 100000 == 0:
            log(f'{read} articles')
    out.close()

    per_year = defaultdict(lambda: defaultdict(Counter))      # place → year → kind → texts
    totals, foreign = Counter(), Counter()
    for tid, (vid_printed) in ((t, b[1]) for t, b in best.items()):
        if not vid_printed:
            continue
        year = texts[tid][3].year
        totals[year] += 1
        names = printed_names.get(tid, ())
        if any(family[s] in FOREIGN for s in names):
            foreign[year] += 1
        for s in names:
            per_year[s][year][kinds(tid)[0 if family[s] in FOREIGN else 1]] += 1
    counted = Counter(s for names in named.values() for s in names)

    with transaction.atomic():
        Mention.objects.all().delete()
        PlaceYear.objects.all().delete()
        Year.objects.all().delete()
        with connection.cursor() as c, open(out.name, encoding='utf-8') as f:
            cols = ', '.join(f'"{x}"' for x in COLUMNS)
            # The writer doubles every backslash, as COPY reads them, and so the NULL marker's: «\\N», matched as written.
            with c.cursor.copy(f"COPY places_mention ({cols}) FROM STDIN WITH (FORMAT text, NULL '\\\\N')") as copy:
                while chunk := f.read(1 << 20):
                    copy.write(chunk)
        PlaceYear.objects.bulk_create([PlaceYear(place=places[s], year=y, texts=sum(k.values()), kinds=dict(k))
                                       for s, ys in per_year.items() for y, k in ys.items()], batch_size=5000)
        Year.objects.bulk_create([Year(year=y, texts=n, foreign=foreign[y]) for y, n in sorted(totals.items())])
        for s, p in places.items():
            p.texts = counted.get(s, 0)
            p.first = first.get(s)
            p.spellings = [{'form': form, 'n': n, 'from': forms_years[s][form][0], 'to': forms_years[s][form][1]}
                           for form, n in spellings[s].most_common(8)]
        Place.objects.bulk_update(places.values(), ['texts', 'first', 'spellings'], batch_size=500)
    Path(out.name).unlink()
    return {'texts': len(chosen), 'articles': read, 'mentions': written, 'places': sum(1 for n in counted.values() if n),
            'years': len(totals)}
