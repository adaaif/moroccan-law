"""Expropriation, for «نزع الملكية» (the blog's twenty-fourth post, S23 of the first-principles review, 7 Nov 2026).
Every text of the Arabic general edition whose title declares the public good and expropriates (meta.yaml's `title_re`
and `taking_re`), by the year the Bulletin printed it and by what it is for (the first of the meta's `purposes` found in
its title after «تقضي ب…»); for each purpose, the last declaration as an example (its title, its page, its text). One
query; the examples, the law and the Constitution are tied to their pages with `clock.tie`."""
import re
from collections import Counter, defaultdict

from apps.blog.services import clock
from apps.corpus.models import Text
from apps.sources.models import Edition

WHAT = re.compile(r'تقضي\s*(?:ب)?(.*?)(?:\s*و\s*ب?نزع|\s*بنزع|$)')


def purpose(title: str, purposes: list[tuple[str, re.Pattern]]) -> str:
    m = WHAT.search(title)
    words = m.group(1) if m else title
    return next((key for key, rx in purposes if rx.search(words)), 'other')


def count(meta: dict) -> dict:
    purposes = [(p['key'], re.compile(p['re'])) for p in meta['purposes']]
    first, last = meta['span']
    rows = (Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR, title_ar__regex=meta['title_re'])
            .filter(title_ar__regex=meta['taking_re'])
            .order_by('first_published_in__date', 'id')
            .values_list('akn_uri', 'title_ar', 'first_published_in__date', 'first_published_in__number',
                         'first_published_in__suffix', 'first_published_page'))
    years: dict[int, Counter] = defaultdict(Counter)
    latest: dict[str, tuple] = {}
    for akn, title, day, number, suffix, page in rows:
        if not first <= day.year <= last:
            continue
        key = purpose(title, purposes)
        years[day.year][key] += 1
        if day.year >= 2020 and page:
            latest[key] = (akn, ' '.join(title.split()), number, suffix, page)
    keys = [p['key'] for p in meta['purposes']] + ['other']
    refs = [{'key': f'e-{k}', 'edition': Edition.GENERAL_AR, 'issue': v[2], 'bis': bool(v[3]), 'page': v[4], 'akn': v[0]} for k, v in latest.items()]
    refs += [{'key': k, 'edition': Edition.GENERAL_AR, 'issue': meta[k]['issue'], 'bis': meta[k].get('bis', False), 'page': meta[k]['page'],
              'akn': meta[k]['akn']} for k in ('law', 'constitution')]
    return {
        'years': [{'year': y, **{k: years[y].get(k, 0) for k in keys}} for y in range(first, last + 1)],
        'examples': {k: {'title': v[1], 'akn': v[0]} for k, v in latest.items()},
        'texts': clock.tie(refs),
    }
