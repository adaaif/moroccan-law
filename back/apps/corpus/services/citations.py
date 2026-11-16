"""A citation (as ma_law reads it) matched to the corpus: the text, the article, the BO issue, and what has
happened to them since. The search uses it to jump; the citation checker to tell a reader where each
reference stands."""
from datetime import date

from django.db.models import Exists, OuterRef, Q

from apps.consolidation.models import Change
from apps.corpus.models import Article, Status, Text, Version, latest_ids
from apps.corpus.services import works
from apps.corpus.services.addresses import article_path, text_path
from apps.corpus.services.codes import ADALA, CODES, OFFICIAL
from apps.sources.models import Edition, Issue

SHOWN = (Change.State.CHECKED, Change.State.CONFIRMED, Change.State.READ)


def text_brief(text: Text) -> dict:
    from apps.corpus.services.codes import display_name
    return {'id': text.pk, 'path': text_path(text.akn_uri), 'type': text.type, 'title': text.title_ar, 'name': display_name(text),
            'number_as_printed': text.number_as_printed, 'status': text.status, 'in_corpus': text.in_corpus}


# The text kinds a citation's kind may be stored as: a dahir that stands as a law is often kept as a law.
DATED_KINDS = {'dahir': ('dahir', 'law'), 'law': ('law', 'dahir'), 'decree': ('decree',), 'decree_law': ('decree_law',),
               'organic_law': ('organic_law',), 'order': ('order',), 'decision': ('decision',)}


def _find_text(citation: dict, on: date | None = None) -> Text | None:
    """The text a citation names, by its kind and number (or its code's name, as it was on `on`), never by a number
    alone; or by its kind and the day it was signed («ظهير 12 غشت 1913», B5 of the search plan) when one text alone
    fits."""
    if citation.get('date') and not citation.get('text_number') and not citation.get('code'):
        kinds = DATED_KINDS.get(citation.get('text_kind') or '', ())
        try:
            day = date.fromisoformat(citation['date'])
        except ValueError:
            return None
        found = list(Text.objects.filter(type__in=kinds, signed_on=day)[:2]) if kinds else []
        return found[0] if len(found) == 1 else None
    if citation.get('code') and not citation.get('text_number'):
        uri = works.code_address(citation['code'], on)
    elif citation.get('text_number'):
        uri, state = works.resolve(citation.get('text_kind'), citation['text_number'])
        if state != 'resolved':
            return None
    else:
        return None
    text = Text.objects.filter(akn_uri=uri).first() if uri else None
    # A finance law takes its bill's number: until the BO publishes the law, «60.26» opens the bill, said as one
    # (the finance-bill review, P19).
    if citation.get('text_number') and citation.get('text_kind') in (None, 'law') and \
            (text is None or not text.versions.exists()):
        bill = works.address('law', citation['text_number']).replace('/act/loi/', '/act/projet-loi/')
        return Text.objects.filter(akn_uri=bill, type='bill').first() or text
    return text


def _find_article(text: Text, number: str) -> Article | None:
    version = text.latest_version()
    if version is None:
        return None
    return version.articles.filter(number=number).order_by('order').first()


def _changes(text: Text, label_number: str | None, since: date | None) -> list[dict]:
    """The changes a text received (to this article when one is named), published after `since`, shown as fact."""
    return _changes_many([(text.akn_uri, label_number)], since)[0]


def _changes_many(asked: list[tuple[str, str | None]], since: date | None) -> list[list[dict]]:
    """`_changes` for each (text's address, article's number) pair, in two queries whatever their number."""
    rows = Change.objects.filter(text_uri__in={uri for uri, _ in asked}, source=Change.Source.READING, state__in=SHOWN)
    if since:
        rows = rows.filter(published_on__gt=since)
    rows = list(rows.order_by('published_on', 'pk'))
    # With whether the site holds each: asked of every row's text one by one, it was one query a change (76 for a question
    # naming an article of the penal code: RD14 of the readers review, 9 Nov 2026).
    by = held(r.by_uri for r in rows)
    of: dict[str, list] = {}
    for r in rows:
        of.setdefault(r.text_uri, []).append(r)
    out = []
    for uri, label_number in asked:
        shown = []
        for r in of.get(uri, []):
            if label_number and r.number not in (label_number, ''):
                continue
            issue = f'{r.issue}-bis' if r.issue_bis else (str(r.issue) if r.issue else None)
            shown.append({'action': r.verb, 'label': r.number, 'by': text_brief(by[r.by_uri]) if r.by_uri in by else None,
                          'published': r.published_on, 'issue': issue, 'state': r.state})
        out.append(shown)
    return out


def _signed(citation: dict) -> tuple[tuple, date] | None:
    """A dated citation's text kinds and day, as `_find_text` reads them; None when it names no kind or no day."""
    kinds = DATED_KINDS.get(citation.get('text_kind') or '', ())
    try:
        day = date.fromisoformat(citation['date'])
    except ValueError:
        return None
    return (kinds, day) if kinds else None


def held(uris) -> dict[str, Text]:
    """The texts at these addresses, each knowing whether the site holds its words, in one query."""
    uris = set(uris)
    return {t.akn_uri: t for t in Text.objects.filter(akn_uri__in=uris).annotate(
        has_versions=Exists(Version.objects.filter(text=OuterRef('pk'))))} if uris else {}


def resolve_many(citations: list[dict], on: date | None = None, *, checker: bool = False,
                 since: date | None = None) -> list[dict]:
    """What `resolve` answers for each citation, without the changes its text received (an article's link marks never
    show them), for a window of articles at once: about six queries whatever the citations (S3 of the performance
    audit: a window of the finance law cost 467, one change list per cited text).

    `checker`: what `resolve` answers, whole, for the citation checker's list (OP15 of the open-source audit: one
    `resolve` a citation, about nine queries each, three hundred citations a request): a finance law's number opens its
    bill until the law is held, a text named by its kind and the day it was signed is the one text that fits, and each
    text's changes since `since` come along, in three queries more and one for the dated ones."""
    plans: list[tuple[str, object]] = []
    for c in citations:
        if c.get('kind') == 'issue' and c.get('issue'):
            plans.append(('issue', None))
        elif checker and c.get('date') and not c.get('text_number') and not c.get('code'):
            plans.append(('dated', _signed(c)))
        elif c.get('code') and not c.get('text_number'):
            plans.append(('code', works.code_target(c['code'], on)))
        elif c.get('text_number'):
            plans.append(('number', works.candidates(c.get('text_kind'), c['text_number'])))
        else:
            plans.append(('none', None))
    followed = works.follow_many(
        [plan[0] for kind, plan in plans if kind == 'code' and plan[1]]
        + [uri for kind, plan in plans if kind == 'number' and not isinstance(plan, str) for uri in plan])
    named = []
    for kind, plan in plans:
        if kind == 'code':
            named.append([followed[plan[0]] if plan[1] else plan[0]] if plan[0] else [])
        elif kind == 'number' and not isinstance(plan, str):
            named.append([followed[uri] for uri in plan])
        else:
            named.append([])
    texts = held(uri for uris in named for uri in uris)
    chosen: list[Text | None] = []
    bills: dict[int, str] = {}
    for i, ((kind, _), uris, c) in enumerate(zip(plans, named, citations)):
        uri = uris[0] if kind == 'code' and uris else ''
        if kind == 'number' and uris:
            uri, state = works.choose(uris, set(texts))
            uri = uri if state == 'resolved' else ''
        chosen.append(texts.get(uri) if uri else None)
        if checker and kind == 'number' and uri and c.get('text_kind') in (None, 'law') and \
                (chosen[-1] is None or not chosen[-1].has_versions):
            # A finance law takes its bill's number, as `_find_text` reads it (the finance-bill review, P19).
            bills[i] = works.address('law', c['text_number']).replace('/act/loi/', '/act/projet-loi/')
    if bills:
        found = {uri: t for uri, t in held(bills.values()).items() if t.type == 'bill'}
        for i, uri in bills.items():
            chosen[i] = found.get(uri) or chosen[i]
    signed = {i: plan for i, (kind, plan) in enumerate(plans) if kind == 'dated' and plan}
    if signed:
        # As `_find_text` reads a dated citation: the one text of its kinds signed that day, else none.
        kinds, days = {k for ks, _ in signed.values() for k in ks}, {day for _, day in signed.values()}
        texts_signed = list(Text.objects.filter(type__in=kinds, signed_on__in=days).annotate(
            has_versions=Exists(Version.objects.filter(text=OuterRef('pk')))))
        for i, (ks, day) in signed.items():
            fits = [t for t in texts_signed if t.type in ks and t.signed_on == day]
            chosen[i] = fits[0] if len(fits) == 1 else None
    # The cited articles, in each text's latest version, as _find_article reads them.
    asked = {t.pk for t, c in zip(chosen, citations) if t is not None and c.get('article')}
    newest = latest_ids(Version.objects.filter(text_id__in=asked).order_by()
                        .values_list('id', 'text_id', 'valid_from', 'consolidation')) if asked else {}
    wanted = Q()
    for t, c in zip(chosen, citations):
        if t is not None and c.get('article') and t.pk in newest:
            wanted |= Q(version_id=newest[t.pk], number=c['article'])
    articles: dict[tuple, Article] = {}
    for a in (Article.objects.filter(wanted).order_by('version_id', 'order').only('id', 'version_id', 'number', 'label', 'eid')
              if wanted else []):
        articles.setdefault((a.version_id, a.number), a)
    issues = {(str(i.number), i.suffix): i for i in Issue.objects.filter(
        edition=Edition.GENERAL_AR, number__in={c['issue'] for (kind, _), c in zip(plans, citations) if kind == 'issue'})} \
        if any(kind == 'issue' for kind, _ in plans) else {}
    out = []
    for (kind, _), c, text in zip(plans, citations, chosen):
        r = {'citation': {k: c.get(k) for k in CITED}, 'state': 'unknown', 'name': None, 'text': None, 'article': None,
             'issue': None, 'changes': [], 'official': None}
        out.append(r)
        if kind == 'issue':
            issue = issues.get((str(c['issue']), c.get('issue_suffix') or ''))
            if issue:
                r.update(state='issue', issue={'key': issue.key, 'edition': issue.edition, 'date': issue.date,
                                               'path': f'/bo/{issue.edition}/{issue.key}'})
            else:
                r['state'] = 'not_in_corpus'
            continue
        code = c.get('code')
        if code in CODES:
            r['name'] = {'ar': CODES[code][0], 'fr': CODES[code][1]}
        if text is None:
            r['state'] = 'not_in_corpus' if (code or c.get('text_number')) else 'unknown'
            if code:
                r['official'] = OFFICIAL.get(code, ADALA)
            continue
        r['text'] = text_brief(text)
        if c.get('article'):
            article = articles.get((newest.get(text.pk), c['article']))
            if article:
                r['article'] = {'label': article.label, 'eid': article.eid, 'path': article_path(text.akn_uri, article.eid)}
                r['state'] = 'found'
            else:
                r['state'] = 'text_only'
        else:
            r['state'] = 'found' if r['text']['in_corpus'] else 'not_in_corpus'
        if r['state'] == 'not_in_corpus' and code:
            r['official'] = OFFICIAL.get(code, ADALA)
        if text.status == Status.REPEALED:
            r['state'] = 'repealed'
    if checker:
        asked = [(text.akn_uri, c.get('article')) for text, c in zip(chosen, citations) if text is not None]
        for r, changes in zip([r for r, text in zip(out, chosen) if text is not None], _changes_many(asked, since)):
            r['changes'] = changes
    return out


CITED = ('kind', 'raw', 'article', 'text_kind', 'text_number', 'code', 'issue', 'issue_suffix', 'start', 'end', 'date')


def resolve(citation: dict, since: date | None = None, on: date | None = None) -> dict:
    """{state, name, text, article, issue, changes}: state is found (the article or text is in the corpus),
    text_only (the text is, the article is not), not_in_corpus (a code or text we only know by name or number),
    issue (a BO issue), or unknown."""
    out = {'citation': {k: citation.get(k) for k in CITED},
           'state': 'unknown', 'name': None, 'text': None, 'article': None, 'issue': None, 'changes': [],
           'official': None}
    if citation.get('kind') == 'issue' and citation.get('issue'):
        issue = Issue.objects.filter(number=citation['issue'], edition=Edition.GENERAL_AR,
                                     suffix=citation.get('issue_suffix') or '').first()
        if issue:
            out.update(state='issue', issue={'key': issue.key, 'edition': issue.edition, 'date': issue.date,
                                              'path': f'/bo/{issue.edition}/{issue.key}'})
        else:
            out['state'] = 'not_in_corpus'
        return out
    code = citation.get('code')
    if code in CODES:
        out['name'] = {'ar': CODES[code][0], 'fr': CODES[code][1]}
    text = _find_text(citation, on)
    if text is None:
        out['state'] = 'not_in_corpus' if (code or citation.get('text_number')) else 'unknown'
        if code:
            out['official'] = OFFICIAL.get(code, ADALA)
        return out
    out['text'] = text_brief(text)
    article_no = citation.get('article')
    if article_no:
        article = _find_article(text, article_no)
        if article:
            out['article'] = {'label': article.label, 'eid': article.eid, 'path': article_path(text.akn_uri, article.eid)}
            out['state'] = 'found'
        else:
            out['state'] = 'text_only'
    else:
        out['state'] = 'found' if out['text']['in_corpus'] else 'not_in_corpus'
    if out['state'] == 'not_in_corpus' and code:
        out['official'] = OFFICIAL.get(code, ADALA)
    if text.status == Status.REPEALED:
        out['state'] = 'repealed'
    out['changes'] = _changes(text, article_no, since)
    return out
