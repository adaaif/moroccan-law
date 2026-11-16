"""The contents step: the model reads an issue's table of contents into entries (`read_toc`), by its schema and
instructions, the old Bulletin's forms added for an issue before 1956."""
from apps.corpus.services.llm import request, run_batch
from apps.sources.models import Issue


TYPES = ['dahir', 'law', 'organic_law', 'decree_law', 'decree', 'order', 'decision', 'circular', 'convention', 'other']
TOC_PAGES = 8          # the table of contents sits on the first pages of an issue
MAX_PAGES_PER_TEXT = 30

TOC_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['entries'],
    'properties': {'entries': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False,
        'required': ['section', 'rubric', 'type', 'number_as_printed', 'title', 'signed_on_gregorian',
                     'signed_on_hijri', 'page'],
        'properties': {
            'section': {'type': 'string', 'enum': ['general', 'special', 'other']},
            'rubric': {'type': 'string', 'description': 'the subject heading above the entry, or empty'},
            'type': {'type': 'string', 'enum': TYPES},
            'number_as_printed': {'type': 'string'},
            'title': {'type': 'string', 'description': 'the whole entry as printed, without the dots and page'},
            'signed_on_gregorian': {'type': 'string', 'description': 'YYYY-MM-DD or empty'},
            'signed_on_hijri': {'type': 'string'},
            'page': {'type': 'integer', 'description': 'the printed page number of the entry'},
        }}}},
}

TOC_SYSTEM = (
    'You read the first pages of an issue of the Moroccan Bulletin Officiel and return its table of contents '
    '(«فهرست»): every entry, in order, with the section it is under (نصوص عامة = general, نصوص خاصة = special), '
    'the subject heading above it, the type and number of the text, its full title as printed, its dates and '
    'the printed page where it starts. A promulgating dahir and the law it promulgates are one entry, typed '
    '«law». Stop at the end of the table of contents. Use only what is printed.'
)
# The Bulletin before 1956 (the Bulletin-from-No.-1 review, 1 Nov 2026): its contents (a «فهرست», or a box on the first
# page) are in two parts, and its texts have kinds and dates of their own. Mapped onto the sections the archive's
# steps read in order (archive.kind_of): the dahirs first, then the orders, then the decisions, the notices last.
OLD_TOC = (
    ' This issue is from before 1956. Its contents list «القسم الرسمي» (the official part) and «القسم الغير الرسمي» '
    '(the non-official part). In the official part: a dahir («ظهير شريف») is type dahir, section general; an order of '
    'the Grand Vizier («قرار وزيري», «قرار من الصدر الأعظم»), of the Resident General or his delegate («قرار مقيمي», '
    '«قرار للمقيم العام», «قرار من نائب المقيم العام») or of a director («قرار لمدير …») is type order, section '
    'special; an individual decision, an appointment, a promotion, a list of names or results is type decision, '
    'section special; any other text of the official part is section special. Every entry of the non-official part '
    '(land registration requests «مطالب التسجيل», notices of surveys «إعلانات بانتهاء التحديد», companies, '
    'announcements «إعلانات متفرقة») is type other, section other. Most texts of this time have no number: leave '
    'number_as_printed empty, never make one up. Dates are printed Hijri first, then «الموافق» and the Gregorian day '
    '(«الصادر في 9 رمضان 1331 الموافق 12 غشت 1913»): give both. When the issue has no contents, list the texts whose '
    'headings these pages print, in order.'
)


def _before_1956(issue) -> bool:
    day = getattr(issue, 'date', None)
    return bool(day) and day.year < 1956


def toc_system(issue) -> str:
    """The contents step's instructions for an issue: the old Bulletin's forms added for one before 1956."""
    return TOC_SYSTEM + (OLD_TOC if _before_1956(issue) else '')


def read_toc(issue: Issue, model: str, log=print, halves: bool = False) -> list[dict]:
    """A contents too long for one answer is read in two halves, by the printed page its entries give: each
    half sees every contents page, so no entry is cut at a page break. BO 7155's contents fill six pages; read
    whole, the answer stopped at 48,818 characters. `halves` skips the whole reading."""
    pages = list(issue.document.pages.order_by('index')[:TOC_PAGES])
    content = '\n\n'.join(f'=== الصفحة {p.printed_number or p.index + 1} ===\n{p.text}' for p in pages)
    if not halves:
        req = request(f'toc-{issue.number}', model=model, system=toc_system(issue), content=content, schema=TOC_SCHEMA,
                      max_tokens=32000)   # a big issue lists a hundred texts (16,000 cut BO 7547's contents short)
        result = run_batch(f'toc:{issue.number}', [req], log=log)[req['custom_id']]
        if result['data']:
            return result['data']['entries']
        if result['stop'] != 'max_tokens':
            raise RuntimeError(f'table of contents not read: {result["error"] or result["stop"]}')
        log('table of contents cut: read again in two halves')
    first = pages[0].printed_number or 1
    middle = first + issue.document.page_count // 2
    reqs = [request(f'toc-{issue.number}-{n}', model=model, content=content, schema=TOC_SCHEMA, max_tokens=32000,
                    system=f'{toc_system(issue)} Return only the entries whose page is {words}.')
            for n, words in enumerate([f'before {middle}', f'{middle} or after'])]
    results = run_batch(f'toc:{issue.number}', reqs, log=log)
    entries = []
    for req, keep in zip(reqs, [lambda page: page < middle, lambda page: page >= middle]):
        result = results[req['custom_id']]
        if not result['data']:
            raise RuntimeError(f'table of contents not read: {result["error"] or result["stop"]}')
        entries += [e for e in result['data']['entries'] if keep(e['page'])]
    return entries
