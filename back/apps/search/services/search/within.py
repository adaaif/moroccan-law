"""«ابحث في هذا النص» (P10 of the polish review): the articles of one text that hold the words, those that hold them
side by side first, each with two lines around them, and the forms the text writes them in, which the law page marks."""
import re

import ma_law

from apps.corpus.services.addresses import article_path, text_path
from apps.search.services.search.asking import asked_words
from apps.search.services.search.query import TYPED_MOST
from apps.search.services.search.quotes import _quote_spans, quoted
from apps.search.services.search.snippets import SNIPPET, _WORD, snippet

FIND_MOST = 300         # articles «ابحث في هذا النص» lists


FORMS_MOST = 60       # the word forms a text's marks light (H2 of the search's marks, 29 Oct 2026)
_EDGE = re.compile(r'^[^\w]+|[^\w]+$')     # a form without the punctuation around it: «الكراء،» → «الكراء»


def _holds(wanted: set, stems: set, quotes: dict, any_word: bool) -> bool:
    """Whether an article holds the words (by their stems) and the quoted phrases (where _quote_spans found them):
    all of them, or any with `any_word`."""
    if any_word:
        return bool(wanted & stems) or any(quotes.values())
    return wanted <= stems and all(quotes.values())


def _quoted_forms(body: str, quotes: dict, forms: dict) -> None:
    """The quoted phrases as the text writes them («القوة القاهرة» for «"القوه القاهره"»), for the law page's marks."""
    for s0, e0 in sorted(span for spans in quotes.values() for span in spans):
        if len(forms) < FORMS_MOST:
            forms.setdefault(' '.join(body[s0:e0].split()), None)


def find_in(path: str, query: str, on=None, any_word: bool = False) -> dict | None:
    """«ابحث في هذا النص» (P10 of the polish review): the articles of one text (the version in force, or on `on`) that hold
    every word (any of them with `any_word`), in the text's order, those that hold the words side by side as typed first
    (`together`, HM33), each with two lines around the first, and `words`: the
    forms the text writes them in («كراء» → «الكراء», «للكراء»), matched as the search matches, which the law page marks
    when a reader comes from a search (H2). Words between quotes are matched as typed, side by side, as the search
    matches them, and marked as a whole. None when the address leads to no text."""
    from apps.consolidation.services import history
    from apps.corpus.services.addresses import split_path
    from apps.corpus.services.works import text_at

    text, _ = text_at(split_path(path.strip('/'))[0])
    if text is None:
        return None
    q = query.strip()[:TYPED_MOST]
    out = {'query': q, 'path': text_path(text.akn_uri), 'count': 0, 'articles': [], 'words': []}
    phrases, _, plain = quoted(q)
    words = plain if phrases else q
    terms = ma_law.search_terms(asked_words(words)) if words else []
    version, _ = history.pick_version(text, on)
    if not (terms or phrases) or version is None:
        return out
    wanted = set(terms)
    forms: dict[str, None] = {}
    # The words as typed, side by side (HM33 of the hard-moment review: «السكن الاجتماعي» in the tax code listed art.
    # 6 first, which holds «السكنية» and «الاجتماعية» apart): the articles that hold them so come first, in the text's order.
    side = ' '.join(ma_law.tokens(asked_words(words))) if words and not any_word and len(terms) > 1 else ''
    found = []
    for a in version.articles.all():
        stems = set(ma_law.index_terms(a.body)) if wanted else set()       # one call an article (S22), not one a word
        quotes = {p: _quote_spans(a.body, p) for p in phrases}
        if _holds(wanted, stems, quotes, any_word):
            out['count'] += 1
            found.append((a, bool(side) and bool(_quote_spans(a.body, side))))
            _quoted_forms(a.body, quotes, forms)
            if len(forms) < FORMS_MOST and wanted:
                for m in _WORD.finditer(a.body):
                    w = _EDGE.sub('', m.group(0))
                    if w and w not in forms and any(ma_law.stem(t) in wanted for t in ma_law.tokens(w)):
                        forms[w] = None
    found.sort(key=lambda x: not x[1])
    out['together'] = sum(1 for _, together in found if together)
    out['articles'] = [{'eid': a.eid, 'label': a.label, 'number': a.number, 'path': article_path(text.akn_uri, a.eid),
                        'together': together,
                        'snippet': snippet(a.body, terms, *SNIPPET, exact=[side] if together else phrases)}
                       for a, together in found[:FIND_MOST]]
    if re.search(r'[A-Za-zÀ-ÿ]', q):
        # A French question: the text's official French holds its words (a French reader reads it first, N16).
        from apps.translations.models import FrenchArticle

        seen = {x['number'] for x in out['articles']}
        numbers = []
        for number, body in FrenchArticle.objects.filter(text_uri=text.akn_uri).values_list('number', 'body'):
            stems = set(ma_law.index_terms(body)) if wanted else set()
            quotes = {p: _quote_spans(body, p) for p in phrases}
            if _holds(wanted, stems, quotes, any_word):
                numbers.append(number)
                _quoted_forms(body, quotes, forms)
                for m in _WORD.finditer(body) if wanted else ():
                    w = _EDGE.sub('', m.group(0))
                    if w and w not in forms and len(forms) < FORMS_MOST and set(ma_law.index_terms(w)) & wanted:
                        forms[w] = None
        rows = [a for a in version.articles.filter(number__in=numbers) if a.number not in seen]
        out['count'] += len(rows)
        out['articles'] += [{'eid': a.eid, 'label': a.label, 'number': a.number, 'path': article_path(text.akn_uri, a.eid),
                             'together': False, 'snippet': []} for a in rows][:max(0, FIND_MOST - len(out['articles']))]
        # The addresses alone: `.only('eid')` through the version made Django ask each article's version again, one
        # query an article (589 for the Labour Code: RD14 of the readers review).
        order = {eid: i for i, eid in enumerate(version.articles.values_list('eid', flat=True))}
        out['articles'].sort(key=lambda x: (not x['together'], order.get(x['eid'], 0)))
    out['words'] = list(forms)[:FORMS_MOST]
    return out
