"""`check_references`: each reference a model gives, read as Moroccan law and resolved, with what it is, its text's
standing and its changes since a day."""
from datetime import date

from django.conf import settings

from apps.mcp.services.law.common import STATUS, Problem, site

MAX_REFERENCES = 50
STATES = {'found': 'found', 'text_only': 'the text is found; that article is not in its current version',
          'not_in_corpus': f'a known text {settings.SITE_NAME} does not hold yet', 'repealed': 'found, and repealed',
          'issue': 'a Bulletin officiel issue', 'unknown': 'not recognised as Moroccan law'}


def check_references(references: list[str], since: str = '') -> tuple[str, dict]:
    import ma_law

    from apps.corpus.services.citations import resolve_many

    if not isinstance(references, list) or not references:
        raise Problem('Give the references as a list of short strings, e.g. ["المادة 52 من مدونة الأسرة"].',
                      code='references.required' if isinstance(references, list) else 'references.invalid')
    if len(references) > MAX_REFERENCES:
        raise Problem(f'At most {MAX_REFERENCES} references at once.', code='references.too_many')
    day = None
    if since:
        try:
            day = date.fromisoformat(since)
        except ValueError:
            raise Problem(f'«{since}» is not a date: give it as YYYY-MM-DD.', code='since.invalid') from None
    out, lines = [], []
    read = [(str(ref)[:200], cites[:5]) for ref in references
            for cites in [list(ma_law.parse_citations(str(ref)[:200])) or
                          list(ma_law.parse_query(str(ref)[:200]))]]
    # Every citation of every reference resolved at once, each as `resolve` answers it alone: a fixed number of
    # queries for fifty references (one `resolve` a citation before, about nine queries each).
    answers = iter(resolve_many([c for _, cites in read for c in cites], checker=True, since=day))
    for ref, cites in read:
        if not cites:
            out.append({'reference': ref, 'found': []})
            lines.append(f'«{ref}»: not read as a reference to a Moroccan text. Try search.')
            continue
        found = []
        for _ in cites:
            r = next(answers)
            t, a = r.get('text') or {}, r.get('article') or {}
            path = a.get('path') or t.get('path')
            item = {'state': r['state'], 'meaning': STATES.get(r['state'], r['state']),
                    'text': t.get('title'), 'name': (r.get('name') or t.get('name') or {}).get('ar'),
                    'article': a.get('label'), 'id': path, 'url': site(path) if path else None,
                    'status': STATUS.get(t.get('status'), t.get('status')) if t else None,
                    'changed_since': [{'how': ch['action'], 'article': ch['label'] or None, 'published': ch['published'],
                                       'bo': ch['issue'], 'by': (ch.get('by') or {}).get('title')}
                                      for ch in r.get('changes') or []] if day else None}
            if r.get('issue'):
                item['url'] = site(r['issue']['path'])
            if r.get('official'):
                item['official_source'] = r['official']
            found.append(item)
            said = f"«{ref}» → {item['meaning']}"
            if item['text']:
                said += f": {item['article'] + ' — ' if item['article'] else ''}{item['name'] or item['text']}"
                said += f" ({item['status']})" if item['status'] else ''
            if item['url']:
                said += f" {item['url']}"
            if day and item['changed_since']:
                said += f"; changed {len(item['changed_since'])} time(s) after {day}"
            lines.append(said)
        out.append({'reference': ref, 'found': found})
    return '\n'.join(lines), {'since': str(day) if day else None, 'references': out}
