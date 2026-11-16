"""A French consolidation from Adala (T1 of the work plan: the labour code's, «version consolidée en date du 26
octobre 2011»), read from its Word text layer as the Arabic files are: the page numbers and the footnotes set apart by
their size (adala.split_page), then the articles cut at their «Article N» headings, in order."""
import re

import pypdfium2 as pdfium

from apps.consolidation.services.adala import MARK, _lines, _main_size, split_page

# «Article 12», «Article 3 bis», and the DOC's «Article 106-1», «Article 618-3 bis» (H4 of the housing plan); an
# order copied from the BO keeps its «ARTICLE PREMIER» and «ART. 2.» (order 02.11, the road plan).
HEAD = re.compile(r'^(?:Article|ARTICLE|ART\.)\s+(premier|PREMIER|\d+)((?:-\d+)*(?:\s+(?:bis|ter|quater|quinquies|sexies|septies|octies))?)\s*[.:]?\s*[-–]?\s*(.*)$')
# A heading Adala quotes in a footnote, from another text: «Article 23 : « Le mode d'emploi … »» (law 31.08's footnotes
# copy decree 2.12.503's articles). The French files' own headings take no colon, but for a title in capitals (TITLED).
QUOTED = re.compile(r'^(?:Article|ARTICLE)\s*\d+\s*:\s*(?:«.*)?$')
# A heading with its title in capitals, as the nationality code sets them: «ARTICLE 4: AGE DE LA MAJORITE …». The title is
# the body's first line, a paragraph of its own.
TITLED = re.compile(r'^ARTICLE\s+(?:PREMIER|\d+)\s*:\s*([^a-z]+)$')
DIVISION = re.compile(r'^(?:\d{1,3}\s+)?(?:LIVRE|TITRE|CHAPITRE|SECTION)\s+\S')
# …and the divisions under it, named in small letters: «Chapitre premier : Du mandat en général», «Section première. – …».
NAMED = re.compile(r'^(?:Livre|Titre|Chapitre|Section)\s+(?:[Pp]remier|[Pp]remière|unique|[IVXL]+|\d+|[a-zé]+i[eè]me)\b\s*(?:[:.–-]|De\s|Des\s|Du\s)')
# A footnote's first line, «2-Voir articles 7, 23 et 24 du décret …»; Word sets some a point under the body only.
NOTE_START = re.compile(r'^\d{1,3}\s?-\s?\S')
GAP = 20        # a heading alone on its line may skip repealed articles (the DOC's 325 to 334)


def _number(n: str, bis: str | None) -> str:
    return ('1' if n.lower() == 'premier' else n) + (('-' + '-'.join(bis.replace('-', ' ').split())) if bis and bis.strip() else '')


def read(path: str, start: str | None = None) -> list[dict]:
    """The file's articles; with `start`, only from the first line that opens so (the DGI's tax code names «Article 5 de la
    loi de finances» in its preface, before its own «Article premier.-»)."""
    pdf = pdfium.PdfDocument(path)
    try:
        pages = [_lines(pdf[i].get_textpage()) for i in range(len(pdf))]
    finally:
        pdf.close()
    main = _main_size(pages)
    articles: list[dict] = []
    previous = 0
    naming = False
    for index, page in enumerate(pages):
        body, _ = split_page(page, main)
        marks = {int(n) for line in body for n in MARK.findall(line)}
        if (kept := _without_notes(page, main, marks)) is not page:
            body, _ = split_page(kept, main)
        for line in body:
            line = MARK.sub('', line).strip()
            if start and not articles and not line.startswith(start):
                continue
            line = re.sub(r'^(Article\s+\d+)l\b', r'\g<1>1', line)    # «Article 3l»: an «l» typed for a «1»
            m = None if QUOTED.match(line) else HEAD.match(line)
            # Each heading carries on from the one before (a cross-reference never opens a line with a capital).
            n = int(_number(m.group(1), None)) if m else 0
            label = m.group(1) if m else ''
            follows = n in (previous + 1, previous) or (previous < n <= previous + GAP and not m.group(3))
            if m and not follows and line.startswith('ARTICLE ') and (d := m.group(1)).isdigit():
                # A heading's footnote mark set in the body's size, run into its number: «ARTICLE 1213: DEROGATIONS» is
                # article 12, note 13, and «ARTICLE 98» article 9, note 8 (the nationality code).
                label = next((d[:k] for k in range(1, len(d)) if int(d[:k]) == previous + 1), label)
                n = int(_number(label, None))
                follows = n == previous + 1
            if m and follows and not (n == previous and not m.group(2).strip()):
                titled = TITLED.match(line)
                articles.append({'label': f'Article {label.lower()}{m.group(2) or ""}', 'number': _number(label, m.group(2)),
                                 'lines': [] if titled else [m.group(3)] if m.group(3) else [], 'page': index + 1,
                                 'title': titled.group(1).strip() if titled else ''})
                previous, naming = n, False
            elif articles and line and ((DIVISION.match(line) and line.isupper()) or (naming and line.isupper())
                                        or (naming and NAMED.match(line))):
                # «SECTION 2: NATURALISATION», «11 SECTION 3: …» after a page's number, and a name on the lines under it.
                naming = True
                continue
            elif articles and line:
                naming = False
                a = articles[-1]
                if a['title'] and not a['lines'] and line.isupper() and not a['title'].endswith(':'):
                    a['title'] += ' ' + line          # «… DES DISPOSITIONS RELATIVES A» / «LA NATIONALITE»
                else:
                    a['lines'].append(line)
    for a in articles:
        title = a.pop('title').rstrip(' :')
        a['body'] = '\n'.join(([title] if title else []) + paragraphs(a.pop('lines'))).strip()
    return articles


def _without_notes(page: list, main: float, marks: set[int]) -> list:
    """The page without its footnotes when Word set them only a point under the body (law 31.08's French: the body
    14, the notes 13), so split_page's share keeps them: among the page's last lines set smaller than the body, the
    notes start at the first that opens with the number of a mark the page's body carries. Small lines above it stay
    (the DOC sets some articles small, and numbers their items «1- …»)."""
    small = [bool(ln) and all(s < main - 0.5 for ch, s, _ in ln if not ch.isspace()) for ln in page]
    start = len(page)
    while start and small[start - 1]:
        start -= 1
    for k in range(start, len(page)):
        m = NOTE_START.match(''.join(ch for ch, *_ in page[k]).strip())
        if m and int(re.match(r'\d+', m.group(0)).group(0)) in marks:
            return page[:k]
    return page


def paragraphs(lines: list[str]) -> list[str]:
    """Word's printed lines joined back into paragraphs: a line runs on into the next unless it ends a sentence or
    the next opens a list item («- 96 heures …», «1. le remplacement …»)."""
    out: list[str] = []
    for line in lines:
        opens = re.match(r'^(?:[-–•]\s|\d+[.)°]\s|[a-z]\)\s)', line)
        if out and not opens and not re.search(r'[.:;!?»]\s*$', out[-1]):
            out[-1] = f'{out[-1]} {line}'
        else:
            out.append(line)
    return out
