"""The law Parliament votes, for «على كل قانون يصوّت عليه البرلمان، 13 مرسوما و48 قرارا وزاريا» (the blog's twenty-first
post, S15 of the first-principles review, 7 Nov 2026).

Three counts. The forms: every text the Arabic general edition printed since 1963, by its kind, and the laws Parliament
voted among them (one query). The hands: each text of the law's rank, year by year, by who made it, read from its title
as printed (voted by Parliament, a dahir or a royal decree «بمثابة قانون», a decree-law; one query). The reading: the words
of every text not repealed, in its latest Arabic version, by layer (one pass over the articles, about a minute on a
copy of the database). And the constitutions' and the 1965 decrees' pages (clock.tie)."""
import re
from collections import Counter, defaultdict

from apps.blog.services import clock
from apps.corpus.models import Article, Consolidation, Status, Text, Version
from apps.sources.models import Edition

FOLD = str.maketrans({'ـ': None, 'ى': 'ي'})


def _hand(title: str, hands: list[tuple[str, re.Pattern]]) -> str | None:
    t = ' '.join((title or '').translate(FOLD).split())
    return next((key for key, rx in hands if rx.search(t)), None)


def _texts(meta: dict) -> dict:
    """The forms since the span's first year, and the hands year by year."""
    first, last = meta['span']
    hands = [(h['key'], re.compile(h['re'])) for h in meta['hands']]
    forms: Counter = Counter()
    years: dict[int, Counter] = defaultdict(Counter)
    rows = (Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR, first_published_in__date__year__gte=first,
                                first_published_in__date__year__lte=last)
            .values_list('type', 'title_ar', 'first_published_in__date').iterator(chunk_size=20000))
    for kind, title, day in rows:
        forms[kind] += 1
        forms['all'] += 1
        if kind not in meta['ranks']:
            continue
        hand = _hand(title, hands) or ('dlaw' if kind == 'decree_law' else None)
        if hand:
            years[day.year][hand] += 1
            forms[f'hand-{hand}'] += 1
            if hand == 'rdl' and kind == 'decree':
                forms['hand-rdl-decree'] += 1
    keys = [h['key'] for h in meta['hands']]
    voted = forms['hand-voted']
    ratio = {'decrees': round((forms['decree'] - forms['hand-rdl-decree']) / voted), 'orders': round(forms['order'] / voted),
             'share': round(forms['all'] / voted)}
    return {'forms': dict(forms), 'ratio': ratio, 'years': [{'year': y, **{k: years[y].get(k, 0) for k in keys}} for y in range(first, last + 1)]}


def _reading(meta: dict) -> list[dict]:
    """The words of the texts not repealed, in their latest Arabic version, by layer."""
    latest = (Version.objects.filter(language='ar').exclude(consolidation=Consolidation.TRANSLATION)
              .order_by('text_id', '-valid_from', '-id').distinct('text_id').values('id'))
    layer_of = {t: layer['key'] for layer in meta['reading']['layers'] for t in layer['types']}
    words: Counter = Counter()
    texts: dict[str, set] = defaultdict(set)
    rows = (Article.objects.filter(version__in=latest, version__text__type__in=list(layer_of),
                                   version__text__status__in=[Status.IN_FORCE, Status.PARTLY_REPEALED])
            .values_list('version__text__type', 'version__text_id', 'body').iterator(chunk_size=20000))
    for kind, text_id, body in rows:
        layer = layer_of[kind]
        words[layer] += len((body or '').split())
        texts[layer].add(text_id)
    return [{'key': layer['key'], 'words': words[layer['key']], 'texts': len(texts[layer['key']])} for layer in meta['reading']['layers']]


def _refs(meta: dict) -> list[dict]:
    def one(key: str, r: dict) -> dict:
        return {'key': key, 'edition': Edition.GENERAL_AR, 'issue': r['issue'], 'bis': r.get('bis', False), 'page': r['page'], 'akn': r.get('akn')}
    return [one(f"c-{c['year']}", c) for c in meta['constitutions']] + [one(k, v) for k, v in meta['exception'].items()]


def count(meta: dict) -> dict:
    return {**_texts(meta), 'reading': _reading(meta), 'texts': clock.tie(_refs(meta))}
