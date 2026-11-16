"""Every article in its text (FX6 of the mended-Bulletin review, 2 Nov 2026).

- `number_of` reads an article's number from its label whatever its spelling: the loader knew «الفصل الثاني», not
  the old print's «الفصل الثانى», so 25,307 published articles had no number (and their addresses went by position).
- `numbers` gives those articles their number; their addresses stay.
- `restore_first` gives a text its article 1 back from the page it was printed on (110 texts began at article 2: the
  1960 kif dahir paid «هذا التعويض» that its lost article 1 granted); `put_in_order` puts an article 1 found after
  article 2 first; `split_preamble` takes an article 1 out of the preamble. Their articles then take the addresses
  their numbers give (art_1 for article 1), and whatever is kept by an article's address (a correction, a report, a
  discussion, an explanation, a follow) moves with it."""
import re

from django.db import transaction
from django.db.models import F

from apps.corpus.models import Article, Version
from apps.corpus.services.issue_structure import ORDINALS, ordinal_value

_FOLD = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي', 'ة': 'ه'})
_ORDINALS = {k.translate(_FOLD): v for k, v in ORDINALS.items()}
_ORIGINAL = {k.translate(_FOLD): k for k in ORDINALS}
_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
_KIND = ('الفصل', 'الماده', 'البند', 'فصل', 'ماده')
FIRST = re.compile(r'(?m)^[ \t«"(]*(?:الفصل|الفصـل|المادة|المادة|البند)\s+(?:الأول|الاول|الأولى|الاولى|1)\b[^\n]{0,12}$')


def number_of(label: str) -> int | None:
    """«الفصل الثانى» → 2, «المادة 3» → 3, «الفصل الحادى عشر» → 11, «فصل فريد» → None."""
    digits = re.search(r'\d+', (label or '').translate(_DIGITS))
    if digits:
        return int(digits.group(0))
    words = (label or '').translate(_FOLD).split()
    if not words:
        return None
    rest = words[1:] if words[0] in _KIND else words
    if not rest:
        return None
    if ' '.join(rest) in _ORDINALS:
        return _ORDINALS[' '.join(rest)]
    return ordinal_value(' '.join(_ORIGINAL.get(w, w) for w in rest))


def numbers(write: bool = False) -> int:
    """Published articles whose label carries a number their row lacks: given it (their addresses stay)."""
    rows = []
    for a in Article.objects.filter(number='', version__consolidation='as_published').only('pk', 'label').iterator(
            chunk_size=5000):
        n = number_of(a.label)
        if n is not None:
            a.number = str(n) + ('-bis' if 'مكرر' in a.label else '')
            rows.append(a)
    if write:
        Article.objects.bulk_update(rows, ['number'], batch_size=2000)
    return len(rows)


def _paths_moved(text_path: str, moves: dict[str, str]) -> None:
    """What is kept by an article's address follows the article: the old address to the new, through a free name
    first so two articles can trade places."""
    from django.apps import apps
    if not moves:
        return
    tables = [('quality.Correction', ('path',)), ('quality.Report', ('path',)), ('discussion.Discussion', ('path',)),
              ('explain.Explanation', ('path',)), ('follows.Follow', ('path',))]
    for stage in ('park', 'land'):
        for label, fields in tables:
            try:
                model = apps.get_model(label)
            except LookupError:
                continue
            for field in fields:
                for old, new in moves.items():
                    src = f'{text_path}/{old}' if stage == 'park' else f'{text_path}/~{new}'
                    dst = f'{text_path}/~{new}' if stage == 'park' else f'{text_path}/{new}'
                    model.objects.filter(**{field: src}).update(**{field: dst})


def _readdress(version: Version) -> dict[str, str]:
    """The version's articles in order, each at the address its number gives (art_2 for «الفصل الثانى»); the
    moves made, old address → new."""
    from apps.corpus.services.addresses import text_path
    articles = list(version.articles.order_by('order'))
    moves, taken = {}, set()
    for k, a in enumerate(articles, 1):
        n = number_of(a.label) if a.eid != 'annex' else None
        eid = 'annex' if a.eid == 'annex' else f'art_{n if n is not None else k}'
        eid = eid if eid not in taken else f'{eid}_{k}'
        taken.add(eid)
        if a.eid != eid:
            moves[a.eid] = eid
        a.order, a.eid = k, eid
        if n is not None and not a.number:
            a.number = str(n)
    Article.objects.filter(pk__in=[a.pk for a in articles]).update(order=F('order') + 100_000)    # free orders
    for a in articles:
        Article.objects.filter(pk=a.pk).update(order=a.order, eid=a.eid, number=a.number)
    _paths_moved(text_path(version.text.akn_uri), moves)
    return moves


def _page_text(version: Version) -> str:
    """The text of the pages the version was printed on, in order."""
    from apps.sources.models import Page
    issue = version.text.first_published_in
    m = re.fullmatch(r'(\d+)-(\d+)', version.source_pages or '')
    if issue is None or not m:
        return ''
    low, high = int(m.group(1)) - 1, int(m.group(2))          # the page before too: a heading may end a column
    rows = Page.objects.filter(document=issue.document_id, printed_number__gte=low, printed_number__lte=high)
    return '\n'.join(rows.order_by('index').values_list('text', flat=True))


def _squash(text: str) -> str:
    return re.sub(r'\s+', ' ', text.translate(_FOLD)).strip()


def _folded(text: str) -> tuple[str, list[int]]:
    """`text` folded (hamza, ى, ة) with each run of spaces one space, and where each folded letter stands in `text`,
    so what is found folded is cut from the text as printed."""
    out, where, space = [], [], True
    for i, ch in enumerate(text):
        if ch.isspace():
            if not space:
                out.append(' ')
                where.append(i)
            space = True
            continue
        out.append(ch.translate(_FOLD))
        where.append(i)
        space = False
    return ''.join(out), where


def found_first(version: Version) -> tuple[str, str] | None:
    """Article 1 as printed before the version's first article: (label, body) in the page's own spelling, or None
    when the pages do not show it where it should stand (just before the first article's label)."""
    articles = list(version.articles.order_by('order')[:1])
    if not articles:
        return None
    pages = _page_text(version)
    first = articles[0]
    flat, where = _folded(pages)
    at = -1
    for size in (40, 24):           # a word put right on the page and not yet in the article: a shorter start
        head = _squash(first.body)[:size]
        at = flat.find(head) if len(head) >= 12 else -1
        if at >= 0:
            break
    if at < 0:
        return None
    label_at = flat.rfind(_squash(first.label), max(0, at - 200), at)
    end = label_at if label_at >= 0 else at
    base = max(0, end - 4000)
    hits = list(re.finditer(r'(?:الفصل|الفصـل|الماده|البند)\s+(?:الاول|الاولي|1)\b', flat[base:end]))
    if not hits:
        return None
    hit = hits[-1]
    a, b = base + hit.start(), base + hit.end()
    label = pages[where[a]:where[b - 1] + 1]
    body = pages[where[b]:where[end] if end < len(where) else len(pages)].strip(' :.-«"\n\t')
    if not (8 <= len(body) <= 3000) or re.search(r'(?:الفصل|المادة|الماده)\s+(?:الثاني|الثانى|الثالث|2|3)\b', body):
        return None
    return label.strip(), body


@transaction.atomic
def restore_first(version: Version) -> bool:
    """Article 1 put back before the first article, from its page; addresses then follow the numbers."""
    got = found_first(version)
    if got is None:
        return False
    label, body = got
    Article.objects.filter(version=version).update(order=F('order') + 100_000)    # room at the head
    for k, a in enumerate(version.articles.order_by('order', 'pk'), 2):
        Article.objects.filter(pk=a.pk).update(order=k)
    first = version.articles.order_by('order').first()
    Article.objects.create(version=version, order=1, label=label, number='1',
                           eid='art_1_restored', body=body, heading_path=first.heading_path if first else [],
                           printed_page=first.printed_page if first else None)
    _readdress(version)
    return True


@transaction.atomic
def put_in_order(version: Version) -> bool:
    """Articles in the order of their numbers when every one has a number (an article 1 found after article 2)."""
    articles = list(version.articles.order_by('order'))
    numbered = [(number_of(a.label), a) for a in articles if a.eid != 'annex']
    if any(n is None for n, _ in numbered):
        return False
    ordered = [a for _, a in sorted(numbered, key=lambda x: x[0])] + [a for a in articles if a.eid == 'annex']
    if ordered == articles:
        return False
    Article.objects.filter(version=version).update(order=F('order') + 100_000)
    for k, a in enumerate(ordered, 1):
        Article.objects.filter(pk=a.pk).update(order=k)
    _readdress(version)
    return True


@transaction.atomic
def split_preamble(version: Version) -> bool:
    """An article 1 the preamble swallowed («… قررنا ما يلي : الفصل الأول …») taken out as the first article."""
    m = list(FIRST.finditer(version.preamble or ''))
    if not m:
        inline = list(re.finditer(r'(?:الفصل|المادة)\s+(?:الأول|الاول|الأولى|الاولى|1)\b\s*[:.-]?', version.preamble or ''))
        if not inline:
            return False
        m = inline
    hit = m[-1]
    before, body = version.preamble[:hit.start()].rstrip(), version.preamble[hit.end():].strip(' :.-\n')
    if len(body) < 8:
        return False
    first = version.articles.order_by('order').first()
    Article.objects.filter(version=version).update(order=F('order') + 100_000)
    for k, a in enumerate(version.articles.order_by('order', 'pk'), 2):
        Article.objects.filter(pk=a.pk).update(order=k)
    Article.objects.create(version=version, order=1, label=hit.group(0).strip(' :.-\n'), number='1', eid='art_1_split',
                           body=body, heading_path=first.heading_path if first else [],
                           printed_page=first.printed_page if first else None)
    Version.objects.filter(pk=version.pk).update(preamble=before)
    _readdress(version)
    return True


def problems() -> dict[str, list[Version]]:
    """Published Arabic versions whose first article is not article 1: `missing` (article 1 nowhere), `late` (after
    article 2), `preamble` (inside the preamble)."""
    from django.db.models import OuterRef, Subquery
    first = Article.objects.filter(version=OuterRef('pk')).order_by('order')
    versions = (Version.objects.filter(consolidation='as_published', language='ar')
                .annotate(first_label=Subquery(first.values('label')[:1])).exclude(first_label__isnull=True)
                .only('pk', 'preamble', 'source_pages', 'text'))
    late = [v for v in versions.iterator(chunk_size=2000) if number_of(v.first_label) in (2, 3)]
    has_one = {vid for vid, label in Article.objects.filter(version__in=late).values_list('version_id', 'label')
               if number_of(label) == 1}
    out = {'missing': [], 'late': [], 'preamble': []}
    says_first = re.compile(r'(?:الفصل|المادة)\s+(?:الأول|الاول|الأولى|الاولى|1)\b')
    for v in late:
        out['late' if v.pk in has_one else 'preamble' if says_first.search(v.preamble or '') else 'missing'].append(v)
    return out
