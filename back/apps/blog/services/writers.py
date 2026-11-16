"""Who writes the texts the Bulletin publishes, for «من يكتب القواعد التي نعيش بها؟» (the blog's fourth post, B2 of
the blog-first-post review, 31 Oct 2026): each text by its author's kind (the King's dahirs, Parliament's laws, the Government's
decrees, ministers' orders, other bodies' decisions), year by year; ministers' orders by ministry (the first minister
its authority names) and by subject; Parliament's laws by kind; the decree-laws, year by year. Every grouping is a list
of words in the post's meta, read on the titles and authorities as the corpus holds them.

One query (each text's year, type, authority and title) and the arithmetic apart (`tabulate`), so rows exported from
the live database with psql give the same figures as the command."""
from collections import Counter, defaultdict

from apps.corpus.models import Text
from apps.sources.models import Edition


def count(meta: dict) -> dict:
    first, last = meta['span']
    rows = (Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR, first_published_in__date__year__gte=first,
                                first_published_in__date__year__lte=last)
            .values_list('first_published_in__date__year', 'type', 'authority', 'title_ar'))
    return tabulate(meta, rows)


def first_match(text: str, groups: list[dict], field: str = 'words') -> str:
    """The group whose word comes first in `text` (the first minister a joint order names), '' when none does."""
    best = None
    for g in groups:
        for word in g[field]:
            at = text.find(word)
            if at >= 0 and (best is None or at < best[0]):
                best = (at, g['key'])
    return best[1] if best else ''


def any_match(text: str, groups: list[dict]) -> str:
    """The first group, in the meta's order, with a word in `text`."""
    return next((g['key'] for g in groups if any(w in text for w in g['words'])), '')


def tabulate(meta: dict, rows) -> dict:
    first, last = meta['span']
    years = list(range(first, last + 1))
    authors = {t: a['key'] for a in meta['authors'] for t in a['types']}
    other = meta['authors'][-1]['key']
    by_year: dict[int, Counter] = defaultdict(Counter)
    ministries, subjects = Counter(), defaultdict(Counter)
    laws: dict[int, Counter] = defaultdict(Counter)
    decree_laws = Counter()
    for year, kind, authority, title in rows:
        author = authors.get(kind, other)
        by_year[year][author] += 1
        decade = year // 10 * 10
        if kind == 'order':
            ministries[first_match(authority or title, meta['ministries']) or 'other'] += 1
            subjects[decade][any_match(title, meta['subjects']) or 'other'] += 1
        elif kind in ('law', 'organic_law'):
            laws[decade][any_match(title, meta['laws']) or 'other'] += 1
        elif kind == 'decree_law':
            decree_laws[year] += 1
    decades = sorted({y // 10 * 10 for y in years})
    return {
        'span': [first, last],
        'authors': {a['key']: [by_year[y][a['key']] for y in years] for a in meta['authors']},
        'ministries': dict(ministries.most_common()),
        'subjects': {k: [subjects[d][k] for d in decades] for k in [s['key'] for s in meta['subjects']] + ['other']},
        'laws': {k: [laws[d][k] for d in decades] for k in [s['key'] for s in meta['laws']] + ['other']},
        'decades': decades,
        'decree_laws': [decree_laws[y] for y in years],
    }
