"""A text's answer: its facts, the version asked for (the latest, or the one in force on a day) and its articles, each
with its marks, page, changes and French, a long text sent a window at a time with its outline at its own address.
`text_answer` keeps it by generation; the MCP and the law page's drawing read it too."""
import re
from collections import namedtuple
from datetime import date

from apps.consolidation.services import history
from apps.corpus.api.views.base import issue_ref, text_ref
from apps.corpus.models import Article, Consolidation, Text
from apps.corpus.services import constitutions, generation
from apps.corpus.services.addresses import article_path, text_path
from apps.corpus.services.annotate import definitions, marks
from apps.corpus.services.citing import citer
from apps.corpus.services.codes import eras, everyday_name, official_link
from apps.corpus.services.heads import head_name
from apps.corpus.services.links import article_links, text_links
from apps.parliament.models import Explanation
from apps.sources.models import Document, Page, Source
from apps.sources.services.quality import page_reading
from apps.translations.models import FrenchArticle, FrenchText
from apps.translations.services import divisions


def fr_article(a: FrenchArticle | None, changes: list[dict] | None = None, standing=None) -> dict | None:
    """An article's French. From a consolidation (Adala's French labour code stands at 26 Oct 2011), or from the
    French BO that first printed it (52.05 on 16 Sep 2010, the road plan), `older` says the Arabic changed since: the
    French is the article before that change (T1 of the work plan)."""
    if a is None:
        return None
    older = bool(standing and any(c.get('on') and c['on'] > standing for c in changes or []))
    return {'label': a.label, 'body': divisions.trim(a.body), 'page': a.printed_page, 'older': older}


# A long text is sent a window of articles at a time (row 7 of the reader-experience review): the article asked for and the
# ones after it, with the whole text's outline; the reader's page asks for more as it scrolls. Law 58.25's 643
# articles were 1.1 MB and 20 s on a mid-range phone.
WINDOW_MAX = 80
MORE = 40                   # the articles `from` sends when no `count` is asked
# An outline gives every article's first eight words, about a tenth of an article: it counts one for every ten.
OUTLINE_PER = 10
OWN_FILE = (Consolidation.SGG, Consolidation.ADALA, Consolidation.DGI, Consolidation.BILL)  # versions whose pages are their own file's
CHUNK = 5000                # ids a query names at once (SQLite takes at most 32,766)
_WHOLE = re.compile(r'[0-9]{1,6}')


class Asked(ValueError):
    """A part of a text's request a reader may not ask; its field's name is the error's."""


def _number(params, name: str, lowest: int, highest: int | None = None) -> int | None:
    """A whole number a reader chose, in Western digits, within its bounds; None when it is not asked."""
    value = params.get(name)
    if value in (None, ''):
        return None
    if not _WHOLE.fullmatch(value) or not lowest <= int(value) <= (highest if highest is not None else int(value)):
        raise Asked(name)
    return int(value)


def asked_range(params) -> tuple[date | None, int | None, tuple[int, int] | None]:
    """(on, window, span) of a text's request, the one place they are read: `on` a date, `window` 1 to WINDOW_MAX
    articles, `from` 0 or more with `count` 1 to WINDOW_MAX (MORE when not asked). A zero or a minus sign once
    returned a text whole and counted nothing; Asked names the field that is wrong."""
    try:
        on = date.fromisoformat(params['on']) if params.get('on') else None
    except ValueError:
        raise Asked('on') from None
    window = _number(params, 'window', 1, WINDOW_MAX)
    start = _number(params, 'from', 0)
    count = _number(params, 'count', 1, WINDOW_MAX)
    return on, window, (start, start + (count or MORE)) if start is not None else None


def _window(eids: list[str], focus: str, window: int | None, span: tuple[int, int] | None) -> tuple[int, int]:
    """The articles [start, end) a request is sent, from the version's anchors in order: a span within the text, or a
    window from two before the focus."""
    total = len(eids)
    if span:
        start = min(span[0], total)
        return start, max(start, min(total, span[1]))
    if not window or total <= window:
        return 0, total
    at = eids.index(focus) if focus and focus in eids else 0
    start = max(0, at - 2)
    return start, min(total, start + window)


_MARKUP = re.compile(r'\*\*|\||-{3,}|^#+\s*', re.M)


def first_words(body: str, most: int = 8) -> str:
    """An article's first words, for the outline (P12 of the polish review): «يبرم عقد الكراء وجوبا بمحرر كتابي…»."""
    words = _MARKUP.sub(' ', body).split()
    return ' '.join(words[:most]) + ('…' if len(words) > most else '')


def outline(rows: list[Article]) -> list[dict]:
    """Every article's anchor, label, number and first words (`w`), and its heading path where it changes (`h`)."""
    out, last = [], None
    for a in rows:
        entry = {'eid': a.eid, 'label': a.label, 'number': a.number, 'w': first_words(a.body)}
        if a.heading_path != last:
            entry['h'] = a.heading_path
            last = a.heading_path
        out.append(entry)
    return out


def text_payload(text: Text, focus: str = '', on: date | None = None, window: int | None = None,
                 span: tuple[int, int] | None = None) -> dict:
    """A text whole: facts, version (the latest, or the one in force on `on`), articles (each with its address,
    its marks — links and defined terms —, its printed page, its changes and what this version changed in it),
    what it amends and what amended it, what it cites and what cites it. With `window`, a long text sends that
    many articles from the one in `focus` and its outline; with `span` (from, to), only those articles."""
    version, before = history.pick_version(text, on)
    issue = text.first_published_in
    pages = {}
    # Where an article's page is: the BO issue for a version as published (and a machine's, made from one), the
    # SGG's or Adala's own file for its consolidation.
    own_file = version is not None and version.consolidation in OWN_FILE
    document_id = issue.document_id if issue else None
    if own_file:
        document_id = version.source_document_id
    elif issue and issue.document_id:
        pages = dict(issue.document.pages.values_list('printed_number', 'index'))
    every = list(version.articles.all()) if version else []
    start, end = _window([a.eid for a in every], focus, window, span)
    rows = every[start:end]
    changes = history.settled(history.article_changes(text), version)
    proposals = history.proposals_of(text) if text.type != 'bill' else {}
    french = FrenchText.objects.filter(text_uri=text.akn_uri).first()
    in_french = {a.number: a for a in FrenchArticle.objects.filter(text_uri=text.akn_uri)} if french else {}
    earlier = {history.label_key(a.label) or a.number: a for a in before.articles.all()} if before else {}
    # How each article's page was read (one look per page, the articles of a text share a few).
    readings = {}
    if issue and issue.document_id and rows:
        printed = {a.printed_page for a in rows if a.printed_page}
        for page in Page.objects.filter(document_id=issue.document_id, printed_number__in=printed).select_related('document'):
            readings[page.printed_number] = page_reading(page)
    defined = definitions(every)
    marked = marks(text, rows, defined, among=every) if rows else {}
    linked = article_links(text, rows)
    cite = citer(text, version)
    from apps.search.services.famous import of_text
    known = of_text(text_path(text.akn_uri))         # «يُعرف في النقاش العام بـ…» (F10 of the famous-articles review)

    def was(a: Article) -> list | None:
        # «ما تغيّر» only where the law changed (HM38 of the hard-moment review): two copies valid from the same day
        # (Adala's and the BO's road code, 11 August 2016) are one law, and a colon's space, «.1» for «1 -», a hamza's
        # seat or a digit's script is no change.
        if before is None or before.valid_from == version.valid_from:
            return None
        old = earlier.get(history.label_key(a.label) or a.number)
        if old is not None and (old.body == a.body or history.same_words(old.body, a.body)):
            return None
        return history.word_diff(old.body if old else '', a.body)

    articles = [
        {'id': a.pk, 'order': a.order, 'label': a.label, 'number': a.number, 'heading_path': a.heading_path,
         'body': a.body, 'eid': a.eid, 'path': article_path(text.akn_uri, a.eid), 'page': a.printed_page,
         'document_id': document_id if a.printed_page else None,
         'page_index': (a.printed_page - 1 if own_file and a.printed_page else pages.get(a.printed_page)),
         'marks': marked.get(a.eid, []), 'citation': cite(a),
         'reading': 'layer' if own_file else readings.get(a.printed_page),
         'changes': history.changes_for(changes, a.label, a.number), 'diff': was(a),
         'proposed': proposals.get(history.label_key(a.label) or a.number),
         'cited_by': linked[a.number]['cited_by'] if a.number in linked else [],
         'applied_by': linked[a.number]['applied_by'] if a.number in linked else [],
         'known_as': known.get(a.number),
         'french': fr_article(in_french.get(history.label_key(a.label) or a.number),
                              history.changes_for(changes, a.label, a.number),
                              french and (french.consolidated_to or french.issue_date))}
        for a in rows]
    if span:
        return {'articles': articles, 'range': [start, end], 'total_articles': len(every)}
    return {
        **text_ref(text), 'focus': focus, 'citation': cite(None), 'everyday_name': everyday_name(text),
        # Its name in the browser's title, which is a search result's too (IX8 of the search-engines review): the server's head
        # says the same (heads.head_name), and the subject a cut title left out.
        'title_name': head_name(text),
        'eras': eras(text), 'constitution': constitutions.facts(text),
        'official': None if version else official_link(text),
        'signed_on': text.signed_on, 'signed_on_hijri': text.signed_on_hijri,
        'authority': text.authority, 'promulgating_dahir': text.promulgating_dahir, 'rubric': text.rubric,
        'status': text.status, 'aliases': text.aliases,
        'issue': issue_ref(issue) if issue else None, 'page': text.first_published_page,
        # A copy's articles open its own file; the text's first page is still the Bulletin's (RD5 of
        # the readers review: the family code names BO 5184, page 418, and the reader opens that page).
        'page_index': pages.get(text.first_published_page) if not (own_file and issue and text.first_published_page)
        else issue.document.pages.filter(printed_number=text.first_published_page).values_list('index', flat=True).first(),
        'version': None if version is None else {
            'language': version.language, 'valid_from': version.valid_from, 'valid_to': version.valid_to,
            'consolidation': version.consolidation, 'consolidation_label': version.get_consolidation_display(),
            # A copy of the text as first issued, not assembled from amendments (the constitutions before 2011).
            'as_issued': bool(version.source_document_id and version.source_document.meta.get('as_issued')),
            # Words a model read from the images of an archive issue's pages (1956–2018): the printed page is the text
            # (UX3 of the phone-test review).
            'read_from_scans': bool(version.consolidation == 'as_published' and version.source_document_id
                                    and version.source_document.meta.get('archive')),
            'source_pages': version.source_pages, 'preamble': version.preamble, 'closing': version.closing,
            # A version a model translated from the official French (BO 7410: no Arabic online). The engine stays
            # out: readers are told «الذكاء الاصطناعي», never a model's name.
            'translated_from': version.translated_from, 'translated_at': version.translated_at,
            'source': None if not version.source_document_id or not own_file else {
                'document_id': version.source_document_id, 'url': version.source_document.url,
                'as_of': version.source_document.meta.get('as_of'),
                'first_issue': version.source_document.meta.get('first_issue'),
                'first_page': version.source_document.meta.get('first_page')},
            'before': None if before is None else {'valid_from': before.valid_from, 'consolidation': before.consolidation}},
        'versions': history.versions_list(text, version),
        'explanations': [{'kind': e.kind, 'body': e.body, 'source_url': e.source_url, 'pages': e.pages}
                         for e in Explanation.objects.filter(text_uri=text.akn_uri)],
        'french': None if french is None else {
            'title': french.title, 'issue_number': french.issue_number, 'issue_suffix': french.issue_suffix,
            'issue_date': french.issue_date, 'pages': french.pages, 'consolidated_to': french.consolidated_to,
            'document_id': Document.objects.filter(sha256=french.document_sha).values_list('pk', flat=True).first()},
        'bill': next(({'url': d.url, 'document_id': d.pk, 'page': d.meta.get('page')} for d in
                      Document.objects.filter(source=Source.PARLIAMENT, meta__text_uri=text.akn_uri)[:1]), None),
        'articles': articles,
        'total_articles': len(every),
        'range': [start, end],
        # A long text's outline has its own address (S15 of the performance audit: 242 KB of the DOC's 313 KB answer,
        # sent again with every window): the version's, named with the corpus's generation so it is kept for good.
        'outline': None,
        'outline_url': outline_url(version) if end - start < len(every) else None,
        'definitions': defined,
        'whole_changes': changes.get('', []),
        **text_links(text),
    }


Picked = namedtuple('Picked', 'id valid_from consolidation')


def _versions(text: Text) -> list[Picked]:
    """A text's versions, as `history.pick` reads them (kept: a request names its version without a query)."""
    rows = generation.kept(['versions', text.pk], lambda: list(text.versions.values_list('id', 'valid_from', 'consolidation')))
    return [Picked(*row) for row in rows]


def _anchors(version_id: int) -> list[str]:
    """A version's article anchors in order (the MCP keeps the same)."""
    return generation.kept(['eids', version_id], lambda: list(Article.objects.filter(version_id=version_id)
                                                              .order_by('order').values_list('eid', flat=True)))


def text_answer(text: Text, eid: str = '', on: date | None = None, window: int | None = None,
                span: tuple[int, int] | None = None):
    """A text's answer as sent, kept by generation, and the articles it carries (what the day of reading counts): the
    API's and the law page's drawing share it.

    It is kept under what it is made of, never under what was asked: the version `on` picks (every day of a version's
    life is one answer), the anchor only when that version holds it (another opens the text at its start, as the page
    then says), and the articles' bounds. Keys a caller chose without bound had let a hundred requests turn the cache
    over."""
    picked, _ = history.pick(_versions(text), on)
    eids = _anchors(picked.id) if picked else []
    focus = eid if eid in eids else ''
    start, end = _window(eids, focus, window, span)
    return generation.counted(['at', text.akn_uri, picked and picked.id, focus, start, end, span is not None],
                              lambda: text_payload(text, focus=focus, on=on, window=window, span=span),
                              lambda d: len(d['articles']))


def outline_url(version) -> str:
    gen = generation.current('corpus')
    return f'/api/corpus/outline/{version.pk}/' + (f'?g={gen}' if gen else '')
