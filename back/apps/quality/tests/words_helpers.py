"""Rows and Tesseract pages the word checker's tests share: a made-up TSV laid out as the Bulletin prints (two columns,
right to left), and suspects on a page of an issue."""
from datetime import UTC, date, datetime
from pathlib import Path

from apps.quality.models import Suspect
from apps.sources.models import Document, Issue, Page

HEAD = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext'
SIZE = (1596, 2000)
LETTER, GAP, HEIGHT = 16, 14, 28


def line(text: str, top: int, right: int = 1480, block: int = 1, number: int = 1) -> list[str]:
    """A printed line's words, laid right to left from `right`: one TSV row a word."""
    rows, x = [], right
    for i, word in enumerate(text.split(), start=1):
        width = LETTER * len(word)
        rows.append(f'5\t1\t{block}\t1\t{number}\t{i}\t{x - width}\t{top}\t{width}\t{HEIGHT}\t90\t{word}')
        x -= width + GAP
    return rows


def tsv(*lines: list[str], size=SIZE) -> str:
    return '\n'.join([HEAD, f'1\t1\t0\t0\t0\t0\t0\t0\t{size[0]}\t{size[1]}\t-1\t',
                      *(row for ln in lines for row in ln)]) + '\n'


def page_with(number: int = 1432, index: int = 3, text: str = '', sha: str | None = None) -> Page:
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=sha or f'{number:016d}'.ljust(64, 'a'),
                                  path=f'issues/bo_ar/BO_{number}_ar.pdf', mime='application/pdf', bytes=1,
                                  language='ar', page_count=8, fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    Issue.objects.create(edition='general_ar', number=number, date=date(1940, 4, 5), document=doc, first_page_number=509)
    return Page.objects.create(document=doc, index=index, printed_number=512, kind='scan', text=text)


def suspect(page: Page, word: str, suggestion: str, context: str, signal: str = 'reread', **more) -> Suspect:
    return Suspect.objects.create(page=page, word=word, suggestion=suggestion, context=context, signal=signal, **more)


def placed(page: Page, word: str = 'خيط', suggestion: str = 'حيط', **more) -> Suspect:
    """A suspect placed on its page: a strip of 400 x 120 pixels, the word marked in its middle."""
    place = {'box': [0.5, 0.1, round(0.5 + 400 / 1596, 5), 0.16], 'line': [0.12, 0.14], 'mark': [0.6, 0.65], 'size': [1596, 2000],
             'found': 8, 'of': 9, 'ahead': {'words': 4, 'weight': 3.0}}
    return suspect(page, word, suggestion, f'ارا حدودها شمالا وشرقا {word} ابن التنيجي وقبلة وغربا',
                   place=more.pop('place', place), **more)


def write_boxes(page: Page, text: str) -> Path:
    from apps.sources.services import regions

    path = regions.boxes_path(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path
