"""One Bulletin Officiel issue, end to end on the sources side: register it, read every page, number them."""
import re
from collections import Counter
from datetime import date
from pathlib import Path

from django.db.models import F

from apps.sources.models import Document, DocumentKind, Edition, Issue, OcrRun, Page, PageKind, Source, TextSource
from apps.sources.services import remarks, witness
from apps.sources.services.ingest import ingest_file, letters
from apps.sources.services.ocr import PROMPT_VERSION, readings_in_parts
from apps.sources.services.render import is_sideways, render_columns



def register(path: Path, *, edition: str, number: int, day: date, url: str = '', suffix: str = '') -> Issue:
    french = edition == Edition.TRANSLATION_FR
    printed = f'{number} {("bis" if french else "مكرر") if suffix == "bis" else suffix}'.strip()
    doc = ingest_file(path, source=Source.SGG_BO, kind=DocumentKind.BO_ISSUE, language='fr' if french else 'ar',
                      url=url, title=f'Bulletin officiel n° {printed}' if french else f'الجريدة الرسمية عدد {printed}',
                      issue={'edition': edition, 'number': number, 'suffix': suffix, 'date': day.isoformat()})
    return doc.issue


# The layer's words are often garbled (letters reversed, visual order), but it still holds every letter of a
# text page: a reading with far fewer letters has skipped something.
# A table page's layer is no measure of letters: it also carries the rows clipped off the page (the next page's
# part of the table). Its amounts are: every amount printed is in the layer, so the share of amounts read that
# the layer holds says how well the digits were read.
AMOUNT = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}')                    # «38.562,85»
GROUPED = re.compile(r'(?<![\d.,])\d{1,3}(?:[ .]\d{1,3})+(?![\d,])')  # «421 325 037 000», «421.325.037.000»
TABLE_AMOUNTS = 20


def _amounts(text: str, *, layer: bool = False) -> list[str]:
    """Every amount as its digits. Grouped integers count only when their groups are well formed; the text layer
    prints them in visual order, groups reversed («000 037 325 421» for 421 325 037 000), so for the layer both
    readings are kept."""
    out = [re.sub(r'\D', '', m) for m in AMOUNT.findall(text)]
    for m in GROUPED.findall(text):
        groups = re.split(r'[ .]', m)
        if all(len(g) == 3 for g in groups[1:]):
            out.append(''.join(groups))
        if layer and all(len(g) == 3 for g in groups[:-1]):
            out.append(''.join(reversed(groups)))
    return out


def coverage(page: Page, text: str) -> float | None:
    """Letters read / letters in the text layer, counted alike; None for a page without a usable layer (a scan)."""
    if page.layer_letters < 200:
        return None
    return letters(text, page.document.language) / page.layer_letters


def amounts(page: Page, text: str) -> tuple[int, int] | None:
    """(amounts read, of which in the layer) on a table page; None on any other page."""
    layer = set(_amounts(page.layer_text, layer=True))
    if len(layer) < TABLE_AMOUNTS:
        return None
    read = _amounts(text)
    return len(read), sum(a in layer for a in read)


# Lines the model wrote about the page rather than from it («الجزء الأيمن (القراءة من اليمين):»).
_NOTE = re.compile(r'^\W*(?:الجزء|العمود) (?:الأيمن|الأيسر)\b.*$|^\W*\[الصفحة التالية.*$|^\W*\(القراءة من .*$', re.M)
# A word with Arabic and Latin letters run together is a misreading («المبارmay» for «المباراة»).
_MIXED = re.compile(r'\S*(?:[\u0621-\u064A][A-Za-z]|[A-Za-z][\u0621-\u064A])\S*')


# A model sometimes copies an amount's groups in visual order: «000 715 233 166» for 166 233 715 000, the minus
# trailing («000 971 254 1-»). No amount starts with a «000» group or ends with a short one, so such a figure can
# only be read one way. Law numbers («103.12») use dots and are never touched.
_SPACED = re.compile(r'(?<![\d.,])(\d{1,3}(?: \d{1,3})+)(\s?[-–])?(?![\d,])')


def _unreverse(match: re.Match) -> str:
    """The one short group goes first, then the three-digit groups in reverse order: «000 971 254 1» →
    1 254 971 000, «000 715 233 166» → 166 233 715 000, «000 3 000» → 3 000 000 (reversing alone gives
    that one back). Two short groups: not a figure this can mend, left as written."""
    groups = match.group(1).split(' ')
    if all(len(g) == 3 for g in groups[1:]) and groups[0] != '000':
        return match.group(0)
    short = [g for g in groups if len(g) < 3]
    if len(short) > 1:
        return match.group(0)
    full = [g for g in groups if len(g) == 3]
    return ('-' if match.group(2) else '') + ' '.join(short + full[::-1])


def clean_reading(text: str) -> str:
    """A reading as shown and parsed: the model's own notes out (`remarks`: its remarks on method, its retries with
    the failed attempt, «[…]» where it says words were not read), reversed amounts put the right way round. The run
    keeps the reading as the model wrote it."""
    return re.sub(r'\n{3,}', '\n\n', _SPACED.sub(_unreverse, _NOTE.sub('', remarks.strip(text)))).strip()


def reading_check(page: Page, text: str) -> dict | None:
    """What the page's own layer confirms of a reading, and the words that look misread, for the page viewer."""
    check = {}
    if (found := amounts(page, text)) is not None:
        check = {'amounts_read': found[0], 'amounts_in_layer': found[1]}
    elif (share := coverage(page, text)) is not None:
        check = {'letters': round(share, 2)}
    if page.document.language == 'ar' and (suspect := _MIXED.findall(text)):
        check['suspect'] = suspect[:10]
    return check or None


def ocr_issue(issue: Issue, model: str, log=print, first: int | None = None) -> None:
    """Every page read by `model`; a sideways page also read turned upright and a two-column page column by column
    (read whole, a model may take the left column first, or drop one), all in one batch; each page keeps its best
    reading. A page with no reading yet sends its columns too: whether it is a table (whose rows a cut would part)
    is known only from its reading, and `best_run` then sets the column reading aside. `first` reads only the issue's
    first pages, its cover and contents (A8 of the consumer plan: a sweep of what was published); a later run reads
    the rest, the pages read already kept."""
    pages = list(issue.document.pages.order_by('index'))
    if first:
        pages = pages[:first]
    if issue.document.language == 'fr':
        # The translation edition's born-digital pages keep their layer (its Latin letters come out whole); only
        # its scans are read.
        pages = [p for p in pages if p.kind != PageKind.TEXT_LAYER]
        if not pages:
            return
    todo = [p for p in pages
            if not OcrRun.objects.filter(page=p, engine=model, prompt_version=PROMPT_VERSION).exists()]
    sideways = [p for p in pages if p.layer_letters >= 200 and is_sideways(p)
                and not p.ocr_runs.filter(engine=model, variant__startswith='turned').exists()]
    if sideways:
        log(f'{len(sideways)} sideways pages, read again turned upright: ' + ', '.join(str(p.index) for p in sideways))
    split = [p for p in pages if not p.ocr_runs.filter(engine=model, variant__startswith='columns').exists()
             and not _is_table(p, model) and render_columns(p)]
    if split:
        log(f'{len(split)} two-column pages, read again column by column')
    readings_in_parts(todo, sideways, split, model, log=log)     # in parts when the budget holds no more at once
    keep_best(pages, model)


def keep_best(pages: list[Page], model: str) -> list[Page]:
    """Each page's text from its best reading; the pages whose text changed."""
    from apps.quality.services.corrections import reapply_pages
    changed = []
    for page in pages:
        run = best_run(page, model)
        if not (run and run.text):
            continue
        old, page.text = page.text, clean_reading(run.text)
        reapply_pages([page])           # a word read against the page's image stays put right (FX2)
        if page.text != old:
            page.text_source = TextSource.OCR
            page.save(update_fields=['text', 'text_source'])
            changed.append(page)
    from apps.sources.services.quality import store
    store(changed)
    return changed


def mostly_table(text: str) -> bool:
    """A reading that is mostly a table's rows: cut into columns, its rows would come apart (labels in one
    column, amounts in the other)."""
    lines = [line for line in text.splitlines() if line.strip()]
    return bool(lines) and sum(line.lstrip().startswith('|') for line in lines) / len(lines) >= 0.5


def confirmed(page: Page, text: str) -> bool:
    """The page's own layer vouches for the reading: its letters within 10 %, or 98 % of its amounts. (On a table
    page whose layer carries clipped rows the letters never match, so its amounts decide.)"""
    text = clean_reading(text)
    share = coverage(page, text)
    if share is not None and 0.9 <= share <= 1.1:
        return True
    found = amounts(page, text)
    return found is not None and found[0] > 0 and found[1] / found[0] >= 0.98


def _is_table(page: Page, model: str) -> bool:
    whole = page.ocr_runs.filter(engine=model, variant__startswith='page').first()
    return bool(whole and mostly_table(whole.text))


def best_run(page: Page, model: str) -> OcrRun | None:
    """A sideways page keeps a reading made upright, a two-column page its column reading when the layer
    confirms it (the columns' order then comes from the page, not the model). Then: on a table page the reading
    with the most amounts the layer confirms, on a text page the one closest to the layer, on a scan the newest."""
    voted = page.ocr_runs.filter(engine='vote').exclude(text='').order_by('-created_at').first()
    if voted:
        return voted            # what the readings of a cover and its copies agreed on (FX3 of the mended-Bulletin review)
    # A copy's reading, kept on its cover's page, voted already: it is not a reading of its own to choose.
    runs = [r for r in page.ocr_runs.filter(engine=model) if r.text and not r.variant.startswith('copy ')]
    kept = [r for r in runs if r.variant.startswith('table')]
    if kept:
        return kept[0]          # a table reading kept because it made its table add up (budget repair_tables)
    sideways = is_sideways(page)
    turned = [r for r in runs if r.variant.startswith('turned')] if sideways else []
    runs = [r for r in runs if not r.variant.startswith('turned')]     # an upright page read turned is no reading
    if _is_table(page, model):   # a table page keeps the reading that keeps its rows whole
        runs = [r for r in runs if not r.variant.startswith('columns')]
    columns = [r for r in runs if r.variant.startswith('columns') and confirmed(page, r.text)]
    runs = turned or columns or runs
    if not runs:
        return None
    if amounts(page, runs[0].text) is not None:
        return max(runs, key=lambda r: amounts(page, clean_reading(r.text))[1])
    if page.layer_letters < 200:
        return runs[0]
    return min(runs, key=lambda r: abs(1 - coverage(page, clean_reading(r.text))))


# A page number may be 1 (the year's first issue starts at 1): the vote keeps the offset most pages agree on,
# and the header's other small numbers (the day of the date) give no offset that holds from page to page.
_PAGE_NUMBER = re.compile(r'\b(\d{1,5})\b')


# Before 1956 the year often follows «عام», and the months are spelled the protectorate's way («جمادى الاولى»,
# «ربيع النبوي», «30 قعدة عام 1331»).
HIJRI_MONTH = re.compile(r'(?:محرم|صفر|ربيع الأول|ربيع الآخر|ربيع الثاني|الأولى|الآخرة|جمادى|رجب|شعبان|رمضان|شوال|القعدة|الحجة|'
                         r'الاولى|الاخرة|الثانية|النبوي|الانور|قعدة|حجة)\s*(?:عام\s*)?$')
# A number followed by a month is the day of the date («15 رجب 1442 (27 فبراير 2021)»), one followed by «درهم» the
# price on the back cover; never a page number. A short issue has too few pages for the vote to outweigh them
# (BO 6964 bis, 3 pages: the day «15» won over its page 1692).
_NOT_A_PAGE = re.compile(r'\s*(?:من\s+)?(?:محرم|صفر|ربيع|جمادى|جمادي|قعدة|حجة|رجب|شعبان|رمضان|شوال|ذو|ذي|يناير|فبراير|مارس|أبريل|ابريل|'
                         r'ماي|مايو|مايه|يونيو|يونيه|يوليوز|يوليو|يوليه|غشت|أغسطس|شتنبر|سبتمبر|أكتوبر|اكتوبر|نونبر|نوفمبر|دجنبر|ديسمبر|ينير|يبراير|'
                         r'درهم|دراهم)')


def _mark(entry: dict) -> tuple[str, bool]:
    """What shows a contents entry's text on its page: its number as printed, else a run of its title's words. A law's
    entry may pair its dahir and its own number («1.00.200 / 04.00», «ظهير شريف رقم 1.99.193 / قانون رقم 10.98»): the
    pair is never printed as such, the dahir's number is (31 Oct 2026: BO 4798 and 4726 found none of their laws, kept
    folios 2 and 6 for 1181 and 2268, and lost their 23 laws)."""
    for number in re.findall(r'\d[\d.\-]*\d', entry.get('number_as_printed') or ''):
        if sum(c.isdigit() for c in number) >= 4:
            return number, False
    return witness.folded(' '.join((entry.get('title') or '').split()[2:7])), True


def _by_contents(votes: Counter, pages: list[Page], contents: list[dict], front: int) -> int | None:
    """The offset the issue's contents bear out (Z27 of the second-archive-run review, 29 Oct 2026). The contents print
    the page each text starts on, so an offset that puts them outside the issue is wrong: 141 of the first 1,432
    archive issues were (BO 4231: its cover voted 2255, its folios read 2355, none of its 74 texts was found). Among
    the folios' offsets, the one most voted of those that hold the contents; but once the pages are read, the one
    just before the contents' first page that finds more of their texts' numbers on the very pages they name, when it
    finds half of them (BO 5398: no folio voted 487, and 482 held 28 of its 32 texts and found none; BO 4758: 19 held
    them all and found 2 of 19, 17 finds 19). Never on the `front` pages, the cover and the contents: they print every
    number (BO 3553: 1441 put its first texts there and outscored its 21 folios for 1439)."""
    printed = [e['page'] for e in contents if isinstance(e.get('page'), int) and e['page'] > 0]
    if len(printed) < 3:
        return None
    n = len(pages)

    def holds(offset):
        return sum(1 for p in printed if offset <= p < offset + n) / len(printed)

    best = max((holds(o) for o in votes), default=0)
    voted = max((o for o in votes if holds(o) >= 0.9 * best), key=lambda o: votes[o]) if best >= 0.5 else None
    texts = [(page.text, witness.folded(page.text)) for page in pages]
    marks = [(e['page'], *_mark(e)) for e in contents if isinstance(e.get('page'), int) and e['page'] > 0]
    marks = [(p, m, words) for p, m, words in marks if len(m) >= (12 if words else 4)]

    def found(offset):         # on the very page: a page's leeway let 4174 outscore BO 6357's 67 folios for 4173
        return sum(1 for p, m, words in marks if front <= p - offset < n and m in texts[p - offset][words])

    offset = max(range(max(1, min(printed) - 9), min(printed) + 1), key=found)
    if marks and found(offset) >= max(3, len(marks) // 2) and (voted is None or found(offset) > found(voted)):
        return offset
    if voted is None and max(printed) - min(printed) < n:
        # No folio puts the contents inside the issue (heads read by columns carry none, Tesseract's voted a day): the
        # scan's offset when it finds a third of the texts on the very pages their contents name (31 Oct 2026: BO 6204
        # bis, 5109 and 3484 list 3 or 4 texts). Fewer, the vote stays: a contents misread wholesale finds one or two by
        # chance (BO 3535 found 1 of 29 at 959 and lost 9 of the 10 texts its folios 3525 had found).
        return offset if marks and found(offset) >= max(1, len(marks) // 3) else None
    return voted


def number_pages(issue: Issue, contents: list[dict] | None = None) -> int | None:
    """Printed page numbers run on through the year. Read each page's running header, take the offset most
    pages agree on (printed = index + offset), and write it to every page. Returns the offset. With the issue's
    contents (the archive's toc.json), the offset is one they bear out (`_by_contents`)."""
    doc: Document = issue.document
    votes = Counter()
    skip = {str(issue.number), str(issue.date.year)}
    pages = list(doc.pages.order_by('index'))
    for page in pages:
        head = (page.text or page.layer_text).strip().splitlines()[:2]
        if (seen := witness.of(page)) is not None:
            head += witness.head_lines(seen)   # a scan read by columns: its folio is in Tesseract's head lines only
        for line in head:
            for m in _PAGE_NUMBER.finditer(line):
                n = m.group(1)
                # The issue number, the year, and the Hijri year where it stands after its month («19 شعبان 1445»).
                # Not every 14xx: in February the pages themselves run 1398, 1399, 1400 … (BO 7278, 7279, 7381).
                if (n in skip or HIJRI_MONTH.search(line[max(0, m.start() - 14):m.start()])
                        or _NOT_A_PAGE.match(line, m.end())):
                    continue
                if int(n) - page.index < 1:      # the first page is printed 1 at the least: a day read as a folio
                    continue
                votes[int(n) - page.index] += 1
    offset = _by_contents(votes, pages, contents, witness.contents_pages(doc)) if contents else None
    if offset is None and not votes:
        # No folio read (old readings rarely keep the running head): the year runs on from the issue before, rather
        # than a mid-year issue left at page 1 (FX4 of the mended-Bulletin review: BO 73's page 407 showed as 3).
        from apps.sources.services.pages import neighbour_start
        offset = neighbour_start(issue)
        if offset is None:
            return None
    offset = offset if offset is not None else votes.most_common(1)[0][0]
    doc.pages.update(printed_number=F('index') + offset)
    issue.first_page_number = offset
    issue.save(update_fields=['first_page_number'])
    return offset


def page_by_printed(issue: Issue, printed: int) -> Page | None:
    return issue.document.pages.filter(printed_number=printed).first()
