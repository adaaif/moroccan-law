"""A text's official French read from a scanned French BO issue (Q6 of the road plan: «read those scans page by page
in the session», no API): each page cut at its gutter into its two columns, each column read by Tesseract (the free
witness), the text's lines taken from its first words to the end of its pages, then cut at its «Article …» headings
as the French edition's are (french.split_articles). The readings are kept beside the file, so a rerun reads nothing
twice; an article a topic cites is read against the page image before it is shown, and what was put right is kept in
data/*.yaml and put right again at every load.

    load_bo_french sources/road/sgg_bo_5874_fr.pdf --url https://www.sgg.gov.ma/BO/bo_fr/2010/bo_5874_fr.pdf \
        --text /akn/ma/act/loi/52-05 --pages 1646-1692 --issue 5874 --issue-date 2010-09-16 \
        --title "Loi n° 52-05 portant code de la route" --start "Loi n° 52-05 portant code"
"""
import re
import subprocess
from collections import Counter
from difflib import SequenceMatcher
import tempfile
from datetime import date
from pathlib import Path

import pypdfium2 as pdfium
import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.corpus.models import Text
from apps.corpus.services.addresses import text_path
from apps.corpus.services.french import _ARTICLE, _HEADER, _join, article_number, clean, split_articles
from apps.sources.models import DocumentKind, Source
from apps.sources.services.ingest import ingest_file
from apps.translations.models import FrenchArticle, FrenchText

SCALE = 300 / 72
FOLIO = re.compile(r'^\s*(\d{3,4})\b|\b(\d{3,4})\s*$')
# A heading as Tesseract gives it: «Aïticle 55», «Articie 266», «. Article 5», «Article 22]», «| Article 44 | .»,
# «ARTICLE PREMIER. —», and a decree's «ART. 4. —», «ART.7.—», «ART. 6,-—», «AR. 12, -», «ARt, 14.», «AnT. 70.»,
# «ARE. 6.», «ART. ]8.», «ART. [16.», «ART. #2.», «ART. 4i.», «ART. S5.», and in the 1970s' type «Amr. 83.», «AnrT. 8a.».
# Also «Article $ L'arabe demeure …» and «Article 49 Tous supportent …» between 39 and 41 (BO 5964 bis): a heading whose
# figure was misread, its first sentence joined to it.
LOOSE_HEAD = re.compile(r'^[\W_]{0,3}(?:(?:(?i:A(?:R[A-Z]?|[A-Z]T|[A-Z]{1,2}[RT]))\s*[.,]|Article)\s*\S{1,4}\s*[.,][\s.,:\-–—]*'
                        r'|Article\s+\S{1,3}\s+(?=[A-ZÀ-ÖØ-Ý«]))(?P<rest>.*)$')
# A speck before the heading is read as a letter: «a Article 166».
OCR_HEAD = re.compile(r'^(?:[a-z]\s+)?[\W_]{0,3}(?P<w>[A-Za-zïîÏÎ]{5,8})\s+(?P<n>(?i:premi[eè]r?e?)|[\d\]}|lI]*\d[\d\]}|lI]*|\d)'
                      r'(?P<s>\s+(?:bis|ter|quater))?[\s|.,:\-–—]*(?P<rest>.*)$')
ART_HEAD = re.compile(r'^[\W_]{0,3}(?i:A(?:R[A-Z]?|[A-Z]T|[A-Z]{1,2}[RT]))\s*[.,]\s*'
                      r'(?P<n>[\dSO\[\]{}|lIi#!]*\d[\dSO\[\]{}|lIi#!orga]*|g[\dorg]?|\d)'
                      r'(?P<s>\s+(?:bis|ter|quater))?[\s|.,:\-–—]*(?P<rest>.*)$')

# Worse in the 1960s' and 1970s' type: «Au. 32. —», «Aer. 6. —», «RT. 100. —», «£. “ART. 98. —», «Am: ‘96. - —», «Anv. G7.
# —», «ART. ror, —», after a speck or none; always before a dash, so «Au. 5, de la» stays a line. Letters for figures:
# «So», «Go», «ho», «Ro», «ror» are 50, 60, 40, 80, 101 (renumber settles a wrong guess).
WIDE_HEAD = re.compile(r'^(?:[\W\d_]{0,5}|[^\W\d]\W{0,3}\s)\W{0,3}(?i:A[A-Zü]{0,3}|RT)\s*[.,:;]+\s*[‘\'"\-]?'
                       r'(?P<n>[\dSOGhRrogIl|\]\[{}#!]{1,4})(?P<s>)\s*[.,:;]?\s*[-–—=]+[\s\-–—]*(?P<rest>\S.*)$')
WIDE_FIGURES = str.maketrans('SOGhRrogIl|][{}#!', '50648109111111111')

RUNNING = re.compile(r'^(?:.*?(?:BULLETIN|BULLE\w*|\w*OFFICIEL|N°\s*\d{4}(?:\s*bis)?|\d{1,2}\w?\s+chaoua\w(?:\s+\d{4})?'
                     r'|\(\d{1,2}-\d{1,2}-\d{4}\)|\b1[6-9]\d{2}\b)[\s—–-]*)+')


def tidy(line: str) -> str:
    """What Tesseract adds to a column: a piece of the running head inside it («1431 (30-9-2016) N OFFICIEL N° 5878
    bis—21 chaoual 3 si l'accident …»), a speck alone on its line, a list's «1» read «l» or «|», a division's title
    in capitals (the cutter knows «Chapitre 9», not the words under it). '' drops the line."""
    if 'OFFICIEL' in line or 'BULLETIN' in line:
        line = RUNNING.sub('', line).strip()
    if re.fullmatch(r'(?:\d{4}\s*)?\(\d{1,2}-\d{1,2}-\d{4}\)', line):        # the head's date, alone
        return ''
    if (head := heading(line)) != line:        # first: «ARTICLE 14» is in capitals too (BO 4420 bis)
        return head
    if (len(line) <= 2 and not line.isdigit()) or (line.isupper() and len(re.sub(r'\W', '', line)) > 8
                                                 and not re.fullmatch(r'PR[EÉ]AMBULE\W*', line)):   # a constitution's
        return ''
    return re.sub(r'^[l|I](?=\s*[.—–-]?\s)', '1', line)


def heading(line: str) -> str:
    """An article heading misread by Tesseract given back as printed; any other line as it is."""
    m = OCR_HEAD.match(line)
    if m and (m.group('w')[0] not in 'AÂ' or SequenceMatcher(None, m.group('w').lower(), 'article').ratio() < 0.7):
        m = None
    if m and m.group('rest')[:1].islower():         # «Article 3 de la loi …»: a reference that opens a line
        m = None
    m = m or ART_HEAD.match(line)                    # «ART.» opens no reference
    if not m and (m := WIDE_HEAD.match(line)):
        n = m.group('n').translate(WIDE_FIGURES)
        return f"Article {n}. – {m.group('rest')}" if n.isdigit() and n[0] != '0' else line
    if not m:
        return line
    # One letter for a figure: «]8», «[16», «#2», «22]» are 18, 116, 12, 221; «S5» is 5 with a speck before it.
    # And in the 1970s' type, a figure read as a letter: «6g», «go», «gr», «6r», «8a» are 69, 90, 91, 61, 80.
    n = m.group('n').translate(str.maketrans('[]{}|lIi#!Ogroa', '111111111109100', 'S')) \
        if not m.group('n').lower().startswith('premi') else 'premier'
    head = f"Article {n}{m.group('s') or ''}"
    return f"{head}. – {m.group('rest')}" if m.group('rest') else head


def gutter(image) -> int | None:
    """The x of the white strip between the page's two columns, looked for in its middle fifth; None for a page
    printed across (a table, a title page)."""
    w, h = image.size
    band = image.crop((0, int(h * 0.08), w, int(h * 0.95))).point(lambda v: 255 - v).resize((w, 1))
    dark = list(band.getdata())
    lo, hi = int(w * 0.4), int(w * 0.6)
    x = min(range(lo, hi), key=lambda i: dark[i])
    return x if dark[x] < 2 else None


def parts(image) -> list:
    """What is read in turn: the page's two columns, or the page whole; a page whose columns stop above a part printed
    across (the constitution's last articles over the Constitutional Council's decision, BO 5964 bis p. 1928) has its
    columns down to the rule across, then that part; one whose columns start under a part across, that part first."""
    w, h = image.size
    if (x := gutter(image)) is not None:
        return [image.crop((0, 0, x, h)), image.crop((x, 0, w, h))]
    rows = list(image.point(lambda v: 255 - v).resize((1, h)).getdata())

    def cut(y: int, near: range) -> int:
        # A text line across barely darkens the gutter: the cut goes to the rule across the page, else to a blank row,
        # so no line is cut in two.
        rule = max(near, key=lambda r: rows[r])
        return rule if rows[rule] > 100 else next((r for r in near if rows[r] == 0), y)

    y = next((h * k // 40 for k in range(39, 15, -1) if (x := gutter(image.crop((0, 0, w, h * k // 40)))) is not None), None)
    if y is not None:
        y = cut(y, range(y - 1, max(y - h // 10, 0), -1))
        return [image.crop((0, 0, x, y)), image.crop((x, 0, w, y)), image.crop((0, y, w, h))]
    # A front page: the masthead and its contents across, then the columns (BO 2616 bis, the 1962 constitution).
    y = next((h * k // 40 for k in range(1, 24) if (x := gutter(image.crop((0, h * k // 40, w, h)))) is not None), None)
    if y is not None:
        y = cut(y, range(y, min(y + h // 10, h)))
        return [image.crop((0, 0, w, y)), image.crop((0, y, x, h)), image.crop((x, y, w, h))]
    return [image]


def read_page(pdf, index: int, cache: Path) -> list[str]:
    """The page's columns (and a part printed across under them), each as Tesseract read it."""
    out = cache / f'{index + 1}.txt'
    if out.exists():
        return out.read_text().split('\f')
    image = pdf[index].render(scale=SCALE, grayscale=True).to_pil().convert('L')
    text = []
    for part in parts(image):
        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            part.save(f.name)
            text.append(subprocess.run(['tesseract', f.name, '-', '-l', 'fra', '--psm', '4'],
                                       capture_output=True, text=True, check=True).stdout)
    out.write_text('\f'.join(text))
    return text


def renumber(lines: list[tuple[int, str]], window: int = 12) -> list[tuple[int, str]]:
    """Headings whose figure Tesseract changed, read as the numbers they stand for: of all the ways to read each
    heading's number as printed or with one figure changed, the run of headings counting up (by one, or two where a
    heading was lost) that keeps the most headings for the fewest changes («ART. 16» after 8 is 10, «Art. 50», «32»,
    «54» in the 1970s' type are 70, 72, 74, BO 3098; «Article 49» after 39 is 40, BO 5964 bis; «Article 84», «85» after
    33 are 34, 35). fill_gaps then finds a heading left between two («ART. g.» for 9)."""
    heads = [(k, n) for k, (_, line) in enumerate(lines)
             if (m := _ARTICLE.match(line)) and not line.startswith(('«', '"')) and (n := article_number(m.group('head'))).isdigit()]
    options = [[(int(n), 0.0)] + [(int(w), 0.5) for i in range(len(n)) for d in '0123456789'
                                  if d != n[i] and (w := n[:i] + d + n[i + 1:])[0] != '0'] for _, n in heads]
    best: list[dict] = []           # per heading: number read → (score, the heading and number before it)
    for i, opts in enumerate(options):
        here = {}
        for v, cost in opts:
            top = (1 - cost - 0.4 * (v - 1), None)      # a run starts at article 1, or pays for what it skipped
            for j in range(max(0, i - window), i):
                for u in (u for u in (v - 1, v - 2) if u in best[j]):
                    score = best[j][u][0] + 1 - cost - 0.4 * (v - u - 1)
                    if score > top[0]:
                        top = (score, (j, u))
            here[v] = top
        best.append(here)
    if not heads:
        return lines
    i, v = max(((i, v) for i in range(len(best)) for v in best[i]), key=lambda iv: best[iv[0]][iv[1]][0])
    chosen = {}
    while True:
        chosen[heads[i][0]] = v
        if best[i][v][1] is None:
            break
        i, v = best[i][v][1]
    out = []
    for k, (page, line) in enumerate(lines):
        if k in chosen and str(chosen[k]) != article_number((m := _ARTICLE.match(line)).group('head')):
            line = f"Article {chosen[k]}. – {m.group('rest')}" if m.group('rest') else f'Article {chosen[k]}'
        out.append((page, line))
    return out


# A heading inside an article's words, at a paragraph's start or after a sentence's end («… par eux, Art ha. — Les
# séances», «ART 43. — Chaque Chambre», BO 2616 bis).
EMBEDDED = re.compile(r'(?:^|(?<=[.,;:]\s))[\W_]{0,3}(?:(?i:A[A-Zü]{0,3}|RT)|Article)\.?\s*\S{1,4}\s*[.,]\s*[—–-]+\s*'
                      r'(?=[A-ZÀ-Ý«‘\'])', re.M)


def _cut(body: str) -> tuple[str, str] | None:
    """The words before and after the first heading inside them (not at their very start)."""
    m = next((m for m in EMBEDDED.finditer(body) if m.start() > 0), None)
    if m is None:
        head = next((m for m in (LOOSE_HEAD.match(x) for x in body.split('\n')[1:]) if m), None)
        if head is None:
            return None
        at = body.index(head.group(0))
        return body[:at].strip(), head.group('rest')
    return body[:m.start()].strip(), body[m.end():].strip()


def fill_gaps(articles: list[dict]) -> int:
    """An article missing between its two neighbours is the head-like paragraph in the first one's body whose
    figures Tesseract lost («ART. IS. — sont interdits …» between 150 and 152; «ART. 6.» after 15), or one printed
    inline after a sentence; failing that, the second one's words before a heading inside them (BO 3098: art. 67's
    words, then «ART. 6. —» for 68, under 67's lost heading). The count."""
    done, k = 0, 0
    while k < len(articles) - 1:
        a, b = articles[k], articles[k + 1]
        if a['number'].isdigit() and b['number'].isdigit() and int(b['number']) == int(a['number']) + 2:
            n = str(int(a['number']) + 1)
            if cut := _cut(a['body']):
                a['body'] = cut[0]
                articles.insert(k + 1, {**a, 'label': f'Article {n}', 'number': n, 'body': cut[1]})
                done += 1
            elif cut := _cut(b['body']):
                articles.insert(k + 1, {**b, 'label': f'Article {n}', 'number': n, 'body': cut[0]})
                b['body'] = cut[1]
                done += 1
        k += 1
    return done


def number_by_arabic(articles: list[dict], arabic: list[tuple[str, str]]) -> list[str]:
    """Each French article given the number of the Arabic article it says (`--align`, the constitutions of 1962–1972,
    whose heads the 1960s' type garbled): the local meaning model reads both languages, and the French articles are
    matched to the Arabic in order, one each, the most alike overall, a number already agreeing weighed a little more. A
    French article matched to none keeps its number if no other holds it, else is dropped. What changed, as «a→b»."""
    import numpy as np

    from apps.search.services.meaning import Encoder

    enc = Encoder(threads=4)
    fr = enc.encode([a['body'][:2000] or a['label'] for a in articles])
    ar = enc.encode([body[:2000] for _, body in arabic])
    sim = fr @ ar.T
    m, n = sim.shape
    score = np.zeros((m + 1, n + 1))
    step = np.zeros((m + 1, n + 1), dtype=np.int8)        # 1 matched, 2 a French one left, 3 an Arabic one left
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            pair = score[i - 1, j - 1] + sim[i - 1, j - 1] + (0.05 if articles[i - 1]['number'] == arabic[j - 1][0] else 0)
            score[i, j], step[i, j] = max((pair, 1), (score[i - 1, j], 2), (score[i, j - 1], 3))
        score[i, 0], step[i, 0] = 0, 2
    score[0, 1:], step[0, 1:] = 0, 3
    match, i, j = {}, m, n
    while i and j:
        if step[i, j] == 1:
            match[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif step[i, j] == 2:
            i -= 1
        else:
            j -= 1
    changed, taken = [], {arabic[j][0] for j in match.values()}
    for k, a in enumerate(articles):
        number = arabic[match[k]][0] if k in match else (a['number'] if a['number'] not in taken else None)
        if number != a['number']:
            changed.append(f"{a['number']}→{number}")
        a['number'] = number
        if number and number != 'preamble':
            a['label'] = 'Article premier' if number == '1' else f'Article {number}'
    articles[:] = [a for a in articles if a['number']]
    return changed


FIXES = Path(__file__).resolve().parents[2] / 'data'


def read_on_pages(path: str, articles: list[dict]) -> list[str]:
    """The words a person read on the French pages (data/*.yaml, `language: fr`, for this text), put right in the
    articles at every load: Tesseract's «b}» for «b)», a chapter's name glued at an article's end; `bodies`, an
    article read whole (art. 99's table). What was not found."""
    missed = []
    for file in sorted(FIXES.glob('*.yaml')):
        spec = yaml.safe_load(file.read_text(encoding='utf-8')) or {}
        if spec.get("text") != path:
            continue
        for fix in spec.get('fixes') or []:
            for n in fix['arts']:
                a = next((a for a in articles if a['number'] == str(n)), None)
                if a is None or fix['wrong'] not in a['body']:
                    missed.append(f'{file.name}: art. {n} «{fix["wrong"][:40]}»')
                    continue
                a['body'] = a['body'].replace(fix['wrong'], fix['right'], 1)
        for n, body in (spec.get('bodies') or {}).items():       # a body read whole (a table read without columns)
            a = next((a for a in articles if a['number'] == str(n)), None)
            if a is None:
                missed.append(f'{file.name}: art. {n}')
            else:
                a['body'] = body.strip()
    return missed


class Command(BaseCommand):
    help = "Read a text's French from a scanned French BO issue and keep it beside the Arabic."

    def add_arguments(self, parser):
        parser.add_argument('path', help='the issue under CORPUS_DIR')
        parser.add_argument('--url', required=True, help='where the SGG serves it')
        parser.add_argument('--text', required=True, help="the Arabic text's AKN URI")
        parser.add_argument('--pages', required=True, help='its printed pages, 1646-1692')
        parser.add_argument('--issue', required=True, help='5874, or 5878-bis')
        parser.add_argument('--issue-date', required=True)
        parser.add_argument('--title', required=True)
        parser.add_argument('--start', required=True, help='the words its own heading starts with')
        parser.add_argument('--align', action='store_true',
                            help='number the articles by the Arabic they say (the meaning model), for a garbled scan')

    def handle(self, *args, path, url, text, pages, issue, issue_date, title, start, align=False, **opts):
        arabic = Text.objects.filter(akn_uri=text).first()
        file = Path(settings.CORPUS_DIR) / path
        if arabic is None or not file.exists():
            raise CommandError(f'{path} or {text}: not found')
        number, _, suffix = issue.partition('-')
        doc = ingest_file(file, source=Source.SGG_BO, kind=DocumentKind.BO_ISSUE, language='fr', url=url)
        first, last = map(int, pages.split('-'))
        cache = Path(settings.CORPUS_DIR) / 'derived' / 'ocr_fr' / doc.sha256[:16]
        cache.mkdir(parents=True, exist_ok=True)
        pdf = pdfium.PdfDocument(str(file))
        try:
            columns = [read_page(pdf, index, cache) for index in range(len(pdf))]
        finally:
            pdf.close()
        # Each column's first line is the running head («1644 BULLETIN OFFICIEL N° 5874 …»), or half of it when the
        # gutter cuts it («1904 BULLE» | «IN OFFICIEL N° 5964 bis …»: the two joined); the folio it prints, less the
        # page's place in the file, is the same on every page: the commonest is taken.
        heads = [[next((x for x in c.splitlines() if x.strip()), '') for c in page] for page in columns]
        offsets = Counter(int(m.group(1) or m.group(2)) - index for index, hs in enumerate(heads)
                          for h in {*hs, ' '.join(hs[:2])} if (_HEADER.search(h) or 'N°' in h) and (m := FOLIO.search(h)))
        if not offsets:
            raise CommandError(f'{path}: no folio read')
        offset = offsets.most_common(1)[0][0]
        lines = []
        for index, page in enumerate(columns):
            if not first <= offset + index <= last:
                continue
            for column, head in zip(page, heads[index]):
                for line in column.splitlines():
                    line = clean(line).strip()
                    running = _HEADER.search(line) or 'N°' in line or re.fullmatch(r'\d{3,4}', line)
                    if line and not (line == clean(head).strip() and running):
                        if line := tidy(line):
                            lines.append((offset + index, line))
        anchor = re.compile(r'\s+'.join(map(re.escape, start.split())), re.I)
        at = next((k for k, (_, line) in enumerate(lines) if anchor.search(line)), None)
        if at is None:
            raise CommandError(f'«{start}» not found on pages {pages}')
        articles = split_articles(renumber(lines[at:]))
        if not articles:
            raise CommandError('no article read')
        # A constitution's «Préambule» stands before its first article, under no «Article» heading: kept as an article
        # numbered `preamble`, as the Arabic's «تصدير» is (paired by number).
        own = next((k for k in range(at, len(lines)) if re.fullmatch(r'PR[EÉ]AMBULE\W*', lines[k][1].upper())), None)
        first_head = next((k for k in range(at, len(lines)) if (m := _ARTICLE.match(lines[k][1]))
                           and article_number(m.group('head')) == articles[0]['number']), None)
        if own is not None and first_head is not None and own < first_head:
            words = [line for _, line in lines[own + 1:first_head]
                     if not re.match(r'^(?:TITRE|Titre)\b|^[A-ZÉÈ\s,\'-]{6,}$', line)]
            articles.insert(0, {'label': 'Préambule', 'number': 'preamble', 'page': lines[own][0], 'heading_path': [],
                                'body': '\n'.join(_join(words)).strip()})
        fill_gaps(articles)
        if align:
            ours = [(a.number, a.body) for a in arabic.latest_version().articles.order_by('order')]
            moved = number_by_arabic(articles, ours)
            self.stdout.write(f'  aligned with the Arabic: {len(moved)} renumbered {moved}')
        for miss in read_on_pages(text_path(text), articles):
            self.stderr.write(f'  not found: {miss}')
        FrenchText.objects.update_or_create(text_uri=text, defaults={
            'type': arabic.type, 'number': arabic.number, 'title': title, 'signed_on': arabic.signed_on,
            'issue_number': int(number), 'issue_suffix': suffix, 'issue_date': date.fromisoformat(issue_date),
            'document_sha': doc.sha256, 'pages': pages, 'consolidated_to': None})
        FrenchArticle.objects.filter(text_uri=text).delete()
        FrenchArticle.objects.bulk_create([FrenchArticle(text_uri=text, order=k + 1, label=a['label'][:80],
                                                         number=a['number'], body=a['body'], printed_page=a['page'])
                                           for k, a in enumerate(articles)])
        Text.objects.filter(akn_uri=text, title_fr='').update(title_fr=title)
        numbers = [a['number'] for a in articles]
        self.stdout.write(f'{text}: {len(articles)} French articles on pages {pages}, {numbers[0]} to {numbers[-1]}')
