"""Every fault the mended-Bulletin review found in the Bulletin's data, counted (FX1, 2 Nov 2026). The faults were found by
hand, one story at a time; this counts them all, so each fix shows its count before and after, and a load that brings
one back is seen (`manage.py data_health --baseline`). It only reads.

Each check returns a `Check`: its name, its count, a few examples to look at, and what the count means."""
import re
from collections import defaultdict
from dataclasses import dataclass, field

from django.db.models import Count, F, Max, OuterRef, Subquery

from apps.corpus.models import Article, Text, Version
from apps.corpus.services.issue_structure import ORDINALS, ordinal_value
from apps.sources.models import Issue, Page
from apps.sources.services import remarks

SAMPLE = 8


@dataclass
class Check:
    name: str
    count: int
    means: str
    sample: list[str] = field(default_factory=list)


_FOLD = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي', 'ة': 'ه'})
_ORDINALS = {k.translate(_FOLD): v for k, v in ORDINALS.items()}


def article_value(label: str) -> int | None:
    """An article's number from its label as printed, whatever its spelling: «الفصل الثانى» → 2, «المادة 3» → 3,
    «الفصل الحادى عشر» → 11; None for a label with no number («فصل فريد»)."""
    words = label.translate(_FOLD).split()
    if not words:
        return None
    digits = re.search(r'\d+', label.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
    if digits:
        return int(digits.group(0))
    rest = ' '.join(words[1:]) if words[0] in ('الفصل', 'الماده', 'البند', 'المادة', 'فصل', 'ماده') else ' '.join(words)
    if rest in _ORDINALS:
        return _ORDINALS[rest]
    folded = {k.translate(_FOLD): k for k in list(ORDINALS)}
    return ordinal_value(' '.join(folded.get(w, w) for w in rest.split())) if rest else None


def copies() -> Check:
    """Issues stored from one file under several numbers (a cover that bears two numbers or more) and not yet folded
    into their cover: same edition, same file size, same page count."""
    groups = defaultdict(list)
    for key, edition, size, pages in Issue.objects.filter(copy_of__isnull=True, document__isnull=False).values_list(
            'number', 'edition', 'document__bytes', 'document__page_count').order_by('number'):
        groups[(edition, size, pages)].append(key)
    extra = [(e, ns) for (e, _, _), ns in groups.items() if len(ns) > 1]
    return Check('copies', sum(len(ns) - 1 for _, ns in extra),
                 'issues stored from another issue\'s file and not folded into it',
                 [f'{e} {ns[0]} ×{len(ns)}' for e, ns in sorted(extra, key=lambda x: -len(x[1]))[:SAMPLE]])


def page_one() -> tuple[Check, Check]:
    """Mid-year issues stored as starting on page 1: «wrong» when the issues before and after run past them (the
    previous one ends after page 1, the next starts after that), «unclear» otherwise. A year's first issue starts at 1."""
    span = {d: (n, last) for d, n, last in Page.objects.values('document').annotate(
        n=Count('pk'), last=Max('printed_number')).values_list('document', 'n', 'last')}
    by_year = defaultdict(list)
    for row in Issue.objects.filter(copy_of__isnull=True, document__isnull=False).values_list(
            'pk', 'edition', 'number', 'suffix', 'date', 'first_page_number', 'document').order_by('date', 'number', 'suffix'):
        by_year[(row[1], row[4].year)].append(row)
    wrong, unclear = [], []
    for rows in by_year.values():
        for k, (_pk, edition, number, suffix, _day, first, doc) in enumerate(rows):
            if first != 1 or k == 0:
                continue
            prev_last = span.get(rows[k - 1][6], (0, None))[1]
            nxt = rows[k + 1][5] if k + 1 < len(rows) else None
            key = f'{number}-{suffix}' if suffix else str(number)
            if prev_last and prev_last > 1 and nxt and nxt > prev_last:
                wrong.append(f'{edition} {key}')
            elif not (nxt is not None and nxt <= span.get(doc, (0, 0))[0] + 3):     # a volume that starts here
                unclear.append(f'{edition} {key}')
    return (Check('page_one', len(wrong), 'mid-year issues stored as starting on page 1, their neighbours running past '
                  'them', wrong[:SAMPLE]),
            Check('page_one_unclear', len(unclear), 'mid-year issues stored as starting on page 1, neighbours unclear',
                  unclear[:SAMPLE]))


# A cheap first sieve before `remarks.found` reads a page: Latin words, or the Arabic words its remarks use.
_SIEVE = r'[A-Za-z]{3,}|ملاحظة|غير مقروء|غير واضح|تعذر|لم أستطع|نُقل|يُنقل'
_MIXED = re.compile(r'\S*(?:[ء-ي][A-Za-z]{2,}|[A-Za-z]{2,}[ء-ي])\S*')


def readings() -> list[Check]:
    """Pages and published articles that still hold the reading model's remarks, and Arabic pages with a word that
    runs Arabic and Latin letters together (what a failed attempt leaves: «شعباeffective»)."""
    pages, mixed, page_ids = 0, 0, []
    mixed_ids = []
    rows = Page.objects.filter(text__regex=_SIEVE).values_list(
        'pk', 'text', 'document__issue__edition', 'document__issue__number', 'index')
    for _pk, text, edition, number, index in rows.iterator(chunk_size=500):
        if remarks.found(text):
            pages += 1
            if len(page_ids) < SAMPLE:
                page_ids.append(f'{edition} {number}·{index}')
        if edition and edition.endswith('_ar') and _MIXED.search(text):
            mixed += 1
            if len(mixed_ids) < SAMPLE:
                mixed_ids.append(f'{edition} {number}·{index}: {_MIXED.search(text).group(0)[:30]}')
    articles, article_paths = 0, []
    arts = Article.objects.filter(body__regex=_SIEVE, version__consolidation__in=('as_published', 'translation')
                                  ).values_list('body', 'eid', 'version__text__akn_uri')
    for body, eid, uri in arts.iterator(chunk_size=500):
        if remarks.found(body):
            articles += 1
            if len(article_paths) < SAMPLE:
                article_paths.append(f'{uri}#{eid}')
    return [Check('remarks_pages', pages, 'page readings that still hold the reading model\'s remarks', page_ids),
            Check('remarks_articles', articles, 'published articles that still hold the model\'s remarks', article_paths),
            Check('mixed_words', mixed, 'Arabic pages with a word of Arabic and Latin letters run together', mixed_ids)]


def articles() -> list[Check]:
    """Published Arabic texts whose first article is not article 1: missing everywhere, present but after article 2,
    or inside the preamble («الفصل الأول» before the first article)."""
    first = Article.objects.filter(version=OuterRef('pk')).order_by('order')
    versions = (Version.objects.filter(consolidation='as_published', language='ar')
                .annotate(first_label=Subquery(first.values('label')[:1]))
                .exclude(first_label__isnull=True).values_list('pk', 'first_label', 'preamble', 'text__akn_uri'))
    late = {}
    for pk, label, preamble, uri in versions.iterator(chunk_size=2000):
        if article_value(label) in (2, 3):
            late[pk] = (uri, preamble)
    has_one = set()
    for vid, label in Article.objects.filter(version_id__in=list(late)).values_list('version_id', 'label'):
        if article_value(label) == 1:
            has_one.add(vid)
    first_in_preamble = re.compile(r'(?:الفصل|المادة)\s+(?:الأول|الاول|الأولى|الاولى|1)\b')
    missing, after, in_preamble = [], [], []
    for vid, (uri, preamble) in late.items():
        (after if vid in has_one else in_preamble if first_in_preamble.search(preamble or '') else missing).append(uri)
    return [Check('first_article_missing', len(missing), 'published texts starting at article 2 or 3, article 1 '
                  'nowhere', missing[:SAMPLE]),
            Check('first_article_late', len(after), 'published texts whose article 1 comes after article 2',
                  after[:SAMPLE]),
            Check('first_article_in_preamble', len(in_preamble), 'published texts whose article 1 sits in the preamble',
                  in_preamble[:SAMPLE])]


_BARE = re.compile(r'^\s*(?:ظهير شريف|ظهير|قرار وزيري|قرار|مرسوم|مرسوم ملكي|قرار مشترك|منشور)\s*\.?\s*$')


def texts() -> list[Check]:
    """Texts that show a title and almost nothing (a published version with no article and under 200 letters of
    preamble); texts dated after the issue that published them; titles that are only the text's kind; two texts with
    one title in one issue, both read from the Bulletin."""
    empty = list(Version.objects.filter(consolidation='as_published').annotate(n=Count('articles'))
                 .filter(n=0).values_list('text__akn_uri', 'preamble'))
    empty = [uri for uri, preamble in empty if len(preamble or '') < 200]
    after = list(Text.objects.filter(first_published_in__isnull=False, signed_on__isnull=False)
                 .filter(signed_on__gt=F('first_published_in__date')).values_list('akn_uri', flat=True))
    bare = [uri for uri, title in Text.objects.filter(title_ar__regex=r'^\s*\S+(\s+\S+)?\s*\.?\s*$')
            .values_list('akn_uri', 'title_ar') if _BARE.match(title)]
    from apps.corpus.services.records import twins as twin_texts
    twins = [[gone, kept] for gone, kept in twin_texts(write=False)]       # what mend_records would fold
    return [Check('title_only', len(empty), 'texts with a title and almost nothing under it', empty[:SAMPLE]),
            Check('dated_after_issue', len(after), 'texts signed after the issue that published them', after[:SAMPLE]),
            Check('bare_titles', len(bare), 'titles that are only the text\'s kind («ظهير شريف»)', bare[:SAMPLE]),
            Check('twin_texts', len(twins), 'one printed text cut twice in an issue (what mend_records folds)',
                  [' → '.join(u) for u in twins[:SAMPLE]])]


def run(only: set[str] | None = None) -> list[Check]:
    """Every check (or those named in `only`: copies, pages, readings, articles, texts)."""
    out: list[Check] = []
    if not only or 'copies' in only:
        out.append(copies())
    if not only or 'pages' in only:
        out.extend(page_one())
    if not only or 'readings' in only:
        out.extend(readings())
    if not only or 'articles' in only:
        out.extend(articles())
    if not only or 'texts' in only:
        out.extend(texts())
    return out
