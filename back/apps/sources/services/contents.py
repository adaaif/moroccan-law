"""What an issue says it holds: its own table of contents («فهرست»), as its first page prints it (W9 of
the library-search review, 10 Nov 2026). An issue kept by its pages alone (a report, a table of sworn experts) opened on a grid of grey
cells and no word of what it is; the Bulletin says it itself, and that is what is shown: no sentence of ours."""
import re

_OPENS = re.compile(r'فهرست|فهرس')
_ENTRY = re.compile(r'^(.*?\S)\s*\.{4,}\s*(\d{1,5})\s*$')
_NOISE = re.compile(r'^(?:صفحة|الصفحة|\|.*\||[-|\s.]*)$')
MOST = 12


def contents(first_page: str) -> list[dict]:
    """The contents table's lines: {'kind': 'rubric' | 'heading' | 'entry', 'text', 'page'}; empty when the page prints
    none. A rubric is a short line alone («تقارير»); a heading ends its sentence («المجلس الأعلى … . - تقرير برسم سنة
    2025.»); an entry is led to its page by dots."""
    m = _OPENS.search(first_page or '')
    if not m:
        return []
    out: list[dict] = []
    for raw in first_page[m.end():].splitlines():
        line = ' '.join(raw.split())
        if not line or _NOISE.match(line):
            continue
        entry = _ENTRY.match(line)
        if entry:
            out.append({'kind': 'entry', 'text': entry.group(1), 'page': int(entry.group(2))})
        elif len(line) <= 40 and not line.endswith('.'):
            out.append({'kind': 'rubric', 'text': line, 'page': None})
        else:
            out.append({'kind': 'heading', 'text': line, 'page': None})
        if len(out) >= MOST:
            break
    return out


def about(first_page: str) -> str:
    """One line for an issue kept by its pages: the first heading its contents table prints, else its first entry."""
    lines = contents(first_page)
    for kind in ('heading', 'entry'):
        found = next((x['text'] for x in lines if x['kind'] == kind), '')
        if found:
            return found[:200]
    return ''
