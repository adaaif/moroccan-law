"""Words a reading may have wrong, found for free (FX9 of the mended-Bulletin review, 2 Nov 2026). Most misreadings stay
invisible until someone reads the page; four signals point at likely ones, for a person to confirm on the image:

- `rare`: a word found once in the whole Bulletin whose dotted neighbour (same letter shapes, other dots) is common:
  «التنبخ» beside «التبغ» is a shape apart, but «الحيزة» beside «الخبزة», «الحدام» beside «الخدام» are dots apart;
- `copies`: the readings of a cover and its copies (FX3) read a word with other dots;
- `glued`: Latin letters glued to Arabic ones, what a failed attempt leaves («شعباeffective»);
- `tesseract`: Tesseract's Arabic reading of the page reads the word's dots otherwise.

A real word read as another real word («يمنع» for «يمنح») escapes `rare`; only the other readings and a person see it.
`confirm` puts a flagged word right in its page and in the articles printed there, each a correction recorded against
the page's image, applied again at every reload."""
import difflib
import re
from collections import Counter, defaultdict

from django.db import transaction
from django.utils import timezone

from apps.quality.models import Correction, Suspect
from apps.sources.models import Page

_MARKS = re.compile(r'[ً-ْـ]')
_FOLD = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ة': 'ه', 'ؤ': 'و', 'ئ': 'ي'})
# Letters that differ by their dots only: one shape each.
_RASM = str.maketrans({'ب': 'ٮ', 'ت': 'ٮ', 'ث': 'ٮ', 'ن': 'ٮ', 'ي': 'ٮ', 'ج': 'ح', 'خ': 'ح', 'ذ': 'د', 'ز': 'ر',
                       'ش': 'س', 'ض': 'ص', 'ظ': 'ط', 'غ': 'ع', 'ق': 'ڡ', 'ف': 'ڡ'})
_ARABIC = re.compile(r'[ء-ي]+')
_TOKEN = re.compile(r'\S+')
GLUED = re.compile(r'[ء-ي]+[A-Za-z]{2,}\S*|[A-Za-z]{2,}[ء-ي]+\S*')


def fold(word: str) -> str:
    return _MARKS.sub('', word).translate(_FOLD)


def shape(word: str) -> str:
    """The word without its dots: words of one shape differ only by their dots."""
    return fold(word).translate(_RASM)


def vocabulary(pages=None) -> Counter:
    """How often each folded Arabic word stands in the pages' readings (every Arabic page when none are given)."""
    counts = Counter()
    rows = pages if pages is not None else Page.objects.filter(document__issue__edition='general_ar')
    for text in rows.values_list('text', flat=True).iterator(chunk_size=2000):
        counts.update(fold(w) for w in _ARABIC.findall(_MARKS.sub('', text or '')))
    return counts


def neighbours(counts: Counter, least: int = 50) -> dict[str, list[tuple[str, int]]]:
    """For each shape, its common words (seen `least` times or more), most common first."""
    out = defaultdict(list)
    for w, n in counts.items():
        if n >= least and len(w) >= 3:
            out[shape(w)].append((w, n))
    for v in out.values():
        v.sort(key=lambda x: -x[1])
    return out


def _context(text: str, start: int, end: int) -> tuple[str, str, str]:
    before = text[max(0, start - 60):start].split()
    after = text[end:end + 60].split()
    return (' '.join(before[-4:] + [text[start:end]] + after[:4]), before[-1] if before else '',
            after[0] if after else '')


def rare(pages, counts: Counter, common: dict) -> list[Suspect]:
    """Words seen once whose dotted neighbour is seen a hundred times as often, one or two letters apart."""
    out = []
    for page in pages:
        for m in _ARABIC.finditer(page.text or ''):
            w = fold(m.group(0))
            if len(w) < 3 or counts.get(w, 0) > 1:
                continue
            for cand, n in common.get(shape(w), [])[:3]:
                if cand == w or len(cand) != len(w) or n < 100 * max(1, counts.get(w, 0)):
                    continue
                if sum(a != b for a, b in zip(cand, w)) <= 2:
                    ctx, _, _ = _context(page.text, m.start(), m.end())
                    out.append(Suspect(page=page, word=m.group(0)[:120], suggestion=cand[:120], context=ctx[:300],
                                       signal=Suspect.Signal.RARE, evidence={'seen': counts.get(w, 0), 'neighbour': n}))
                    break
    return out


def glued(pages) -> list[Suspect]:
    """Words of Arabic and Latin letters run together: what a failed attempt leaves."""
    out = []
    for page in pages:
        for m in GLUED.finditer(page.text or ''):
            ctx, _, _ = _context(page.text, m.start(), m.end())
            out.append(Suspect(page=page, word=m.group(0)[:120], context=ctx[:300], signal=Suspect.Signal.GLUED))
    return out


def copies() -> list[Suspect]:
    """Words a copy's reading of the same page (FX3) reads with other dots than the page's reading."""
    out = []
    pages = Page.objects.filter(ocr_runs__variant__startswith='copy ').distinct()
    for page in pages.prefetch_related('ocr_runs'):
        mine = _TOKEN.findall(page.text or '')
        folded = [fold(w) for w in mine]
        others = defaultdict(Counter)
        for run in page.ocr_runs.all():
            if not run.variant.startswith('copy ') or not run.text:
                continue
            theirs = _TOKEN.findall(run.text)
            for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, folded, [fold(w) for w in theirs],
                                                               autojunk=False).get_opcodes():
                if op == 'replace' and a2 - a1 == b2 - b1:
                    for i, j in zip(range(a1, a2), range(b1, b2)):
                        if shape(mine[i]) == shape(theirs[j]) and folded[i] != fold(theirs[j]):
                            others[i][theirs[j]] += 1
        text = page.text or ''
        spans = [m.span() for m in _TOKEN.finditer(text)]
        for i, alt in others.items():
            word, n = alt.most_common(1)[0]
            ctx, _, _ = _context(text, *spans[i])
            out.append(Suspect(page=page, word=mine[i][:120], suggestion=word[:120], context=ctx[:300],
                               signal=Suspect.Signal.COPIES, evidence={'readings': n}))
    return out


def tesseract(pages, counts: Counter) -> list[Suspect]:
    """Words Tesseract's Arabic reading of the page reads with other dots, when the reading's word is rare in the
    Bulletin (twice at most) and Tesseract's common (fifty times or more): Tesseract alone misreads more than the model
    (a sample of 30 pages gave 17 flags a page, most its own errors). A page at a time; slow: run at night."""
    import subprocess
    import tempfile
    from pathlib import Path

    from apps.sources.services.render import _render
    out = []
    for page in pages:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'page.png'
            _render(page, 2000).save(path)
            seen = subprocess.run(['tesseract', str(path), 'stdout', '-l', 'ara', '--psm', '3'],
                                  capture_output=True, text=True, timeout=300).stdout
        mine = _TOKEN.findall(page.text or '')
        theirs = _TOKEN.findall(seen)
        folded = [fold(w) for w in mine]
        spans = [m.span() for m in _TOKEN.finditer(page.text or '')]
        for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, folded, [fold(w) for w in theirs],
                                                           autojunk=False).get_opcodes():
            if op == 'replace' and a2 - a1 == b2 - b1:
                for i, j in zip(range(a1, a2), range(b1, b2)):
                    if (len(folded[i]) >= 3 and shape(mine[i]) == shape(theirs[j]) and folded[i] != fold(theirs[j])
                            and counts.get(folded[i], 0) <= 2 and counts.get(fold(theirs[j]), 0) >= 50):
                        ctx, _, _ = _context(page.text, *spans[i])
                        out.append(Suspect(page=page, word=mine[i][:120], suggestion=theirs[j][:120],
                                           context=ctx[:300], signal=Suspect.Signal.TESSERACT))
    return out


def prune() -> int:
    """Open suspects whose word no longer stands on their page (a re-reading or a correction put it right): out of the
    queue, so a person never weighs a word that is gone. Returns how many went."""
    gone = []
    for pk, word, text in Suspect.objects.filter(status=Suspect.Status.OPEN).values_list('pk', 'word', 'page__text') \
            .iterator(chunk_size=5000):
        if word not in (text or ''):
            gone.append(pk)
    for i in range(0, len(gone), 5000):
        Suspect.objects.filter(pk__in=gone[i:i + 5000]).delete()
    return len(gone)


@transaction.atomic
def confirm(suspect: Suspect, user=None) -> int:
    """The suggestion put in place in the page and in the articles printed on it, each recorded as a correction
    read against the page's image. Returns how many articles changed."""
    from apps.corpus.models import Version
    from apps.corpus.services.addresses import article_path
    from apps.quality.services.corrections import page_path, put_right
    if not suspect.suggestion:
        raise ValueError('a suspect with no suggestion is put right by hand')
    page = suspect.page
    issue = page.document.issue
    from apps.quality.services.corrections import WORD
    # Its neighbours as the correction finds them: the Arabic words on either side (figures are not words there).
    words = WORD.findall(suspect.context)
    k = next((i for i, w in enumerate(words) if w == suspect.word), None)
    before = words[k - 1] if k else ''
    after = words[k + 1] if k is not None and k + 1 < len(words) else ''
    evidence = {'suspect': suspect.pk, 'signal': suspect.signal, 'read_on': str(timezone.now().date())}
    c, _ = Correction.objects.get_or_create(
        path=page_path(issue, page.index), wrong=suspect.word, right=suspect.suggestion, before=before, after=after,
        defaults={'source': Correction.Source.PAGE, 'status': Correction.Status.APPLIED, 'decided_at': timezone.now(),
                  'decided_by': user, 'evidence': evidence})
    text = put_right(page.text, c)
    if text != page.text:
        Page.objects.filter(pk=page.pk).update(text=text)
    changed = 0
    for v in Version.objects.filter(text__first_published_in=issue, consolidation='as_published').select_related('text'):
        m = re.fullmatch(r'(\d+)-(\d+)', v.source_pages or '')
        if not m or not (int(m.group(1)) <= (page.printed_number or -1) <= int(m.group(2))):
            continue
        for a in v.articles.filter(body__contains=suspect.word):
            body = put_right(a.body, Correction(wrong=suspect.word, right=suspect.suggestion, before=before, after=after))
            if body == a.body:
                continue        # the word stands there between other neighbours: not the place read on the page
            Correction.objects.get_or_create(
                path=article_path(v.text.akn_uri, a.eid), wrong=suspect.word, right=suspect.suggestion, before=before,
                after=after, defaults={'source': Correction.Source.PAGE, 'status': Correction.Status.APPLIED,
                                       'decided_at': timezone.now(), 'decided_by': user, 'evidence': evidence})
            a.body = body
            a.save(update_fields=['body'])
            changed += 1
    Suspect.objects.filter(pk=suspect.pk).update(status=Suspect.Status.CONFIRMED, decided_by=user,
                                                 decided_at=timezone.now())
    return changed
