"""A finance bill as filed in Parliament (the finance-bill review, P1, P17; 26 Oct 2026): the government's own
files (the Ministry of Economy and Finance's, the same the Chamber's dossier holds), born digital, read from their text
layers, cut at their articles, Arabic and French. A bill is never law: its text lives at its own address
(`/akn/ma/act/projet-loi/60-26`), its versions are `Consolidation.BILL` (as filed, then as each chamber voted it), and
what its articles would change is read as proposals (`read_bill`), never applied to a law's versions.

The Arabic layer gives back the lam-alif turned («املادة», «األولى»), as Adala's and the DGI's files do: put right by
`layer.repair` against the corpus's words; amounts in visual order («000 000 000 60») turned back as the DGI reader does."""
import re
from dataclasses import dataclass

import pypdfium2 as pdfium

from apps.consolidation.services import sgg

# «المادة 7», «املــادة األولى»: a heading alone on its line (the layer turns «الم» into «امل»).
AR_HEAD = re.compile(r'^(?:ا?ل?م|امل)[ـ]*ا[ـ]*د[ـ]*ة\s+(الأولى|األولى|\d{1,3})\s*$')
FR_HEAD = re.compile(r'^Article\s+(premier|\d{1,3})\s*$')
AR_DIVISION = re.compile(r'^(?:الجـ?زء|الجزء|الباب|الفرع|القسم)\s')
FR_DIVISION = re.compile(r'^(?:PREMIERE|DEUXIEME|TROISIEME|PREMIÈRE|DEUXIÈME)\s+PARTIE$|^TITRE\s|^CHAPITRE\s')
# Running heads and folios: «مشروع قانون المالية رقم 60.26», «للسنة المالية 2027», «- 2 -», «PROJET DE LOI DE FINANCES N° 60-26».
RUNNING = re.compile(r'^(?:مشروع قانون المالية رقم [\d.]+|للسنة المالية \d{4}|PROJET DE LOI DE FINANCES N° [\d-]+|'
                     r'POUR L’ANNEE BUDGETAIRE \d{4}|-\s*\d{1,3}\s*-|\d{1,3})$')
ENDS = re.compile(r'[.:؛!؟?»"]\s*$|\)\s*$')
OPENS = re.compile(r'^(?:[IVX]+\s*[-.–]|[A-Z]\s*[-.–)]|[ء-ي]{1,4}\s*[-–)]|\d{1,2}\s*[°-]|\(?\d{1,2}\s*[-–)]|[-–•●▪]\s*\S|«)')


@dataclass
class Bill:
    articles: list[sgg.SggArticle]
    stats: dict


def page_lines(path: str) -> list[list[str]]:
    pdf = pdfium.PdfDocument(path)
    try:
        return [[ln.strip() for ln in pdf[i].get_textpage().get_text_range().splitlines()] for i in range(len(pdf))]
    finally:
        pdf.close()


def _number(word: str) -> int:
    return 1 if word in ('الأولى', 'األولى', 'premier') else int(word)


def cut(pages: list[list[str]], head: re.Pattern, division: re.Pattern, fix=lambda s: s) -> list[sgg.SggArticle]:
    """The bill's articles in order: a heading alone on its line whose number is the next one starts an article (a
    reference to «المادة 7 من …» runs on in its sentence, never alone); the divisions above become its headings; lines
    are joined into paragraphs."""
    articles: list[sgg.SggArticle] = []
    heads: list[str] = []
    last = 0
    for index, raw in ((i, ln) for i, lines in enumerate(pages) for ln in lines):
        line = fix(raw).strip()
        if not line or RUNNING.match(line):
            continue
        m = head.match(line)
        if m and _number(m.group(1)) == last + 1:
            last += 1
            label = line
            articles.append(sgg.SggArticle(label=label, number=str(last), heading_path=list(heads), page=index))
            heads = []
            continue
        if division.match(line) and len(line) < 80:
            heads = [line]
            continue
        if not articles:
            continue
        body = articles[-1].lines
        # A quoted passage prints « at the head of every line: a line runs on from the one before when both are quoted.
        quoted = line.startswith('«') and bool(body) and body[-1].startswith('«')
        rest = line[1:].lstrip() if quoted else line
        if body and len(rest) < 90 and not body[-1].endswith(('.', ':', '؛', ';')) and heads == [] and \
                not ENDS.search(body[-1]) and not OPENS.match(rest) and not re.search(r'\d\s*$', body[-1]) and \
                (quoted or not line.startswith('«')):
            body[-1] = f'{body[-1]} {rest}'
        else:
            body.append(line)
    return articles


def read_arabic(path: str) -> Bill:
    from apps.consolidation.services import layer
    from apps.consolidation.services.dgi import heading
    from apps.sources.services.issue import _SPACED, _unreverse
    words = layer.lexicon()
    stats = {'words': 0, 'turned': 0, 'unknown': 0}

    def fix(line: str) -> str:
        out, st = layer.repair(line, words)
        for k in stats:
            stats[k] += st[k]
        # Amounts printed in visual order («000 000 000 60» for 60 000 000 000), and brackets turned («)9 أكتوبر 1977(»).
        out = _SPACED.sub(_unreverse, out)
        out = signed(out)
        out = re.sub(r'\)([^()]{1,60})\(', r'(\1)', out)
        # «%10بالنسبة» → «10% بالنسبة»; a list mark turned, «I-.» → «I.-».
        out = re.sub(r'%\s?(\d+(?:[.,]\d+)?)\s*', r'\1% ', out)
        out = re.sub(r'(^|«)([IVX]+)\s*-\s*\.', r'\1\2.-', out)
        # «فاتح يناير ،2027»: the comma the layer sets before a year belongs after it.
        out = re.sub(r'(\s)،(\d{4})\b', r'\1\2،', out).strip()
        # A quoted line opens with the guillemet turned («»المادة .57 - الإعفاءات»), its heading's number in visual order,
        # and may close turned too: put back as the finance laws print them («المادة 57.- الإعفاءات»).
        if out[:1] in ('»', '«'):
            out = '«' + heading(out[1:].strip())
        if out.endswith('«') and out.count('«') > out.count('»'):
            out = out[:-1] + '»'
        return out

    return Bill(articles=cut(page_lines(path), AR_HEAD, AR_DIVISION, fix), stats=stats)


def signed(line: str) -> str:
    """A negative amount's sign and first group come last in the layer: «690 921 000 -88» is -88 690 921 000."""
    return re.sub(r'(?<![\d-])((?:\d{3} )+\d{3}) -(\d{1,3})(?![\d ])', r'-\2 \1', line)


def read_french(path: str) -> Bill:
    return Bill(articles=cut(page_lines(path), FR_HEAD, FR_DIVISION), stats={})


MONTHS = {'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8, 'septembre': 9,
          'octobre': 10, 'novembre': 11, 'décembre': 12}
SUFFIX = r'(?:\s+(bis|ter|quater|quinquies|sexies))?'


def dates_of_effect(french_body: str) -> dict[str, tuple[str, str, bool]]:
    """{code article: (ISO date, words, partial)} from a finance bill's «Dates d'effet» (art. 7-IV): «5 – Les dispositions
    de l'article 59-I … sont applicables aux revenus acquis à compter du 1er janvier 2027». The first date a paragraph
    names after «compter du» is its date; a paragraph that dates only the provisions «relatives à» one thing (7: the
    importers' advance in 82-I, which also brings the electronic declaration) dates part of the change: `partial`."""
    from datetime import date
    out: dict[str, tuple[str, str, bool]] = {}
    # The article's last «Dates d'effet» is its paragraph IV (art. 247 is titled «Dates d'effet et dispositions transitoires»).
    tail = french_body.rsplit('Dates d’effet', 1)[-1] if 'Dates d’effet' in french_body else ''
    for para in re.split(r'\n(?=\d{1,2}\s*[–-]\s*Les dispositions)', tail):
        when = re.search(r'compter du\s+(1er|\d{1,2})\s+(\w+)\s+(\d{4})', para)
        if not when or when.group(2) not in MONTHS:
            continue
        day = 1 if when.group(1) == '1er' else int(when.group(1))
        on = date(int(when.group(3)), MONTHS[when.group(2)], day).isoformat()
        # The paragraph's own number («11 – Les dispositions …») is no code article.
        head = re.sub(r'^\s*\d{1,2}\s*[–-]', '', para.split('du code général des impôts', 1)[0])
        partial = 'relatives à' in para
        for n, suffix in re.findall(r'(?<![\d-])(\d{1,3})' + SUFFIX + r'(?=[\s\-–,()°]|$)', head):
            key = f'{n}-{suffix}' if suffix else n
            if 0 < int(n) <= 303:
                out.setdefault(key, (on, ' '.join(para.split())[:400], partial))
    return out


def code_articles(french_body: str) -> set[str]:
    """The CGI articles a finance bill's article changes or adds, from its French lead: «les dispositions des articles 6,
    9-II, 11-II, 19 … du code général des impôts … sont modifiées et complétées» and «complété par les articles 125
    sexies, 247 quater et 247 quinquies»."""
    out: set[str] = set()
    leads = [re.search(r'dispositions des\s+articles\s+(.*?)du code général des impôts', french_body, flags=re.S),
             re.search(r'complété par les articles\s+(.*?)comme suit', french_body, flags=re.S)]
    for lead in (m.group(1) for m in leads if m):
        for n, suffix in re.findall(r'(?<![\d-])(\d{1,3})' + SUFFIX + r'(?=[\s\-–,()°]|$)', lead):
            out.add(f'{n}-{suffix}' if suffix else n)
    return out
