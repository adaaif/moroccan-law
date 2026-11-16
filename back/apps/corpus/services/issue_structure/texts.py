"""The texts step: each text cut out of the issue by the contents and described, by the model (its schema and
instructions) or by code, for a special text whose day and number code is sure of."""
import re

from apps.corpus.services.issue_structure.articles import split_articles
from apps.corpus.services.issue_structure.printed import _days, normalize_number
from apps.corpus.services.issue_structure.segment import issue_lines, segment_issue
from apps.corpus.services.issue_structure.toc import TYPES, _before_1956
from apps.corpus.services.llm import request, run_batch
from apps.sources.models import Issue


TEXT_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['found', 'type', 'number_as_printed', 'title', 'signed_on_gregorian', 'signed_on_hijri',
                 'authority', 'promulgating_dahir', 'preamble', 'closing', 'signatories', 'cites', 'amends'],
    'properties': {
        'found': {'type': 'boolean'},
        'type': {'type': 'string', 'enum': TYPES},
        'number_as_printed': {'type': 'string'},
        'title': {'type': 'string'},
        'signed_on_gregorian': {'type': 'string', 'description': 'YYYY-MM-DD or empty'},
        'signed_on_hijri': {'type': 'string', 'description': 'as printed'},
        'authority': {'type': 'string', 'description': 'who issued it (the minister, the Head of Government…)'},
        'promulgating_dahir': {'type': 'string', 'description': 'number of the dahir promulgating a law, or empty'},
        'preamble': {'type': 'array', 'items': {'type': 'string'}, 'description': 'each «بناء على …» line'},
        'closing': {'type': 'string', 'description': 'place and date of signature, as printed'},
        'signatories': {'type': 'array', 'items': {'type': 'string'}},
        'cites': {'type': 'array', 'items': {'type': 'string'}, 'description': 'texts cited, as printed'},
        'amends': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['target_text', 'target_article', 'action', 'words'],
            'properties': {'target_text': {'type': 'string'}, 'target_article': {'type': 'string'},
                           'action': {'type': 'string',
                                      'enum': ['modify', 'add', 'repeal', 'renumber', 'replace_words']},
                           'words': {'type': 'string', 'description': 'a few words saying the change'}}}},
    },
}

TEXT_SYSTEM = (
    'You read ONE legal text of the Moroccan Bulletin Officiel and describe it; you never copy its articles. '
    'Give its type, number, title, dates and authority as printed. A law comes with the dahir that promulgates '
    'it: describe the law, with the dahir\'s number in promulgating_dahir, and take the preamble («بناء على …») '
    'and the signatures of the dahir or decree. List every text it cites, and every change it makes to another '
    'text: one entry per article changed, added or repealed, with the target text\'s full name and number. '
    'Use only what is printed. If the text is not there, set found to false.'
)
OLD_TEXT = (
    ' This text is from before 1956. A dahir («ظهير شريف») has no number: leave number_as_printed empty. Its dates are '
    'printed Hijri first, then «الموافق» and the Gregorian day («وحرر بالرباط في 8 جمادى الثانية عام 1352 الموافق 29 '
    'شتنبر سنة 1933»): give the Hijri date as printed and the Gregorian date. An order of the Grand Vizier («قرار '
    'وزيري»), of the Resident General («قرار مقيمي») or of a director is type order; the Resident General\'s «اطلع عليه '
    'وأذن بنشره» and his name go in signatories. A text cited by its date («الظهير الشريف الصادر في 12 غشت 1913») is '
    'listed in cites as printed.'
)


def text_system(issue) -> str:
    """The texts step's instructions for an issue: the old Bulletin's forms added for one before 1956."""
    return TEXT_SYSTEM + (OLD_TEXT if _before_1956(issue) else '')


def extract_texts(issue: Issue, toc: list[dict], model: str, log=print) -> list[dict]:
    requests, out = texts_requests(issue, toc, model, log=log)
    results = run_batch(f'texts:{issue.number}', requests, log=log) if requests else {}
    return texts_answered(out, results)


def texts_requests(issue: Issue, toc: list[dict], model: str, log=print, prefix: str = '',
                   only=None, by_code=None, before: list[dict] | None = None) -> tuple[list, list]:
    """The texts step's requests for an issue (custom ids `<prefix>t<i>`), and its items waiting for the answers. The
    archive run sends several issues' requests in one batch (the Bulletin-to-1956 review). With `only`, an entry it
    refuses is cut from the pages like the others but not described: its item waits, `stop` «later». With `by_code`,
    an entry it takes is described by code (`describe_by_code`, `stop` «code») when code is sure of its day and number,
    by Haiku otherwise (Z19 of the second-archive-run review: code alone agreed with Haiku on kind, number and day for
    79 % of 299 special texts, 90 % of the 83 % it is sure of, some of the rest Haiku's own misses). `before`, the issue's texts from an earlier step: an entry described then keeps its description,
    its text cut again from the pages as they read now (Z17)."""
    lines = issue_lines(issue)
    spans = segment_issue(issue, toc)        # the whole contents: a text's end is where the next one, of any kind, starts
    described = {_entry_key(item['toc']): item for item in before or [] if item.get('data')}
    requests, out = [], []
    for i, (entry, span) in enumerate(zip(toc, spans)):
        kept = described.get(_entry_key(entry))
        if span is not None and kept is None and only is not None and not only(entry) \
                and not (by_code and by_code(entry)):
            out.append({'toc': entry, 'pages': [lines[span[0]][0], lines[span[1] - 1][0]], 'data': None, 'articles': [],
                        'tail': '', 'stop': 'later', 'error': ''})
            continue
        if span is None:
            log(f'  t{i}: not found in the pages: {entry["title"][:80]}')
            out.append({'toc': entry, 'pages': [entry['page'], entry['page']], 'data': None, 'articles': [],
                        'tail': '', 'stop': 'not_found', 'error': 'not_found'})
            continue
        part = lines[span[0]:span[1]]
        cut = split_articles(part)
        item = {'toc': entry, 'pages': [part[0][0], part[-1][0]], 'front': cut['front'],
                'articles': cut['articles'], 'tail': cut['tail'], 'data': None, 'stop': '', 'error': ''}
        coded = describe_by_code(entry, cut['front'], cut['tail']) if kept is None and by_code and by_code(entry) else None
        if kept is not None:
            item.update(data=kept['data'], stop=kept['stop'])
        elif coded and coded['sure']:
            item.update(data=coded, stop='code')
        else:                                # a general text, or a special one code is not sure of: Haiku describes it
            content = '\n'.join(f'[ص {page}] {line}' if n == 0 or part[n - 1][0] != page else line
                                for n, (page, line) in enumerate(part))
            requests.append(request(f'{prefix}t{i}', model=model, system=text_system(issue), content=content,
                                    schema=TEXT_SCHEMA, max_tokens=8000))
            item['id'] = f'{prefix}t{i}'
        out.append(item)
    return requests, out


def _entry_key(entry: dict) -> tuple:
    return entry.get('title', ''), entry.get('page'), entry.get('number_as_printed', '')


def texts_answered(out: list[dict], results: dict) -> list[dict]:
    for item in out:
        if 'id' not in item:
            continue
        res = results.get(item.pop('id'), {'data': None, 'stop': 'missing', 'error': 'missing'})
        item.update(data=res['data'], stop=res['stop'], error=res['error'])
    return out


# A special text described by code (Z19 of the second-archive-run review): its kind, number, title and dates as the
# contents give them, the rest from its own lines as the Bulletin prints them: the issuer on the line under the
# heading («ان وزير المالية ،», «الوزير الأول،»), its visas, the place and date it was signed, the signatures.
_VISA = re.compile(r'^\s*و?(?:بناء على|بمقتضى|بعد الاطلاع|بعد الإطلاع|باقتراح|نظرا|اعتبارا|بعد استطلاع|بعد استشارة|'
                   r'بعد المداولة|بعد دراسة|بعد موافقة|بعد التداول|طبقا)')
_DECIDES = re.compile(r'(?:يقرر|يقرران|يقررون|قرر|رسم|يرسم|يرسمان|أصدرنا أمرنا الشريف|اصدرنا امرنا الشريف)'
                      r'\s*(?:ما يلي|مايلي)?\s*[:.]?\s*$')
_ISSUER = re.compile(r'^\s*(?:إن|ان|أن)?\s*(.{3,120}?)\s*[،,]\s*$')
_SIGNED = re.compile(r'^\s*و?حرر\b|^\s*بالرباط في')
_SIGNATURE = re.compile(r'^\s*(?:الإمضاء|الامضاء)\s*[:：]?\s*(.+?)\s*[.؛]?\s*$')
_BY_TITLE = re.compile(r'^(?:قرار مشترك|قرار|مقرر|مرسوم|ظهير شريف|ظهير)\s+(?:ل|لل)?(.+?)\s+رقم\b')


def describe_by_code(entry: dict, front: str, tail: str) -> dict:
    lines = [line.strip() for line in (front or '').splitlines() if line.strip()]
    authority, preamble = '', []
    for line in lines[1:]:
        if _VISA.match(line):
            preamble.append(line.rstrip(' ؛;،,'))
        elif _DECIDES.search(line) and preamble:
            break
        elif not preamble and not authority and (m := _ISSUER.match(line)) and len(line.split()) <= 14:
            authority = m.group(1)
        elif preamble:
            preamble[-1] = f'{preamble[-1]} {line}'.rstrip(' ؛;،,')    # a visa running on to the next line
    if not authority and (m := _BY_TITLE.match(entry.get('title') or '')):
        authority = m.group(1)
    closing, signatories, role = '', [], ''
    for line in (tail or '').splitlines():
        line = line.strip()
        if not line:
            continue
        if not closing and _SIGNED.match(line):
            closing = line
        elif m := _SIGNATURE.match(line):
            signatories.append(f'{m.group(1)} ({role})' if role else m.group(1))
            role = ''
        elif closing and len(line.split()) <= 10 and 'بالعطف' not in line:
            role = line.rstrip(' ،,:')
    # Sure of its day when the text signs it («وحرر بالرباط في …») or its heading prints the contents' day; sure of
    # its number when its heading prints the contents' number. A text code is not sure of goes to Haiku.
    heading, number = (lines[0] if lines else ''), entry.get('number_as_printed', '')
    signed = (_days(closing) or [''])[0]
    sure_day = bool(signed) or (bool(entry.get('signed_on_gregorian')) and entry['signed_on_gregorian'] in _days(heading))
    sure_number = (normalize_number(number) in {normalize_number(n) for n in re.findall(r'رقم\s+([\d.\-/]+\d)', heading)}
                   if number else 'رقم' not in heading)
    return {'found': True, 'type': entry.get('type') or 'other', 'number_as_printed': number,
            'title': entry.get('title', ''), 'signed_on_gregorian': signed or entry.get('signed_on_gregorian', ''),
            'sure': sure_day and sure_number,
            'signed_on_hijri': entry.get('signed_on_hijri', ''), 'authority': authority, 'promulgating_dahir': '',
            'preamble': preamble, 'closing': closing, 'signatories': signatories, 'cites': [], 'amends': [],
            'by': 'code'}
