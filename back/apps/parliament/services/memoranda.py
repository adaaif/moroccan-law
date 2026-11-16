"""The explanatory memorandum read out of a bill as filed («النص كما أودع بمكتب المجلس»): the government's
«مذكرة تقديمية» comes first, the bill's own text after it. The bill is a scan; its first pages are read by the
same OCR as the BO, and the memorandum is the stretch from its heading to the bill's heading."""
import re

SITE = 'https://www.chambredesrepresentants.ma'
HEAD = re.compile(r'^\W*(?:ال)?مذكرة\s+(?:ال)?تقديمية|^\W*(?:ال)?مذكرة\s+(?:ال)?تقديم\b')
# Where the bill's own text begins: its title as a heading, or its first article or division.
BILL = re.compile(r'^\W*(?:مشروع\s+(?:ال)?قانون(?:\s+(?:ال)?تنظيمي)?\s+رقم|المادة\s+(?:الأولى|1)\b|الباب\s+الأول\b|القسم\s+الأول\b'
                  r'|الجزء\s+الأول\b|الفصل\s+(?:الأول|1)\b)')


def search_urls(printed: str, title: str) -> list[str]:
    """The Chamber's search, asked for the bill's number, then its number and subject, then the next page."""
    from urllib.parse import quote_plus
    subject = ' '.join(re.split(rf'{re.escape(printed)}', title, maxsplit=1)[-1].split()[:6])
    first = f'{SITE}/ar/search?keys={quote_plus(f"مشروع قانون رقم {printed}")}'
    return [first, f'{SITE}/ar/search?keys={quote_plus(f"مشروع قانون رقم {printed} {subject}")}', f'{first}&page=1']


def bill_page(search_html: str, printed: str) -> str | None:
    """The bill's own page among the search results: the one under «النصوص-التشريعية» titled with its number."""
    from html import unescape
    from urllib.parse import unquote
    for href, label in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', search_html, re.S):
        words = re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', '', label)))
        if 'النصوص-التشريعية' in unquote(href) and re.search(rf'(?:مشروع|مقترح) قانون(?: تنظيمي)? رقم {re.escape(printed)}(?!\d)', words):
            return href if href.startswith('http') else SITE + href
    return None


def bill_file(page_html: str) -> str | None:
    """The bill as filed among the page's files: not the committee's report."""
    for href in re.findall(r'href="(/sites/default/files/loi/[^"]+\.pdf)"', page_html, re.I):
        if not re.search(r'rapport|تقرير', href, re.I):
            return SITE + href
    return None


def names_bill(pages: list[str], printed: str) -> bool:
    """The file is the bill it was fetched for: its pages print its number (the Chamber's file names have typos —
    bill 59.24's page links «Projet_ loi_59.25.pdf»)."""
    digits = re.sub(r'\D', '', printed)
    flat = re.sub(r'[^\d]', ' ', ' '.join(pages).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
    return any(re.sub(r'\s', '', m) == digits for m in re.findall(r'\d+\s\d+', flat))


def memorandum(pages: list[str]) -> tuple[str, bool]:
    """(the memorandum, whether its end was found) from the pages' texts in order; ('', False) if it has none."""
    lines = [ln.strip() for page in pages for ln in page.splitlines()]
    start = next((i for i, ln in enumerate(lines) if HEAD.match(ln) and len(ln) < 60), None)
    if start is None:
        return '', False
    out = []
    for ln in lines[start + 1:]:
        if BILL.match(ln) and len(ln) < 160:
            return '\n'.join(_paragraphs(out)), True
        out.append(ln)
    return '\n'.join(_paragraphs(out)), False


def _paragraphs(lines: list[str]) -> list[str]:
    """Running headers and page numbers out; what is left kept as the OCR gave it, one paragraph a line."""
    keep = []
    for ln in lines:
        if not ln or re.fullmatch(r'[\d\s\-–/]+', ln) or ln.startswith('|'):
            continue
        keep.append(ln)
    return keep
