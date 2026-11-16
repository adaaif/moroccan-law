"""What every tool shares: the refusal the model can act on, the site's addresses, the kept answers a text is read
from (its head, a run of its articles, its articles' addresses), and the facts said the same way everywhere: a law, its
publication, its version, an article with its changes, standing and official French."""
import json
import re
from datetime import date
from urllib.parse import urlsplit

from django.conf import settings

from apps.consolidation.services import history
from apps.corpus.models import Status, Text, TextType
from apps.corpus.services import generation
from apps.corpus.services.addresses import split_path
from apps.corpus.services.works import text_at

LONG_ARTICLE = 12000          # characters: a longer article (a finance law's table) is cut, with where to continue

STATUS = {Status.IN_FORCE: 'in force', Status.PARTLY_REPEALED: 'partly repealed', Status.REPEALED: 'repealed',
          Status.NOT_YET_IN_FORCE: 'not yet in force', Status.UNKNOWN: 'status not established'}
OFFICIAL_VERSIONS = {'as_published'}
ISSUE_ID = re.compile(r'^/?bo/(?:(general_ar|translation_fr|conventions_ar|conventions_fr)/)?(\d{1,5})(?:[-_ ]?(bis|ter))?/?$',
                      re.I)


class Problem(Exception):
    """A refusal the model can act on: what is wrong and what to do instead (MC15). `code` names it for a program, as
    `<field>.<reason>` (`id.not_found`, `on.invalid`): the versioned API (apps/opendata/v1) answers it in the site's
    error shape, never by reading the sentence. The assistants are given the sentence alone."""

    def __init__(self, message: str = '', *, code: str | None = None):
        super().__init__(message)
        self.code = code


# ── Addresses ────────────────────────────────────────────────────────────────

def site(path: str) -> str:
    return settings.SITE_URL.rstrip('/') + path


def address(raw: str) -> str:
    """An id as search gives it, a link to the site (3adala.com, or any older address: only the path is read), or the
    path alone:
    «/ma/loi/65-99/art_51», «bo/7533»."""
    raw = (raw or '').strip()
    if raw.startswith(('http://', 'https://')):
        try:
            raw = urlsplit(raw).path
        except ValueError:          # a link that cannot be read («https://[»): refused as any other wrong address
            raise Problem(f'«{raw[:80]}» is not a link to read. Use an id from search, such as /ma/loi/65-99/art_51.',
                          code='id.invalid') from None
    raw = raw.split('#')[0].split('?')[0].rstrip('/')
    if raw.startswith(('ma/', 'bo/')):
        raw = '/' + raw
    return raw


def _json(response) -> dict:
    return json.loads(response.content)


def _text_or_problem(path: str) -> tuple[Text, str, str]:
    """The text an address names, the address it has now, and the article's eid ('' for the text)."""
    if not path.startswith('/ma/'):
        raise Problem(f'«{path}» is not a {settings.SITE_NAME} address. Use an id from search, such as /ma/loi/65-99/art_51.',
                      code='id.invalid')
    uri, eid = split_path(path)
    text, now = text_at(uri)
    if text is None:
        raise Problem(f'No text at {path}. Search for it by its name or number with the search tool.',
                      code='id.not_found')
    return text, now, eid


def _head(text: Text, uri: str, on: date | None = None) -> dict:
    """The text's facts, its first article only (kept like the site's window of one)."""
    from apps.corpus.api.views import text_payload
    return _json(generation.answer(['at', uri, '', on, 1, None], lambda: text_payload(text, on=on, window=1)))


def _run(text: Text, uri: str, start: int, end: int, on: date | None = None) -> dict:
    from apps.corpus.api.views import text_payload
    span = (start, end)
    return _json(generation.answer(['at', uri, '', on, None, span], lambda: text_payload(text, on=on, span=span)))


def _eids(text: Text, on: date | None = None) -> list[str]:
    version, _ = history.pick_version(text, on)
    if version is None:
        return []
    return generation.kept(['eids', version.pk], lambda: list(version.articles.order_by('order').values_list('eid', flat=True)))


# ── Facts said the same way everywhere ───────────────────────────────────────

def _law(head: dict) -> dict:
    name = head.get('name') or {}
    out = {'id': head['path'], 'title': head.get('title') or '', 'name_ar': name.get('ar') or '',
           'name_fr': name.get('fr') or '', 'number': head.get('number_as_printed') or '', 'type': head.get('type'),
           'status': STATUS.get(head.get('status'), head.get('status')), 'url': site(head['path'])}
    if head.get('type') == TextType.BILL:
        out['status'] = 'a bill filed in Parliament: not law'
    return out


def _published(head: dict) -> dict | None:
    issue = head.get('issue')
    if not issue:
        return None
    return {'bo': issue['key'], 'date': issue.get('date'), 'page': head.get('page'),
            'url': site(f"/bo/{issue['edition']}/{issue['key']}")}


def _version(head: dict) -> dict | None:
    v = head.get('version')
    if not v:
        return None
    official = v['consolidation'] in OFFICIAL_VERSIONS
    out = {'in_force_since': v['valid_from'], 'kind': v['consolidation'], 'source': v['consolidation_label'],
           'official': official}
    if not official:
        out['note'] = ('Consolidated text: unofficial, for information. The Bulletin officiel prevails; the changes '
                       'listed give the amending BO issues.')
    if v.get('translated_from'):
        out['note'] = ('Arabic translated by AI from the official French translation: not the official text. '
                       'The Bulletin officiel prevails.')
    if (v.get('source') or {}).get('as_of'):
        out['as_of'] = v['source']['as_of']
    return out


def _changes(article: dict) -> list[dict]:
    out = []
    for c in article.get('changes') or []:
        if c.get('state') and c['state'] not in history.SHOWN_AS_FACT:
            continue
        by = c.get('by') or {}
        issue = c.get('issue') or {}
        out.append({'on': c.get('effective_on') or c.get('on'), 'how': c.get('verb'),
                    'by': by.get('title') or f"{by.get('kind', '')} {by.get('number', '')}".strip(),
                    'by_id': by.get('path'),
                    'bo': f"{issue.get('number')}{'-bis' if issue.get('bis') else ''}" if issue.get('number') else None,
                    'page': issue.get('page')})
    return out


def _article_status(article: dict, law_status: str) -> str:
    last = (article.get('changes') or [])[-1:] or [{}]
    if last[0].get('verb') == 'repealed':
        return 'repealed'
    return law_status


def _french(article: dict, head: dict) -> dict | None:
    fr = article.get('french')
    if not fr:
        return None
    src = head.get('french') or {}
    out = {'label': fr['label'], 'text': fr['body'],
           'source': f"Official French translation, BO {src.get('issue_number', '')}{('-' + src['issue_suffix']) if src.get('issue_suffix') else ''}"
                     f" ({src.get('issue_date', '')})".strip()}
    if fr.get('older'):
        out['note'] = 'The Arabic changed after this French was printed: the Arabic is the text in force.'
    return out


def _cut(body: str) -> tuple[str, bool]:
    if len(body) <= LONG_ARTICLE:
        return body, False
    return body[:LONG_ARTICLE].rsplit(' ', 1)[0] + ' …', True


def _article_item(article: dict, head: dict, law: dict, *, french: bool = True) -> dict:
    body, cut = _cut(article['body'])
    item = {'id': article['path'], 'label': article['label'], 'text': body,
            'title': f"{article['label']} — {law['name_ar'] or law['title']}",
            'url': site(article['path']), 'status': _article_status(article, law['status']),
            'heading': ' › '.join(article.get('heading_path') or []), 'citation': article.get('citation') or '',
            'changes': _changes(article)}
    if cut:
        item['cut'] = (f'This article is {len(article["body"])} characters; the first {LONG_ARTICLE} are given. '
                       f'Its whole text is at {item["url"]}.')
    if french:
        item['french'] = _french(article, head)
    return item
