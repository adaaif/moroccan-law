"""What a search's answer carries beside its results: on a French page, the official French of the articles it shows
and of a door's articles; and a topic's words of the law, each with the article of the topic's own texts that holds it
best."""
import ma_law

from apps.corpus.services.addresses import text_path
from apps.corpus.services.codes import texts_of
from apps.search.models import SearchEntry
from apps.search.services.search.asking import asked_words
from apps.search.services.search.bm25 import _bm25, _brief, _texts
from apps.search.services.search.quotes import quoted
from apps.search.services.search.snippets import SNIPPET, snippet


def with_french(out: dict) -> dict:
    """On a French page (N16 of the read-and-trusted review): each shown article's official French, its label and two
    lines around the words, when the site holds it; the web shows it first with the Arabic a tap away. «licenciement
    abusif» answered with the Labour Code's articles in Arabic, their French on the site all along. One query for the page."""
    from apps.consolidation.services.history import label_key
    from apps.corpus.services.addresses import split_path
    from apps.translations.models import FrenchArticle
    from apps.translations.services import divisions

    wanted: dict[tuple[str, str], list[dict]] = {}
    for r in out.get('results', []):
        uri = split_path(r['text']['path'])[0]
        for a in r['articles']:
            wanted.setdefault((uri, label_key(a['label']) or a['eid'].removeprefix('art_')), []).append(a)
    if not wanted:
        return out
    phrases, _, plain = quoted(out['query'])
    terms = ma_law.search_terms(asked_words(out.get('asked') or (plain if phrases else out['query'])))
    for fa in FrenchArticle.objects.filter(text_uri__in={u for u, _ in wanted}, number__in={n for _, n in wanted}):
        for a in wanted.get((fa.text_uri, fa.number), []):
            a['french'] = {'label': fa.label, 'snippet': snippet(divisions.trim(fa.body), terms, *SNIPPET, exact=phrases)}
    return out


def door_french(rows: list[dict]) -> list[dict]:
    """A door's articles with their official French, for a French page (RD12 of the readers review, 9 Nov 2026):
    «congé de maternité» was answered by a French card over the Labour Code's articles in Arabic, their French on
    the site all along and shown in the results below. One query."""
    from apps.corpus.services.addresses import split_path
    from apps.translations.models import FrenchArticle
    from apps.translations.services import divisions

    wanted = {}
    for row in rows:
        uri, eid = split_path(row['path'])
        wanted[(uri, row.get('number') or eid.removeprefix('art_'))] = row
    if not wanted:
        return rows
    for fa in FrenchArticle.objects.filter(text_uri__in={u for u, _ in wanted}, number__in={n for _, n in wanted}):
        row = wanted.get((fa.text_uri, fa.number))
        if row is not None:
            row['french'] = {'label': fa.label, 'body': divisions.trim(fa.body)}
    return rows


def topic_words(slug: str) -> list[dict]:
    """A topic's words of the law (topics.json `words`, the /words pages), each with the article of the topic's own
    texts that holds it best: what a question in everyday words most likely asks about (P9 of the polish review). Found
    by searching the word, never guessed; a word none of its texts holds comes alone."""
    from django.core.cache import cache

    from apps.topics.services import topics
    from apps.explain.services import concepts

    topic = topics.find(slug)
    if topic is None:
        return []
    found = cache.get(f'topic-words:{slug}')
    if found is not None:
        return found
    own = {text_path(t.akn_uri) for t in texts_of(topic['codes']).values() if t}
    found = []
    for key in topic['words']:
        word = concepts.find(key)
        if not word or word['built_in']:
            continue
        terms = ma_law.search_terms(word['search'])
        hits = _bm25(terms, all_words=True, types=[], years=(None, None), repealed=False) if terms else []
        best = next((h for h in hits if h[1] == SearchEntry.Kind.ARTICLE and h[2] in own), None)
        article = SearchEntry.objects.filter(pk=best[0]).first() if best else None
        text = _texts([best[2]]).get(best[2]) if best else None
        found.append({'slug': word['slug'], 'term': word['term'], 'search': word['search'], 'article': article and text and {
            'label': article.label, 'path': article.path, 'text': _brief(text),
            'snippet': snippet(article.body, terms, *SNIPPET)}})
    cache.set(f'topic-words:{slug}', found, 3600)
    return found
