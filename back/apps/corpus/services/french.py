"""The BO's French translation edition (decision C3): an issue's contents read by the model, each text cut out of
the pages by its title and its «Article …» headings, and kept beside the Arabic text it translates. The contents
give each text's type, number, title and date, so no text is sent to a model whole: the articles are the page's
own words. The Arabic text is the law; the French is labelled its official translation.

From 2020 the issues are born digital and their text layer is read as it is (Latin letters come out whole, unlike
the Arabic edition's ligatures); a scanned page is read by the OCR."""
import re
import unicodedata

from django.db import transaction

from apps.corpus.models import Text
from apps.corpus.services import works
from apps.corpus.services.issue_structure import SUBTYPES, TOC_SCHEMA, TYPES, _date, normalize_number
from apps.corpus.services.llm import request, run_batch
from apps.sources.models import Issue
from apps.translations.models import FrenchArticle, FrenchText

TOC_PAGES = 8

TOC_SYSTEM = (
    'You read the first pages of an issue of the French translation of the Moroccan Bulletin Officiel and return '
    'its table of contents («SOMMAIRE»): every entry, in order, with the section it is under (TEXTES GENERAUX = '
    'general, TEXTES PARTICULIERS = special), the subject heading above it, the type and number of the text, its '
    'full title as printed, its dates and the printed page where it starts. A promulgating dahir and the law it '
    'promulgates are one entry, typed «law», with the law\'s number. Stop at the end of the table of contents. Use '
    'only what is printed.'
)

# Before 1956 (A of the Bulletin-from-No.-1 review): the French Bulletin is in two parts and its dahirs have no number.
OLD_TOC = (
    ' This issue is from before 1956. Its contents («SOMMAIRE») list a «PARTIE OFFICIELLE» and a «PARTIE NON '
    'OFFICIELLE». In the official part a dahir is type dahir, section general; an arrêté viziriel, résidentiel or of a '
    'director is type order, section special; an individual decision, an appointment or a list is type decision, '
    'section special. Every entry of the non-official part is type other, section other. Texts of this time have no '
    'number: leave number_as_printed empty. Give the date the entry prints («Dahir du 12 août 1913 (9 ramadan 1331)») '
    'as signed_on_gregorian and signed_on_hijri. When the issue has no contents, list the texts whose headings these '
    'pages print, in order.'
)


def toc_system(issue) -> str:
    return TOC_SYSTEM + (OLD_TOC if issue.date and issue.date.year < 1956 else '')


_HEADER = re.compile(r'BULLETIN\s+OFFICIEL', re.I)
_DECOR = re.compile(r'^[\s*_\-–—.•]*$')
_KINDS = ('dahir', 'loi', 'décret', 'decret', 'arrêté', 'arrete', 'décision', 'decision', 'circulaire',
          'ordonnance', 'convention', 'accord', 'avis', 'extrait', 'ordre')
# A contents line («IV. — Dahir relatif au notariat . . . 540»: its dots may be spaced) and the formula before the
# articles («ARRÊTE :»), never a text's heading.
_LEADER = re.compile(r'(?:[.…]\s*){3,}\d{0,4}\s*$')
_CONTENTS_LINE = re.compile(r'(?:[.…]\s*){3,}\d{1,4}\s*$')
_FORMULA = re.compile(r'^\s*(?:arr[êe]te|arr[êe]tons|d[ée]cr[èe]te|d[ée]cide|d[ée]cidons|ordonne|ordonnons)\s*:', re.I)
ORDINALS = {'premier': '1', 'première': '1', 'unique': '1'}
SUFFIXES = {'bis': '-bis', 'ter': '-ter', 'quater': '-quater', 'quinquies': '-quinquies'}
# «Article premier. – Le texte», «Article 2 bis», «ARTICLE 12.», «Article 7-1», and a decree's «ART. 2. – .Les …»
# (BO 7410: its articles 2 to 9 had gone into the first). Never a quoted «Article 3 …».
_ARTICLE = re.compile(r'^(?P<head>(?:article\s+|art\.\s*)(?P<n>premier|première|unique|\d+(?:[.\-]\d+)*)'
                      r'(?:\s+(?P<s>bis|ter|quater|quinquies))?)\s*(?:[.:]\s*(?:[-–—]\s*)?\.?\s*(?P<rest>.*))?$', re.I)
_DIVISION = re.compile(r'^(?:livre|titre|chapitre|section|sous-section|partie|paragraphe)\s+\S+(?:\s+\S+){0,3}$', re.I)
_TAIL = re.compile(r'^(?:fait\s+à|le\s+texte\s+en\s+langue\s+arabe|annexe|tableau)\b', re.I)


def clean(text: str) -> str:
    """The layer's own marks put right: a line-end hyphen kept as U+FFFE, no-break spaces."""
    return unicodedata.normalize('NFC', text.replace('￾', '-').replace('\xa0', ' ').replace('\r', ''))


def read_toc(issue: Issue, model: str, log=print) -> list[dict]:
    pages = list(issue.document.pages.order_by('index')[:TOC_PAGES])
    content = '\n\n'.join(f'=== Page {p.printed_number or p.index + 1} ===\n{clean(p.text)}' for p in pages)
    req = request(f'toc-fr-{issue.number}', model=model, system=toc_system(issue), content=content, schema=TOC_SCHEMA,
                  max_tokens=32000)
    result = run_batch(f'toc-fr:{issue.number}', [req], log=log)[req['custom_id']]
    if not result['data']:
        raise RuntimeError(f'table of contents not read: {result["error"] or result["stop"]}')
    return result['data']['entries']


def issue_lines(issue: Issue) -> list[tuple[int, str]]:
    out = []
    for page in issue.document.pages.order_by('index'):
        lines = [line.strip() for line in clean(page.text).splitlines()]
        lines = [line for n, line in enumerate(lines)
                 if line and not (n < 3 and _HEADER.search(line)) and not _DECOR.match(line)]
        out.extend((page.printed_number, line) for line in lines)
    return out


def _number_in(title: str) -> str | None:
    """The text's number in a title: the law's, not the dahir's that promulgates it («Dahir n° 1-25-70 … portant
    promulgation de la loi organique n° 53-25 …»)."""
    law = re.search(r'promulgation\s+de\s+la\s+loi(?:\s+organique)?(?:\s+de\s+finances)?(?:\s+rectificative)?'
                    r'(?:\s+pour\s+l.ann[ée]e\s+budg[ée]taire\s+\d{4})?\s+n[°ºo]\s*([^\s,;]*\d[^\s,;]*)', title, re.I)
    m = law or re.search(r'n[°ºo]\s*([^\s,;]*\d[^\s,;]*)', title, re.I)
    return m.group(1).rstrip('.') if m else None


def _start_of(lines: list[tuple[int, str]], entry: dict, after: int) -> int | None:
    """The line where an entry's text begins: a line opening with its kind that names its number again, on or
    after its page (the contents' page numbers slip by one now and then)."""
    printed = re.sub(r'^n[°ºo]\s*', '', entry['number_as_printed'].strip(), flags=re.I)
    numbers = {n for n in (_number_in(entry['title']), printed) if n}
    if not numbers:
        found = _dated_start(lines, entry, after)
        return found if found is not None else _titled_start(lines, entry, after)
    for n in range(after, len(lines)):
        page, line = lines[n]
        if page is None or page < entry['page'] - 1 or _LEADER.search(line):
            continue
        if not line.lower().startswith(_KINDS):
            continue
        # An order's title runs over several lines before its number («… chargée de la pêche maritime n° 1458-26»).
        joined = ' '.join(text for _, text in lines[n:n + 9])
        if any(re.search(rf'n[°ºo]\s*{re.escape(num)}(?![\d-])', joined, re.I) for num in numbers):
            return n
    return None


MONTHS = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre',
          'décembre')
_PLAIN = {'dahir', 'arrêté', 'arrete', 'viziriel', 'résidentiel', 'portant', 'relatif', 'concernant', 'modifiant',
          'complétant', 'pour', 'dans', 'avec', 'sans', 'leur', 'sont', 'cette', 'celui', 'celle', 'suite'}


def _plain(text: str) -> str:
    return unicodedata.normalize('NFD', text.lower()).encode('ascii', 'ignore').decode()


# The Hijri months as the French Bulletin spelled them, and the Gregorian ones: a day's words, never a title's.
_HIJRI = re.compile(r'moharr?e?m|safar|reb[ia]+|rabi[ae]?|dj?oum[ae]d[ai]|redj?eb|rajab|chaa?bane?|ramadh?an|chaou?al'
                    r'|chawwal|kaa?da|hi[dj]j?[ae]h?|tani|thani|akhir|aouel|ouel|oula|premier')
_MONTHS_PLAIN = {_plain(m) for m in MONTHS}


def _title_words(title: str) -> list[str]:
    """A title's own words: its Hijri day in brackets, the month names and the words every title has left out (two
    texts of one day would otherwise share «juin» and «chaabane»)."""
    plain = re.sub(r'\([^)]*\)', ' ', _plain(title))
    common = {_plain(x) for x in _PLAIN}
    return [w for w in re.findall(r'[a-z]{4,}', plain)
            if w not in common and w not in _MONTHS_PLAIN and not _HIJRI.fullmatch(w)][:8]


def _dated_start(lines: list[tuple[int, str]], entry: dict, after: int) -> int | None:
    """An entry with no number (a dahir or an arrêté before 1957): the first line on or after its page that opens with
    its kind and names its day («DAHIR DU 12 AOÛT 1913 (9 ramadan 1331)», «… du 1er août …»), the title's words in the
    lines after it when two texts share the day. A heading alone of its day but past the entry's next page must share a
    word with the title (BO 190 of 1916: the Council's minutes of 7 June, whose heading names no kind, had taken the
    order of that day four pages on, and every entry after it was lost)."""
    day = _date(entry.get('signed_on_gregorian') or '')
    if day is None:
        return None
    when = re.compile(rf'\b{day.day}(?:er)?\s+{_plain(MONTHS[day.month - 1])}\s+{day.year}\b')
    words = _title_words(entry['title'])
    found = []
    for n in range(after, len(lines)):
        page, line = lines[n]
        if page is None or page < entry['page'] - 1 or _LEADER.search(line):
            continue
        if not _plain(line).startswith(tuple(_plain(k) for k in _KINDS)) or _FORMULA.match(line):
            continue
        joined = _plain(' '.join(text for _, text in lines[n:n + 4]))
        if when.search(joined):
            found.append((sum(1 for w in words if w in joined), n))
            if len(found) == 3:
                break
    if not found:
        return None
    best = max(found, key=lambda f: (f[0], -f[1]))
    if len(found) == 1:
        near = lines[best[1]][0] <= entry['page'] + 1
        return best[1] if best[0] >= 1 or near or not words else None
    # Two of the title's words, or one where no other heading of that day shares any.
    return best[1] if best[0] >= 2 or (best[0] == 1 and sorted(f[0] for f in found)[-2] == 0) else None


def _titled_start(lines: list[tuple[int, str]], entry: dict, after: int) -> int | None:
    """An old entry the day did not find (no kind in its title, «Nominations dans le personnel …», «Ordre général …»,
    or no day in the contents): a heading on its page or the next that opens with the title's first word, most of
    the title's own words in its first lines."""
    words = _title_words(entry['title'])
    first = (re.findall(r'[a-z]+', _plain(entry['title'])) or [''])[0]
    if len(words) < 2 or len(first) < 4:
        return None
    need = max(2, -(-3 * len(words) // 5))
    for n in range(after, len(lines)):
        page, line = lines[n]
        if page is None or page < entry['page'] - 1 or _LEADER.search(line):
            continue
        if page > entry['page'] + 1:
            return None
        plain = _plain(line).strip()
        if not plain.lstrip(' -–—.0123456789ivx').startswith(first[:5]) or _FORMULA.match(line):
            continue
        joined = _plain(' '.join(text for _, text in lines[n:n + 4]))
        if sum(1 for w in words if w in joined) >= need:
            return n
    return None


def _contents_end(lines: list[tuple[int, str]]) -> int:
    """The line after the issue's contents («SOMMAIRE» to its last dotted line): no text starts inside them."""
    head = next((n for n, (_, text) in enumerate(lines[:60]) if _plain(text).strip().startswith('sommaire')), None)
    if head is None:
        return 0
    end = last = head
    for n in range(head + 1, min(len(lines), head + 400)):
        if _CONTENTS_LINE.search(lines[n][1]):
            end = last = n
        elif n - last > 12:
            break
    return end + 1


def article_number(label: str) -> str:
    m = _ARTICLE.match(label.strip())
    if not m:
        return ''
    n = ORDINALS.get(m.group('n').lower(), m.group('n').replace('.', '-'))
    return n + SUFFIXES.get((m.group('s') or '').lower(), '')


def _follows(number: str, previous: str | None) -> bool:
    if previous is None:
        return number in ('1', '')
    base, head = previous.split('-')[0], number.split('-')[0]
    if not base.isdigit() or not head.isdigit():
        return True
    return int(base) < int(head) <= int(base) + 2 or (head == base and number != previous)


def split_articles(lines: list[tuple[int, str]]) -> list[dict]:
    """A text's lines → its articles, each with its page and the divisions above it."""
    candidates = [(k, m) for k, (_, line) in enumerate(lines)
                  if (m := _ARTICLE.match(line)) and not line.startswith(('«', '"'))]
    heads, previous = set(), None
    for k, m in candidates:
        number = article_number(m.group('head'))
        if _follows(number, previous):
            heads.add(k)
            previous = number
    articles, path, tail = [], {}, False
    last = max(heads) if heads else len(lines)
    for k, (page, line) in enumerate(lines):
        if k in heads:
            m = _ARTICLE.match(line)
            label = re.sub(r'\s+', ' ', m.group('head')).strip()
            articles.append({'label': label[0].upper() + label[1:].lower(), 'number': article_number(label),
                             'page': page, 'heading_path': list(path.values()),
                             'lines': [m.group('rest')] if m.group('rest') else []})
        elif _DIVISION.match(line) and not tail:
            path[line.split()[0].lower()] = line
        elif articles and (tail or (k > last and _TAIL.match(line))):
            tail = True
        elif articles:
            articles[-1]['lines'].append(line)
    for a in articles:
        a['body'] = '\n'.join(_join(a.pop('lines'))).strip()
    return articles


def _join(lines: list[str]) -> list[str]:
    """The layer's lines joined into paragraphs: a line runs on unless it ends a sentence or the next one opens an
    item («– », «1° », «a) »)."""
    out: list[str] = []
    for line in lines:
        if out and not re.search(r'[.:;!?»]\s*$', out[-1]) and not re.match(r'^(?:[–—\-•]|\d+°|[a-z]\)|\d+\))', line):
            joined = out[-1][:-1] + line if out[-1].endswith('-') and line[:1].islower() else f'{out[-1]} {line}'
            out[-1] = joined
        else:
            out.append(line)
    return out


def arabic_uri(entry: dict) -> tuple[str, str]:
    """The Arabic text this entry translates: (its AKN URI, its normalised number). A law, decree or SGG-numbered
    order has one address from its kind and number, read or not; another text is the corpus's own of that kind and
    number, else the address the Arabic will get when it is read."""
    kind = entry['type'] if entry['type'] in TYPES else 'other'
    number = normalize_number(_number_in(entry['title']) or entry['number_as_printed'] or '')
    if works.numbered(kind, number, entry['number_as_printed']):
        return works.follow(works.address(kind, number)), number
    if number:
        found = Text.objects.filter(number=number, type=kind).order_by('id').first()
        if found:
            return found.akn_uri, number
    signed = _date(entry['signed_on_gregorian'])
    year = signed.year if signed else ''
    return (f'/akn/ma/act/{SUBTYPES.get(kind, "texte")}/{year}/{number}' if number and year else ''), number


def old_uri(issue: Issue, entry: dict, i: int) -> str:
    """The address of a text before 1956 that only the French Bulletin printed (A of the Bulletin-from-No.-1 review): no
    number then, so its kind, its French issue's day and number and its place there; «bofr» never meets an Arabic
    issue's own addresses («bo2266-2»)."""
    kind = entry['type'] if entry['type'] in TYPES else 'other'
    return f'/akn/ma/act/{SUBTYPES.get(kind, "texte")}/{issue.date}/bofr{issue.key}-{i + 1}'


@transaction.atomic
def load(issue: Issue, toc: list[dict], only: set[int] | None = None) -> dict:
    """Each contents entry's French text, beside its Arabic. Entries with no number (notices) are left out, but for an
    issue before 1956 whose `only` entries (those the Arabic edition never printed) are given their own addresses."""
    lines = issue_lines(issue)
    starts, after = [None] * len(toc), _contents_end(lines)
    for i in sorted(range(len(toc)), key=lambda i: (toc[i]['page'], i)):
        n = _start_of(lines, toc[i], after)
        starts[i] = n
        after = n + 1 if n is not None else after
    found = sorted(n for n in starts if n is not None) + [len(lines)]
    counts = {'texts': 0, 'articles': 0, 'not_found': 0, 'no_number': 0}
    # A reload replaces what this issue gave before.
    gone = list(FrenchText.objects.filter(issue_number=issue.number, issue_date=issue.date).values_list('text_uri', flat=True))
    FrenchArticle.objects.filter(text_uri__in=gone).delete()
    FrenchText.objects.filter(text_uri__in=gone).delete()
    for i, (entry, start) in enumerate(zip(toc, starts)):
        if only is not None:
            if i not in only:
                continue
            uri, number = old_uri(issue, entry, i), ''
        else:
            uri, number = arabic_uri(entry)
        if not uri:
            counts['no_number'] += 1
            continue
        if start is None:
            counts['not_found'] += 1
            continue
        end = min(m for m in found if m > start)
        part = lines[start:end]
        articles = split_articles(part)
        if not articles and len(part) > 1:
            # A text with no «Article» (a dahir naming a person): its words, one unnamed article, from the line that
            # names it again («Par dahir n° 1-25-39 …»): a title found in the contents brought their lines with it.
            again = next((k for k in range(1, len(part)) if number and number in part[k][1].replace('.', '-')), 1)
            articles = [{'label': '', 'number': '', 'page': part[again][0],
                         'body': '\n'.join(_join([line for _, line in part[again:]])).strip()}]
        FrenchText.objects.update_or_create(text_uri=uri, defaults={
            'type': entry['type'], 'number': number, 'title': entry['title'][:2000],
            'signed_on': _date(entry['signed_on_gregorian']), 'issue_number': issue.number,
            'issue_suffix': issue.suffix, 'issue_date': issue.date, 'document_sha': issue.document.sha256,
            'pages': f'{part[0][0]}-{part[-1][0]}'})
        FrenchArticle.objects.filter(text_uri=uri).delete()
        FrenchArticle.objects.bulk_create([
            FrenchArticle(text_uri=uri, order=k + 1, label=a['label'][:80], number=a['number'], body=a['body'],
                          printed_page=a['page']) for k, a in enumerate(articles)])
        Text.objects.filter(akn_uri=uri, title_fr='').update(title_fr=entry['title'][:2000])
        counts['texts'] += 1
        counts['articles'] += len(articles)
    return counts
