"""«المغرب في الجريدة الرسمية» (post 2 of the places review, 1 Nov 2026): the Moroccan cities the Bulletin names
since No. 1 (1913), read from what `build_places` counted (apps/places). A city counts with its province or prefecture of the
same name (C5: «إقليم تازة» and «تازة» are one place to a reader; the finder keeps them apart), each text once. Period
by period as a share of the period's texts (PL4); the five biggest against all the others (PL14); who rose and who fell;
the old names beside the new (PL15); since 2020, texts per 10,000 inhabitants by the 2024 census decree, a city with its
province by the province's (PL16); what
the State's texts did in each city, by the words of their titles (PL17); the titles that say they are the French zone's. Five queries; the arithmetic apart."""
from functools import reduce
from operator import or_

from django.db.models import Count, Q

from apps.corpus.models import Text
from apps.places.models import Mention, Place, Year
from apps.places.services.names import fold
from apps.sources.models import Edition

ZONE = ('المنطقة الفرنسوية', 'المنطقة الفرنساوية', 'المنطقة الفرنسية')
FIELDS = ('pk', 'slug', 'kind', 'name_ar', 'name_fr', 'lat', 'lon', 'population', 'town', 'parent', 'texts', 'first', 'spellings', 'old')


def count(meta: dict) -> dict:
    cities = list(Place.objects.filter(kind='city').values(*FIELDS))
    provinces = list(Place.objects.filter(kind='province').exclude(town='').values('pk', 'town', 'population'))
    ids = [c['pk'] for c in cities] + [p['pk'] for p in provinces]
    rows = list(Mention.objects.filter(place_id__in=ids, printed=True).values_list('place_id', 'uri', 'date__year', 'kind', 'old')
                .distinct())
    totals = list(Year.objects.values_list('year', 'texts', 'foreign'))
    out = tabulate(meta, cities, provinces, rows, totals)
    # An old name as the Bulletin printed it most often (the list holds it folded): «فضالة», not «فضاله»; a clinging و ب ل
    # dropped only when what is left is the old name («بفضالة» → «فضالة»), never its own first letter («بتي جان», Petitjean).
    printed, olds = {}, {c['slug']: set(c['old'] or ()) for c in cities}
    for slug, form, _n in (Mention.objects.filter(old=True, printed=True).values_list('place__slug', 'form').annotate(n=Count('pk'))
                          .order_by('-n')):
        clings = form[:1] in 'وبل' and fold(form[1:]) in olds.get(slug, ()) and fold(form) not in olds.get(slug, ())
        printed.setdefault(slug, form[1:] if clings else form)
    for c in out['cities']:
        if c['old'] and c['slug'] in printed:
            c['old']['forms'] = [printed[c['slug']], *c['old']['forms']]
    # The Bulletin before 1956 in its own words (BH12 of the posts-from-No.-1 review): the titles that say their text is the
    # French zone's, «بالمنطقة الفرنسوية من الايالة الشريفة».
    out['totals']['zone'] = (Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR, first_published_in__date__year__lt=1956)
                             .filter(reduce(or_, (Q(title_ar__contains=z) for z in ZONE))).count())
    return out


def tabulate(meta: dict, cities: list[dict], provinces: list[dict], rows: list[tuple], totals: list[tuple]) -> dict:
    periods = [tuple(p) for p in meta['periods']]
    at = lambda y: next((i for i, (a, b) in enumerate(periods) if a <= y <= b), None)
    texts = [0] * len(periods)
    for y, n, _ in totals:
        i = at(y)
        if i is not None:
            texts[i] += n
    per = lambda v, i: round(1000 * v / texts[i], 2) if texts[i] else 0
    city_of = {c['pk']: c['slug'] for c in cities}
    city_of.update({p['pk']: p['town'] for p in provinces})
    # A city counted with its province is weighed by the province's people (PL16): its texts are the province's too.
    people = {c['slug']: c['population'] for c in cities}
    people.update({p['town']: p['population'] for p in provinces if p.get('population')})
    named, kinds, old = {}, {}, {}
    for pid, uri, year, kind, is_old in rows:
        slug, i = city_of.get(pid), at(year)
        if slug is None or i is None:
            continue
        named.setdefault(slug, {})[uri] = i
        kinds.setdefault(slug, {})[uri] = kind
        if is_old:
            old.setdefault(slug, {})[uri] = i
    out = []
    for c in cities:
        mine = named.get(c['slug'])
        if not mine:
            continue
        counts = [0] * len(periods)
        for i in mine.values():
            counts[i] += 1
        k = {}
        for kind in kinds[c['slug']].values():
            k[kind] = k.get(kind, 0) + 1
        olds = [0] * len(periods)
        for i in old.get(c['slug'], {}).values():
            olds[i] += 1
        f = c['first'] or {}
        out.append({'slug': c['slug'], 'ar': c['name_ar'], 'fr': c['name_fr'], 'lat': c['lat'], 'lon': c['lon'], 'pop': people.get(c['slug']),
                    'n': len(mine), 'c': counts, 's': [per(v, i) for i, v in enumerate(counts)],
                    'kinds': dict(sorted(k.items(), key=lambda kv: -kv[1])),
                    'old': {'forms': c['old'], 'c': olds} if c['old'] and sum(olds) else None,
                    'first': {'year': int(f['date'][:4]), 'date': f['date'], 'issue': f['issue'], 'page': f['page'], 'form': f['form']} if f else None})
    out.sort(key=lambda x: -x['n'])
    floor, most = meta['moves']['floor'], meta['moves']['most']
    big = [x for x in out if x['n'] >= floor]
    edge = lambda x: (sum(x['s'][-2:]) - sum(x['s'][:2])) / 2
    top = {x['slug'] for x in out[:5]}
    five, rest = [0] * len(periods), [0] * len(periods)
    for i in range(len(periods)):
        five[i] = len({u for s in top for u, j in named[s].items() if j == i})
        rest[i] = len({u for s, m in named.items() if s not in top for u, j in m.items() if j == i})
    recent = len(periods) - 1
    per_people = sorted(({'slug': x['slug'], 'v': round(10000 * x['c'][recent] / x['pop'], 2)} for x in out
                         if x['pop'] and x['pop'] >= meta['people_floor'] and x['c'][recent]), key=lambda r: -r['v'])
    return {
        'periods': [list(p) for p in periods], 'texts': texts, 'cities': out,
        'moves': {'rose': [x['slug'] for x in sorted(big, key=edge, reverse=True)[:most] if edge(x) > 0],
                  'fell': [x['slug'] for x in sorted(big, key=edge)[:most] if edge(x) < 0]},
        'five': {'slugs': [x['slug'] for x in out[:5]], 'top': [per(v, i) for i, v in enumerate(five)],
                 'rest': [per(v, i) for i, v in enumerate(rest)]},
        'people': per_people[:12], 'people_low': per_people[-5:],
        'totals': {'cities': len(out), 'texts': sum(texts)},
    }
