"""What changed in the corpus since a day, for a program that keeps a copy of it in step (GET /api/v1/changes):

- `published`: the texts the Bulletin published since that day (a bill is not among them: it is no Bulletin text);
- `amended`: the changes to the texts the site holds that the Bulletin published since then, each with the amending
  text, the article it changes where one is named, and the day it takes effect.

A change is one the site shows as fact: read in the amending text, and checked by a person, confirmed by another
source or read with nothing against it, as the references' check counts the changes since a day
(apps/corpus/services/citations.py `SHOWN`). A bill's proposals are never among them.

Both lists are one feed, read a page at a time in one order: the Bulletin's date, newest first; on one day the texts
published before the changes; then the newest row first. A page holds at most PAGE items of the two kinds together,
and `next` is the last one's place in that order (its date, its kind and its row): the next page starts where this one
stopped even while new rows arrive, never at an offset. A day further back than REACH days is refused: a whole copy
comes from the edition (/api/open/). A page costs the same few queries whatever it holds."""
import re
from datetime import date, timedelta

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.consolidation.models import Change
from apps.corpus.models import Article, Text, TextType, Version, latest_ids
from apps.corpus.services.addresses import article_path, text_path
from apps.corpus.services.citations import SHOWN
from apps.mcp.services.law import STATUS, site
from apps.sources.models import Edition, Issue

PAGE = 200
REACH = 366
PUBLISHED, AMENDED = 'p', 'a'
# The two kinds' order on one day: the texts published, then the changes.
RANK = {PUBLISHED: 0, AMENDED: 1}
CURSOR = re.compile(r'^(\d{4}-\d{2}-\d{2})\.([pa])\.(\d{1,18})$')


def _since(raw) -> date:
    if not raw:
        raise Refused('since', 'required')
    try:
        day = date.fromisoformat(str(raw))
    except ValueError:
        raise Refused('since', 'invalid') from None
    if day < timezone.localdate() - timedelta(days=REACH):
        raise Refused('since', 'too_far')
    return day


def _cursor(raw) -> tuple[date, str, int] | None:
    if not raw:
        return None
    found = CURSOR.match(str(raw))
    if not found:
        raise Refused('cursor', 'invalid')
    try:
        day = date.fromisoformat(found.group(1))
    except ValueError:
        raise Refused('cursor', 'invalid') from None
    return day, found.group(2), int(found.group(3))


def _published(since: date, after) -> list[Text]:
    rows = (Text.objects.filter(first_published_in__date__gte=since).exclude(type=TextType.BILL)
            .select_related('first_published_in').order_by('-first_published_in__date', '-pk'))
    if after:
        day, kind, pk = after
        if kind == PUBLISHED:
            rows = rows.filter(Q(first_published_in__date__lt=day) | Q(first_published_in__date=day, pk__lt=pk))
        else:                       # a change was last: the texts of its day came before it
            rows = rows.filter(first_published_in__date__lt=day)
    return list(rows[:PAGE + 1])


def _amended(since: date, after) -> list[Change]:
    rows = (Change.objects.filter(source=Change.Source.READING, state__in=SHOWN, published_on__gte=since)
            .filter(Exists(Text.objects.filter(akn_uri=OuterRef('text_uri')))).order_by('-published_on', '-pk'))
    if after:
        day, kind, pk = after
        if kind == PUBLISHED:       # a text was last: its day's changes come after it
            rows = rows.filter(published_on__lte=day)
        else:
            rows = rows.filter(Q(published_on__lt=day) | Q(published_on=day, pk__lt=pk))
    return list(rows[:PAGE + 1])


def _issue(edition: str, key: str, day: date, page, held: bool = True) -> dict:
    """Where the Bulletin printed it; its link when the site holds that issue."""
    return {'bo': key or None, 'edition': edition, 'date': day.isoformat(), 'page': page,
            'url': site(f'/bo/{edition}/{key}') if held and key else None}


def _text_item(t: Text) -> dict:
    issue = t.first_published_in
    path = text_path(t.akn_uri)
    return {'id': path, 'url': site(path), 'title': t.title_ar, 'title_fr': t.title_fr or None, 'type': t.type,
            'number': t.number_as_printed, 'status': STATUS.get(t.status, t.status), 'on': issue.date.isoformat(),
            'published_in': _issue(issue.edition, issue.key, issue.date, t.first_published_page)}


def _articles_of(changes: list[Change], texts: dict[str, Text]) -> dict[tuple[str, str], str]:
    """Each (text, article number) a change names, and that article's address in the text's version today, where it
    holds one: two queries for the page."""
    wanted = {(c.text_uri, c.number) for c in changes if c.number and c.text_uri in texts}
    if not wanted:
        return {}
    ids = {texts[uri].pk: uri for uri, _ in wanted}
    newest = latest_ids(Version.objects.filter(text_id__in=ids).values_list('pk', 'text_id', 'valid_from',
                                                                             'consolidation'))
    uri_of = {version: ids[text] for text, version in newest.items()}
    found = {}
    for version, number, eid in (Article.objects.filter(version_id__in=uri_of, number__in={n for _, n in wanted})
                                 .exclude(eid='').order_by('order').values_list('version_id', 'number', 'eid')):
        found.setdefault((uri_of[version], number), article_path(uri_of[version], eid))
    return found


def _change_items(changes: list[Change]) -> list[dict]:
    if not changes:
        return []
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in={c.text_uri for c in changes} |
                                                       {c.by_uri for c in changes if c.by_uri})
             .only('pk', 'akn_uri', 'title_ar', 'type')}
    articles = _articles_of(changes, texts)
    issues = set(Issue.objects.filter(edition=Edition.GENERAL_AR, number__in={c.issue for c in changes if c.issue})
                 .values_list('number', 'suffix'))
    out = []
    for c in changes:
        t, by = texts.get(c.text_uri), texts.get(c.by_uri)
        if t is None:               # removed between the page's queries
            continue
        path = text_path(c.text_uri)
        key = (f'{c.issue}-bis' if c.issue_bis else str(c.issue)) if c.issue else ''
        held = (c.issue, 'bis' if c.issue_bis else '') in issues
        out.append({
            'id': path, 'url': site(path), 'title': t.title_ar, 'type': t.type, 'article': c.number or None,
            'article_id': articles.get((c.text_uri, c.number)), 'how': c.verb, 'on': c.published_on.isoformat(),
            'effective_on': c.effective_on.isoformat() if c.effective_on else None,
            'by': {'id': text_path(by.akn_uri) if by else None, 'title': by.title_ar if by else None,
                   'kind': c.by_kind, 'number': c.by_number, 'article': c.by_article or None},
            'published_in': _issue(Edition.GENERAL_AR, key, c.published_on, c.page, held),
        })
    return out


def since(raw_since, raw_cursor='') -> dict:
    """The page of changes since `raw_since` (YYYY-MM-DD) that follows `raw_cursor` (a page's `next`), or the first.
    `Refused` (`since`, `required` | `invalid` | `too_far`) or (`cursor`, `invalid`)."""
    day, after = _since(raw_since), _cursor(raw_cursor)
    texts, changes = _published(day, after), _amended(day, after)
    feed = sorted([(t.first_published_in.date, PUBLISHED, t.pk, t) for t in texts] +
                  [(c.published_on, AMENDED, c.pk, c) for c in changes],
                  key=lambda item: (-item[0].toordinal(), RANK[item[1]], -item[2]))
    page = feed[:PAGE]
    last = page[-1] if len(feed) > PAGE else None
    return {'since': day.isoformat(),
            'published': [_text_item(row) for _, kind, _, row in page if kind == PUBLISHED],
            'amended': _change_items([row for _, kind, _, row in page if kind == AMENDED]),
            'next': f'{last[0].isoformat()}.{last[1]}.{last[2]}' if last else None}
