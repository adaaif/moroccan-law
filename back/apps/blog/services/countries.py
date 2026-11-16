"""«العالم في الجريدة الرسمية» (post 1 of the places review, 1 Nov 2026): every state the Bulletin names since
No. 1 (1913), read from what `build_places` counted (apps/places): the texts as published that name each state, period by
period, as a share of the period's texts (PL4: the Bulletin printed ten times more texts in the 2010s than in 1956–59),
with and without the orders that list foreign diplomas equal to a Moroccan one (PL5); who rose and who fell (PL8); why
the Bulletin names each state, by the words of each text's title (PL9); the states that are gone (PL10); the year each
state was first named (PL11) and how its name was printed (PL12). Three queries; the arithmetic apart (`tabulate`)."""
from apps.places.models import Mention, Place, PlaceYear, Year
from apps.sources.models import Edition

FIELDS = ('slug', 'kind', 'name_ar', 'name_fr', 'name_en', 'lat', 'lon', 'successor', 'region', 'texts', 'first', 'spellings')


def count(meta: dict) -> dict:
    places = list(Place.objects.filter(kind__in=('country', 'gone')).values(*FIELDS))
    years = list(PlaceYear.objects.filter(place__kind__in=('country', 'gone')).values_list('place__slug', 'year', 'texts', 'kinds'))
    totals = list(Year.objects.values_list('year', 'texts', 'foreign'))
    out = tabulate(meta, places, years, totals)
    # The conventions edition's texts in the count (PL6): said in the post, read or not yet.
    out['totals']['conventions'] = Mention.objects.filter(edition=Edition.CONVENTIONS_AR, printed=True).values('uri').distinct().count()
    return out


def tabulate(meta: dict, places: list[dict], years: list[tuple], totals: list[tuple]) -> dict:
    periods = [tuple(p) for p in meta['periods']]
    at = lambda y: next((i for i, (a, b) in enumerate(periods) if a <= y <= b), None)
    texts, foreign = [0] * len(periods), [0] * len(periods)
    for y, n, f in totals:
        i = at(y)
        if i is not None:
            texts[i] += n
            foreign[i] += f
    per = lambda v, i: round(1000 * v / texts[i], 2) if texts[i] else 0
    counts, studies, kinds, last, opened = {}, {}, {}, {}, {}
    for slug, y, n, k in years:
        i = at(y)
        if i is None:
            continue
        if n:
            opened[slug] = min(opened.get(slug, y), y)
        counts.setdefault(slug, [0] * len(periods))[i] += n
        studies.setdefault(slug, [0] * len(periods))[i] += k.get('studies', 0)
        for kind, m in k.items():
            kinds.setdefault(slug, {}).setdefault(kind, 0)
            kinds[slug][kind] += m
        last[slug] = max(last.get(slug, 0), y)
    states = []
    for p in places:
        c = counts.get(p['slug'])
        if not c or not sum(c):
            continue
        s = studies[p['slug']]
        f = p['first'] or {}
        first = {'year': int(f['date'][:4]), 'date': f['date'], 'issue': f['issue'], 'edition': f['edition'], 'page': f['page'],
                 'form': f['form'], 'title': f['title'][:200]} if f else None
        if first and first['year'] < periods[0][0]:
            # Since the Bulletin is read from 1913 (1 Nov 2026), a state may be named before the post's span: the post
            # counts from its first year, so its first is its first year since then; the year it was first named stays
            # beside, for a post that goes back to 1913.
            first = {'year': opened.get(p['slug']), 'named_before': first['year']}
        states.append({
            'slug': p['slug'], 'gone': p['kind'] == 'gone', 'ar': p['name_ar'], 'fr': p['name_fr'], 'en': p['name_en'],
            'lat': p['lat'], 'lon': p['lon'], 'successor': p['successor'] or None, 'region': p['region'].split('/')[0] if p['region'] else '',
            'n': sum(c), 'c': c, 's': [per(v, i) for i, v in enumerate(c)], 'x': [per(v - s[i], i) for i, v in enumerate(c)],
            'kinds': dict(sorted(kinds[p['slug']].items(), key=lambda kv: -kv[1])),
            'first': first,
            'last': last[p['slug']], 'spellings': [sp['form'] for sp in p['spellings'][:4]],
        })
    states.sort(key=lambda x: -x['n'])
    now = [x for x in states if not x['gone']]
    floor = meta['moves']['floor']

    def moves(field):
        big = [x for x in now if x['n'] >= floor]
        edge = lambda x: (sum(x[field][-2:]) - sum(x[field][:2])) / 2
        return {'rose': [x['slug'] for x in sorted(big, key=edge, reverse=True)[:meta['moves']['most']] if edge(x) > 0],
                'fell': [x['slug'] for x in sorted(big, key=edge)[:meta['moves']['most']] if edge(x) < 0]}

    firsts = {}
    for x in now:
        if x['first'] and x['first']['year']:
            firsts[x['first']['year']] = firsts.get(x['first']['year'], 0) + 1
    climb, run = [], 0
    for y in range(periods[0][0], periods[-1][1] + 1):
        run += firsts.get(y, 0)
        climb.append(run)
    never = sorted((p['name_ar'], p['name_fr']) for p in places if p['kind'] == 'country' and not counts.get(p['slug']))
    all_kinds = {}
    for x in states:
        for k, m in x['kinds'].items():
            all_kinds[k] = all_kinds.get(k, 0) + m
    return {
        'periods': [list(p) for p in periods], 'texts': texts, 'foreign': foreign,
        'baseline': [per(v, i) for i, v in enumerate(foreign)],
        'states': states, 'moves': moves('s'), 'moves_nodip': moves('x'),
        'climb': {'from': periods[0][0], 'counts': climb}, 'never': [{'ar': a, 'fr': f} for a, f in never],
        'kinds': dict(sorted(all_kinds.items(), key=lambda kv: -kv[1])),
        'totals': {'states': len(now), 'gone': len(states) - len(now), 'texts': sum(texts), 'foreign': sum(foreign),
                   'never': len(never), 'studies': all_kinds.get('studies', 0)},
    }
