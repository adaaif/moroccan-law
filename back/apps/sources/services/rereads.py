"""A second reading set beside the first (FX10 of the mended-Bulletin review, 2 Nov 2026, within a budget of $10). The
pages a re-reading would mend were read again by Haiku on another machine; here each new
reading is kept as a run of its page (variant «reread …») and weighed against the page's reading:

- the new reading holds the old one's words and many more (a column, an article the first reading never read): it
  becomes the page's reading;
- otherwise word by word, where the two disagree on one word: Latin letters glued to Arabic ones give way to the other
  reading's clean word; of two words one shape apart (dots), the common one stays when the other is seen at most a
  thousand times and it thirty times as often; two common words («ستة» and «سنة») are left to a person (a suspect,
  signal «reread»); two rare ones (names, mostly) are left as the first reading has them.
  The words put right go into the articles printed on the page too.

What comes out is a run of its own (engine «vote», variant «merged with a reread»), which choosing a page's reading
again keeps. Everything is found again from the stored runs, so `merge` can run again after a reload."""
import difflib
import re
from collections import Counter

from apps.quality.models import Suspect
from apps.quality.services.suspects import GLUED, fold, shape
from apps.sources.models import OcrRun, Page
from apps.sources.services.issue import clean_reading

_TOKEN = re.compile(r'\S+')
_ARABIC_WORD = re.compile(r'^[ء-ي]+$')


class Change:
    """One word put right: what the page read, what it reads now, the Arabic words on either side, and why."""

    def __init__(self, wrong: str, right: str, before: str, after: str, why: str):
        self.wrong, self.right, self.before, self.after, self.why = wrong, right, before, after, why


def _core(token: str) -> str:
    return token.strip('.,،؛:()[]«»"\'!?؟-')


def weigh(old: str, new: str, counts: Counter) -> tuple[str, list[Change], list[tuple[str, str, str]], bool]:
    """(the page's reading, the words put right, the words for a person: (word, other reading's word, context),
    whether the new reading, fuller, replaced the old)."""
    a, b = _TOKEN.findall(old), _TOKEN.findall(new)
    fa, fb = [fold(_core(w)) for w in a], [fold(_core(w)) for w in b]
    matched = sum(m.size for m in difflib.SequenceMatcher(None, fa, fb, autojunk=False).get_matching_blocks())
    fuller = len(fb) >= 1.15 * len(fa) and len(fb) - len(fa) >= 40 and matched >= 0.9 * len(fa)
    changes, doubts = [], []
    spans = [m.span() for m in _TOKEN.finditer(old)]
    out, last = [], 0
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, fa, fb, autojunk=False).get_opcodes():
        if op != 'replace' or a2 - a1 != b2 - b1:
            continue
        for i, j in zip(range(a1, a2), range(b1, b2)):
            wa, wb = _core(a[i]), _core(b[j])
            if not wa or not wb or not _ARABIC_WORD.match(re.sub(r'[ً-ْـ]', '', wb)):
                continue
            why = None
            if GLUED.search(a[i]) and not GLUED.search(b[j]):
                why = 'glued'
            elif shape(wa) == shape(wb) and fold(wa) != fold(wb):
                ca, cb = counts.get(fold(wa), 0), counts.get(fold(wb), 0)
                if (ca <= 2 and cb >= 20) or (ca <= 1000 and cb >= 30 * max(ca, 1)):
                    why = 'rare'            # «وسرقا» seen 38 times, «وشرقا» 167,164: the common word stays
                elif cb <= 1000 and ca >= 30 * max(cb, 1):
                    pass                    # the first reading's word is the common one: it stays
                elif ca >= 20 and cb >= 20:
                    # Two common words («ستة» and «سنة»: «بمقتضى ستة رسوم», six deeds): only a person can tell.
                    ctx = ' '.join(a[max(0, i - 4):i + 5])
                    doubts.append((a[i], wb, ctx))
                # Two rare words (most of them names): neither reading is worth a person's time over the other.
            if why:
                before = next((fold(_core(x)) and _core(x) for x in reversed(a[max(0, i - 3):i])
                               if _ARABIC_WORD.match(_core(x) or '-')), '')
                after = next((_core(x) for x in a[i + 1:i + 4] if _ARABIC_WORD.match(_core(x) or '-')), '')
                changes.append(Change(wa, wb, before, after, why))
                s, e = spans[i]
                out.append(old[last:s] + a[i].replace(wa, wb, 1))
                last = e
    out.append(old[last:])
    return (new if fuller else ''.join(out)), changes, doubts, fuller


def merge(page: Page, counts: Counter, write: bool = False) -> dict:
    """The page's latest re-reading weighed against its reading (see the module's docstring)."""
    from apps.corpus.models import Article, Version
    from apps.quality.models import Correction
    from apps.quality.services.corrections import put_right, reapply_pages
    runs = list(page.ocr_runs.exclude(text='').order_by('created_at'))
    reread = next((r for r in reversed(runs) if r.variant.startswith('reread')), None)
    if reread is None:
        return {}
    # The reading the page had before: its cover's vote (FX3), else the model's own reading, never a copy's or the
    # merge itself; so merging again finds the same words put right (and gives them back to articles a reload reset).
    first = (next((r for r in runs if r.engine == 'vote' and r.variant.startswith(('vote of', 'kept of'))), None)
             or next((r for r in reversed(runs) if r.engine != 'vote' and not r.variant.startswith(('copy ', 'reread'))
                      and not r.engine.startswith('tesseract')), None))
    old = clean_reading(first.text) if first else page.text
    text, changes, doubts, fuller = weigh(old, clean_reading(reread.text), counts)
    done = {'fuller': int(fuller), 'words': len(changes), 'doubts': len(doubts), 'articles': 0}
    if not write:
        return done
    page.text = text
    reapply_pages([page])
    Page.objects.filter(pk=page.pk).update(text=page.text)
    OcrRun.objects.filter(page=page, engine='vote', variant='merged with a reread').delete()
    OcrRun.objects.create(page=page, engine='vote', variant='merged with a reread', text=page.text)
    for word, other, ctx in doubts:
        Suspect.objects.get_or_create(page=page, word=word[:120], suggestion=other[:120], signal='reread',
                                      defaults={'context': ctx[:300]})
    issue = page.document.issue
    for v in Version.objects.filter(text__first_published_in=issue, consolidation='as_published'):
        m = re.fullmatch(r'(\d+)-(\d+)', v.source_pages or '')
        if not m or not (int(m.group(1)) <= (page.printed_number or -1) <= int(m.group(2))):
            continue
        for art in Article.objects.filter(version=v):
            body = art.body
            for c in changes:
                body = put_right(body, Correction(wrong=c.wrong, right=c.right, before=c.before, after=c.after))
            if body != art.body:
                Article.objects.filter(pk=art.pk).update(body=body)
                done['articles'] += 1
    return done
