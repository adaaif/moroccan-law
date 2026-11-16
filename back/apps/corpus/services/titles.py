"""A text's title as the BO heads it (H5 of the housing plan): «مرسوم رقم 2.23.350 صادر في فاتح جمادى الأولى 1445 (15
نوفمبر 2023) بتحديد أشكال إعانة الدولة…», not the model's shortened «بتحديد أشكال…», which named 1,690 texts by what
they do and made every citation of them read «المادة الثالثة من بتحديد…». The full heading is in the issue's own
reading: its table of contents, else the text's first line."""
import json
import re
from pathlib import Path

from django.conf import settings

# A heading opens with the text's kind.
KIND = re.compile(r'^(?:ال)?(?:مرسوم|قرار|ظهير|قانون|مقرر|منشور|دورية|أمر|قانون تنظيمي|قانون - إطار|قانون-إطار)\b')


# The words a heading of each kind opens with: a heading of another kind is the contents' slip, not the text's.
KIND_WORDS = {'decree': ('مرسوم', 'المرسوم'), 'decree_law': ('مرسوم', 'المرسوم'), 'decision': ('قرار', 'مقرر', 'القرار', 'المقرر'),
              'order': ('قرار', 'مقرر', 'القرار', 'المقرر'), 'dahir': ('ظهير', 'الظهير'), 'law': ('قانون', 'القانون'),
              'organic_law': ('قانون', 'القانون')}


def headed(title: str) -> bool:
    return bool(KIND.match((title or '').strip()))


def full_title(title: str, toc_title: str = '', front: str = '', number: str = '') -> str:
    """The title with its heading: the model's, if it has one; else the contents' or the first line's, when that one
    is headed, names the text's number and ends with what the model read."""
    if headed(title):
        return title
    core = re.sub(r'[\s.،]+$', '', ' '.join((title or '').split()))
    for candidate in (toc_title, (front or '').split('\n')[0]):
        whole = re.sub(r'[\s.]+$', '', ' '.join((candidate or '').split()))
        # Named by its number, the heading is the text's own, even where the model reworded what follows it.
        if headed(whole) and (number in whole if number else (not core or core[:40] in whole)):
            return whole
    return title


def restore(log=print, write: bool = False) -> dict:
    """Puts the heading back on every text read from a BO issue whose stored title lacks it."""
    from apps.corpus.models import Text

    counts = {'unheaded': 0, 'restored': 0, 'no_heading_found': 0}
    cache: dict = {}
    examples = []
    for text in Text.objects.filter(first_published_in__isnull=False).select_related('first_published_in').iterator():
        if headed(text.title_ar):
            continue
        counts['unheaded'] += 1
        key = text.first_published_in.key
        if key not in cache:
            path = Path(settings.CORPUS_DIR) / 'reports' / 'issues' / key / 'texts.json'
            data = json.loads(path.read_text()) if path.exists() else {}
            cache[key] = data.get('texts', data) if isinstance(data, dict) else data
        found = None
        for item in cache[key] or []:
            toc, data = item.get('toc') or {}, item.get('data') or {}
            printed = data.get('number_as_printed') or toc.get('number_as_printed') or ''
            if printed and printed == text.number_as_printed and (data.get('title') or '').strip(' .') == text.title_ar.strip(' .'):
                found = full_title(text.title_ar, toc.get('title', ''), item.get('front', ''), printed)
                break
        if not found or found == text.title_ar:
            counts['no_heading_found'] += 1
            continue
        if text.type in KIND_WORDS and not found.startswith(KIND_WORDS[text.type]):
            counts['kind_differs'] = counts.get('kind_differs', 0) + 1
            continue
        counts['restored'] += 1
        if len(examples) < 8:
            examples.append((text.akn_uri, found[:110]))
        if write:
            text.title_ar = found[:500]
            text.save(update_fields=['title_ar', 'updated_at'])
    for uri, title in examples:
        log(f'  {uri}: {title}')
    return counts


# ── A title's subject: what the text is about, without the kind, number and date its row already shows ────────────────
_LEAD_LAW = re.compile(r'^\s*(?:ال)?(?:قانون(?:\s*-?\s*إطار)?(?:\s+تنظيمي)?|مرسوم ملكي|مرسوم بقانون)\s+رقم\s*[\d.\s]+\d\s*(?:بمثابة\s+قانون\s*)?')
_LEAD_DAHIR = re.compile(r'^\s*(?:ال)?ظهير(?:\s+(?:ال)?شريف)?(?:\s+(?:معتبر\s+|يعتبر\s+)?بمثابة\s+قانون)?(?:\s+رقم\s*[\d.\s]+\d)?'
                         r'(?:\s+(?:معتبر\s+|يعتبر\s+)?بمثابة\s+قانون)?\s*')
_SIGNED = re.compile(r'^\s*(?:ال)?(?:صادر|مؤرخ|مورخ|موءرخ)\s+(?:في|بتاريخ)\s+.{4,60}?\(\s*\d{1,2}\s+\S+\s+\d{4}\s*\)\s*'
                     r'|^\s*بتاريخ\s+.{4,60}?\(\s*\d{1,2}\s+\S+\s+\d{4}\s*\)\s*')
_AS_LAW = re.compile(r'^\s*(?:(?:معتبر\s+|يعتبر\s+)?بمثابة\s+قانون\s*)')
_ABOUT = re.compile(r'^\s*(?:(?:ال)?متعلق(?:ة)?\s+ب|يتعلق\s+ب|تتعلق\s+ب|في\s+شأن\s+|فى\s+شأن\s+|بشأن\s+)(?=\S)')
# The first heading a title swallowed («… يتعلق بالجماعات قسم تمهيدي أحكام عامة»: 14 titles on 10 Nov 2026).
_SWALLOWED = re.compile(r'\s+(?:(?:قسم|باب|كتاب)\s+تمهيدي|(?:ال)?ـ?(?:قسم|باب|فصل)\s+الأول)?\s*(?:أحكام|احكام|مقتضيات)\s+عامة\s*$')


def subject(title: str, most: int = 96) -> str:
    """What a law or a dahir is about, as its title says it once the kind, the number and the date are taken off:
    «قانون رقم 43.20 يتعلق بخدمات الثقة بشأن المعاملات الإلكترونية» → «خدمات الثقة بشأن المعاملات الإلكترونية». Cut by
    words; the whole title when nothing is left of it."""
    whole = ' '.join((title or '').split())
    rest = _LEAD_LAW.sub('', whole, count=1)
    if rest == whole:
        rest = _LEAD_DAHIR.sub('', whole, count=1)
    rest = _AS_LAW.sub('', _SIGNED.sub('', rest, count=1), count=1)
    about = _ABOUT.sub('', rest, count=1)
    if about != rest and len(about) >= 8:
        rest = about
    # A title that ran on into the text's opening («… الدفاع الوطني. الحمد لله وحده …») stops where the title did.
    rest = re.split(r'\s*[.،]?\s+الحمد\s+لله', rest, maxsplit=1)[0]
    rest = _SWALLOWED.sub('', rest).strip(' ،.:-')
    if len(rest) < 8:
        rest = _SWALLOWED.sub('', whole).strip(' ،.:-')
    if len(rest) <= most:
        return rest
    cut = rest[:most]
    return (cut[:cut.rfind(' ')] if ' ' in cut else cut).rstrip('،, ') + '…'
