"""The Grand Vizier's signature, for «محمد المقري» (the blog's twenty-fifth post, S20 of the first-principles review, 7
Nov 2026). Every text whose closing in its Arabic version as published carries the name (meta.yaml's `name_re`): by the
year the Bulletin printed it and by kind (an order he signed, a dahir registered under his name); for each year, the
Resident General named in the same closings (the most named one); the first and the last text. One query; the clipping
and the titles are tied to their pages with `clock.tie`."""
import re
from collections import Counter, defaultdict

from apps.blog.services import clock
from apps.corpus.models import Consolidation, TextType, Version
from apps.corpus.services.addresses import text_path
from apps.sources.models import Edition


def count(meta: dict) -> dict:
    residents = [(r['key'], re.compile(r['re'])) for r in meta['residents']]
    rows = (Version.objects.filter(language='ar', consolidation=Consolidation.AS_PUBLISHED, closing__regex=meta['name_re'],
                                   text__first_published_in__edition=Edition.GENERAL_AR)
            .order_by('text__first_published_in__date', 'text_id')
            .values_list('text_id', 'text__type', 'text__akn_uri', 'text__title_ar', 'text__first_published_in__date', 'closing'))
    seen: set[int] = set()
    years: dict[int, Counter] = defaultdict(Counter)
    named: dict[int, Counter] = defaultdict(Counter)
    first = last = None
    for text_id, kind, akn, title, day, closing in rows:
        if text_id in seen:
            continue
        seen.add(text_id)
        years[day.year]['dahir' if kind == TextType.DAHIR else 'order' if kind == TextType.ORDER else 'other'] += 1
        for key, rx in residents:
            if rx.search(closing or ''):
                named[day.year][key] += 1
                break
        row = {'date': day.isoformat(), 'title': ' '.join(title.split()), 'path': text_path(akn)}
        first = first or row
        last = row
    span = range(min(years), max(years) + 1) if years else range(0)
    refs = [{'key': 'clip', 'edition': Edition.GENERAL_AR, 'issue': meta['clip']['issue'], 'page': meta['clip']['page']}]
    refs += [{'key': f"s-{s['year']}", 'edition': Edition.GENERAL_AR, 'issue': s['issue'], 'page': s['page'], 'akn': s.get('akn')} for s in meta['signed']]
    return {
        'years': [{'year': y, 'dahir': years[y]['dahir'], 'order': years[y]['order'], 'other': years[y]['other'],
                   'resident': named[y].most_common(1)[0][0] if named[y] else None} for y in span],
        'total': len(seen), 'first': first, 'last': last, 'texts': clock.tie(refs),
    }
