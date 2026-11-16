"""`get_bulletin`: one issue of the Bulletin officiel with the texts the site holds from it, or the last week's issues,
as text for the model and as data."""
from datetime import date

from django.conf import settings
from django.http import Http404

from apps.corpus.services import generation
from apps.mcp.services.law.common import ISSUE_ID, Problem, _json, address, site

BULLETIN_TEXTS = 40        # texts get_bulletin lists for a week; one issue lists all of its own


def _issue_ref(issue: dict, texts: list[dict]) -> dict:
    return {'key': issue['key'], 'edition': issue['edition'], 'date': issue['date'],
            'url': site(f"/bo/{issue['edition']}/{issue['key']}"), 'count': len(texts),
            'texts': [{'id': t['path'], 'kind': t.get('type_label') or t['type'], 'title': t['title'],
                       'page': t.get('page')} for t in texts]}


def bulletin(issue: str = '') -> dict:
    from apps.corpus.api.views import IssueDetail, IssueList

    def detail(edition, key):
        try:
            return _json(generation.answer(['issue', edition, key], lambda: IssueDetail.issue(edition, key)))
        except Http404:
            raise Problem(f'No issue {key} in the Bulletin officiel ({edition}) that {settings.SITE_NAME} holds.',
                          code='issue.not_found') from None

    if issue:
        m = ISSUE_ID.match(address(issue) if address(issue).startswith('/bo') else '/bo/' + issue.strip().lower())
        if not m:
            raise Problem(f'«{issue}» is not an issue number: give it as 7533 or 7533-bis.', code='issue.invalid')
        edition, number, suffix = m.group(1) or 'general_ar', m.group(2), (m.group(3) or '').lower()
        d = detail(edition, f'{number}-{suffix}' if suffix else number)
        return {'issues': [_issue_ref(d, d['texts'])]}
    issues = [i for i in _json(generation.answer(['issues'], IssueList.issues)) if i['edition'] == 'general_ar']
    if not issues:
        raise Problem(f'{settings.SITE_NAME} holds no issue of the Bulletin officiel yet.', code='issue.not_found')
    newest = date.fromisoformat(issues[0]['date'])
    week = [i for i in issues if (newest - date.fromisoformat(i['date'])).days < 7][:6]
    out, room = [], BULLETIN_TEXTS
    for d in (detail(i['edition'], i['key']) for i in week):
        ref = _issue_ref(d, d['texts'][:max(room, 0)])
        ref['count'] = len(d['texts'])
        room -= len(ref['texts'])
        out.append(ref)
    return {'issues': out}


def bulletin_text(data: dict) -> str:
    lines = []
    for i in data['issues']:
        lines.append(f"Bulletin officiel {i['key']} ({i['edition']}), {i['date']}: {i['count']} texts — {i['url']}")
        for t in i['texts']:
            lines.append(f"  • {t['kind']}: {t['title']} (p. {t['page']}) — {site(t['id'])}")
        if len(i['texts']) < i['count']:
            lines.append(f"  … {i['count'] - len(i['texts'])} more: get_bulletin with issue {i['key']} lists them all.")
        lines.append('')
    return '\n'.join(lines).strip()


def bulletin_data(data: dict) -> dict:
    """The structured side without the titles the text already gives (MC15: the words once)."""
    return {'issues': [{**{k: v for k, v in i.items() if k != 'texts'},
                        'texts': [{'id': t['id'], 'kind': t['kind'], 'page': t['page']} for t in i['texts']]}
                       for i in data['issues']]}
