"""«أرضي فالجريدة الرسمية» (M8–M10 of the land review, 26 Oct 2026): the BO's land texts read as places and plots.

Since 2019 the BO prints, every week, the decrees that declare a public utility and expropriate plots, renew a
declaration, approve an administrative delimitation of collective or state land, extend a zone of collective
registration, align a commune's roads, take a plot out of the forest or move one between the state's domains. Each
names a commune and a province, often a property («المدعو "المحطة"») and a title or requisition number, and most of the
expropriations carry a table of plots with their owners as printed. People learn from these pages that their land is
concerned, and a search box finds them badly (a commune's name is in hundreds of texts; a row of a table is not an
article). Here each text becomes a place's entry: its kind (by its title's own formula), its communes, provinces,
properties and numbers, and its table's rows, kept by address (the text's AKN URI and the row), never a foreign key, so
a reload of the corpus only means building again (`manage.py build_land_places`, $0).

The tables are read by code from what the OCR wrote; nothing is checked yet (owner-provisional): the finder waits for a
person to read a sample of rows (C2 «names»: the owners' names are searchable as printed, since the law publishes them so
owners learn, 7.81 ch. 8 and 10)."""
import re

from django.db import transaction

from apps.sources.services.compare import fold

# A text's kind, by its title's own formula, in this order (a renewal also says «المنفعة العامة»).
KINDS = [
    ('renewal', ('بتجديد إعلان المنفعة العامة',)),
    ('forest', ('النظام الغابوي', 'الملك الغابوي')),
    ('road', ('تخطيط حدود الطرق',)),
    ('expropriation', ('نزع ملكية', 'نزع الملكية', 'المراد نزع')),
    ('utility', ('المنفعة العامة',)),
    ('occupation', ('الاحتلال المؤقت',)),
    ('delimitation', ('التحديد الإداري',)),
    ('collective', ('التحفيظ الجماعي',)),
    ('plan', ('تصميم التهيئة', 'تصاميم التهيئة')),
    ('domain', ('بضم قطعة', 'بضم قطع', 'بإخراج قطعة', 'إلى ملكها العمومي', 'إلى الملك العمومي')),
]
TYPES = ('decree', 'order', 'decision', 'dahir', 'other')
SINCE = '2019-01-01'

# Words that end a place's name: what follows a commune or a province in a title.
_STOP = r'(?=\s+(?:ب?إقليم|ب?عمالة|بقيادة|بدائرة|بجهة|التابع|التابعة|الكائن|الكائنة|وذلك|قصد|من\s+أجل|لفائدة|و?بنزع|و?بتعيين|المبين|المبينة|المرسومة)\b|[،,.()«»:؛]|$)'
_COMMUNE = re.compile(r'(?:ب|لل|ل)?(?:الجماعة\s+الترابية|الجماعة\s+القروية|الجماعة\s+الحضرية|جماعة)\s+(?!السلالية|النواب)([^\s،,.()«»:؛]+(?:\s+[^\s،,.()«»:؛]+){0,3}?)' + _STOP)
_PROVINCE = re.compile(r'(?:ب)?(?:إقليم|عمالة)\s+([^\s،,.()«»:؛]+(?:\s*-\s*[^\s،,.()«»:؛]+)?(?:\s+[^\s،,.()«»:؛]+){0,2}?)' + _STOP)
_PROPERTY = re.compile(r'(?:المدعو|المدعوة|المسمى|المسماة|المدعوين)\s*[«"]([^»"]{2,60})[»"]')
_REF = re.compile(r'(?:الرسم\s+العقاري|الرسوم\s+العقارية|رسم\s+عقاري|مطلب\s+التحفيظ|المطلب|مطلب)\s*(?:عدد|رقم)?\s*([0-9A-Za-z][0-9A-Za-z]*(?:\s*/\s*[0-9A-Za-z]+)+|\d{2,})')
_NOT_COMMUNE = {'السلالية', 'النواب', 'الترابية', 'المعنية', 'المذكورة'}


def kind_of(title: str) -> str | None:
    for kind, words in KINDS:
        if any(w in title for w in words):
            return kind
    return None


def compact(ref: str) -> str:
    """A title or requisition number without its spaces and slashes, as typed or printed: «F/18820» → «f18820»."""
    return re.sub(r'[\s/\-]', '', ref).lower()


def _clean(name: str) -> str:
    return ' '.join(name.replace('ـ', '').split()).strip(' -')


def places_in(text: str) -> tuple[list[str], list[str]]:
    """The communes and provinces a text names, in order, once each."""
    communes = [c for c in (_clean(m.group(1)) for m in _COMMUNE.finditer(text)) if c and c.split()[0] not in _NOT_COMMUNE]
    provinces = [p for p in (_province(_clean(m.group(1))) for m in _PROVINCE.finditer(text)) if p]
    return _once(communes), _once(provinces)


# A province's name is one word, «X - Y», or two words when the first is one of these («سيدي قاسم», «بني ملال»).
_TWO = {'سيدي', 'مولاي', 'بني', 'قلعة', 'الدار', 'عين', 'الفقيه', 'أولاد', 'وادي', 'الحي', 'جرادة', 'تاوريرت'}


def _province(name: str) -> str:
    if ' - ' in name:
        a, _, b = name.partition(' - ')
        return f'{a.split()[-1]} - {b.split()[0]}' if a and b else name
    words = name.split()
    return ' '.join(words[:2]) if len(words) > 1 and words[0] in _TWO else (words[0] if words else '')


def _once(names: list[str]) -> list[str]:
    """Each name once, a copy with a clinging «و» or «ل» («واومانة», «لطنجة») folded into the name it repeats."""
    names = list(dict.fromkeys(names))
    return [n for n in names if not (n[0] in 'ول' and n[1:] in names)]


# A table's columns, by the words of its header cells.
COLUMNS = [
    ('plot', ('رقم القطعة', 'رقم انقطعة', 'رقم القطع', 'رقم الأرض', 'رقم البقعة', 'رقم')),
    ('owners', ('أسماء الملاك', 'اسم المالك', 'الملاك', 'المالك')),
    ('area', ('المساحة',)),
    ('notes', ('ملاحظات',)),
    ('property', ('تعيين الملك', 'اسم الملك', 'الملك', 'المرجع العقاري', 'الرسم العقاري', 'نوع العقار', 'العقار')),
]


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip('|').split('|')]


def _header(cells: list[str]) -> dict[int, str] | None:
    """The columns a header row names, or None when the row is not a header."""
    out: dict[int, str] = {}
    for i, cell in enumerate(cells):
        for key, words in COLUMNS:
            if key not in out.values() and any(w in cell for w in words):
                out[i] = key
                break
    return out if len(out) >= 2 and 'owners' in out.values() else None


def rows_in(body: str) -> list[dict]:
    """The rows of a text's tables of plots: plot, property, title or requisition, area, owners as printed, notes."""
    out, columns = [], None
    for line in body.splitlines():
        if not line.lstrip().startswith('|'):
            continue
        cells = _cells(line)
        if all(set(c) <= set('-: ') for c in cells):      # the separator row
            continue
        head = _header(cells)
        if head:
            columns = head
            continue
        if not columns or not any(cells):
            continue
        row = {key: cells[i] if i < len(cells) else '' for i, key in columns.items()}
        if not (row.get('owners') or row.get('property')):
            continue
        prop = row.get('property', '')
        refs = [compact(m.group(1)) for m in _REF.finditer(prop)]
        owners = [o.strip(' -–') for o in re.split(r'<br\s*/?>|\n', row.get('owners', '')) if o.strip(' -–')]
        named = [o for o in owners if not re.match(r'^(?:الساكن|الساكنة|الساكنون|القاطن|عنوانه|عنوانها)', o)]
        out.append({'plot': row.get('plot', '')[:40], 'property': re.sub(r'<br\s*/?>', ' ', prop)[:400],
                    'ref': refs[0] if refs else '', 'area': row.get('area', '')[:60],
                    'owners': '\n'.join(owners)[:6000], 'owners_count': len(named),
                    'notes': re.sub(r'<br\s*/?>', '\n', row.get('notes', ''))[:2000]})
    return out


def read(text, articles: list) -> dict | None:
    """One text as a place's entry, or None when its title is not one of the land's formulas."""
    kind = kind_of(text.title_ar)
    if kind is None:
        return None
    bodies = '\n'.join(a.body for a in articles)
    head = text.title_ar + '\n' + '\n'.join(a.body for a in articles[:2])
    communes, provinces = places_in(head)
    properties = list(dict.fromkeys(m.group(1).strip() for m in _PROPERTY.finditer(head)))
    rows = rows_in(bodies)
    refs = list(dict.fromkeys([compact(m.group(1)) for m in _REF.finditer(head)] + [r['ref'] for r in rows if r['ref']]))
    page = next((a.printed_page for a in articles if a.printed_page), None)
    search = ' '.join([fold(text.title_ar), fold(' '.join(communes + provinces + properties)), ' '.join(refs),
                       *(fold(f"{r['property']} {r['owners']} {r['notes']}") for r in rows)])
    return {'kind': kind, 'communes': communes, 'provinces': provinces, 'properties': properties, 'refs': refs,
            'page': page, 'search': search, 'rows': rows}


def build() -> dict:
    """Every land text since 2019 read again into PlaceText and Parcel, in one transaction. Counts by kind."""
    from apps.corpus.models import Article, Text, Version, latest_ids
    from apps.topics.models import Parcel, PlaceText

    texts = list(Text.objects.filter(type__in=TYPES, first_published_in__date__gte=SINCE)
                 .select_related('first_published_in'))
    texts = [t for t in texts if kind_of(t.title_ar)]
    versions = latest_ids(Version.objects.filter(text__in=texts, language='ar')
                          .values_list('pk', 'text_id', 'valid_from', 'consolidation'))
    by_version: dict[int, list] = {}
    for a in Article.objects.filter(version_id__in=versions.values()).order_by('version_id', 'order').only(
            'version_id', 'body', 'printed_page', 'order'):
        by_version.setdefault(a.version_id, []).append(a)
    counts: dict[str, int] = {}
    places, parcels = [], []
    for t in texts:
        entry = read(t, by_version.get(versions.get(t.pk), []))
        if entry is None:
            continue
        counts[entry['kind']] = counts.get(entry['kind'], 0) + 1
        places.append(PlaceText(uri=t.akn_uri, kind=entry['kind'], date=t.first_published_in.date,
                                issue=t.first_published_in.key, page=entry['page'], title=t.title_ar,
                                communes=entry['communes'], provinces=entry['provinces'], properties=entry['properties'],
                                refs=entry['refs'], search=entry['search'], rows=len(entry['rows'])))
        parcels += [Parcel(uri=t.akn_uri, row=i, **r) for i, r in enumerate(entry['rows'])]
    with transaction.atomic():
        Parcel.objects.all().delete()
        PlaceText.objects.all().delete()
        PlaceText.objects.bulk_create(places, batch_size=500)
        Parcel.objects.bulk_create(parcels, batch_size=1000)
    return {'texts': len(places), 'rows': len(parcels), 'kinds': counts}


QUERY_MOST = 60


def find(q: str) -> dict:
    """The land texts that name what was typed (a commune, a property, a title or requisition number, a name as the BO
    printed it), newest first, each with the rows that hold it (or its first rows); three queries."""
    from apps.corpus.services.addresses import text_path
    from apps.topics.models import Parcel, PlaceText

    q = (q or '').strip()[:80]
    folded, short = fold(q), compact(q)
    if len(folded) < 2:
        return {'query': q, 'count': 0, 'texts': [], 'place': None}
    # A number is matched compact («F/18820», «f 18820», «18820»); words folded, each one.
    words = folded.split()
    found = PlaceText.objects.all()
    if re.search(r'\d', q) and len(short) >= 3:
        found = found.filter(search__contains=short)
    else:
        # The words as typed, together («رباط الخير», not «الرباط» here and «الخير» there); each alone only when the
        # phrase is nowhere.
        whole = found.filter(search__contains=folded)
        if len(words) > 1 and not whole.exists():
            for w in words:
                found = found.filter(search__contains=w)
        else:
            found = whole
    total = found.count()
    texts = list(found.order_by('-date', 'uri')[:QUERY_MOST])
    uris = [t.uri for t in texts]
    rows: dict[str, list] = {}
    for r in Parcel.objects.filter(uri__in=uris).order_by('uri', 'row'):
        rows.setdefault(r.uri, []).append(r)

    def hit(r) -> bool:
        blob = fold(f'{r.property} {r.owners} {r.notes}')
        return (bool(short) and short in r.ref) or folded in blob

    out = []
    for t in texts:
        mine = rows.get(t.uri, [])
        shown = [r for r in mine if hit(r)] or mine[:2]
        out.append({'path': text_path(t.uri), 'kind': t.kind, 'date': t.date, 'issue': t.issue, 'page': t.page,
                    'title': t.title, 'communes': t.communes, 'provinces': t.provinces, 'properties': t.properties,
                    'rows_total': t.rows,
                    'rows': [{'row': r.row, 'plot': r.plot, 'property': r.property, 'ref': r.ref, 'area': r.area,
                              'owners': r.owners.split('\n') if r.owners else [], 'owners_count': r.owners_count,
                              'notes': r.notes} for r in shown[:5]]})
    # The place itself, when what was typed is a commune's name as the texts print it.
    place = next((c for t in texts for c in t.communes if fold(c) == folded), None)
    return {'query': q, 'count': total, 'texts': out,
            'place': {'commune': place, 'since': min(t.date for t in texts).year} if place and texts else None}


def of_place(commune: str, most: int = 20) -> list[dict]:
    """The land texts that name a commune, newest first: what a reader following it hears of (M10). One query."""
    from apps.corpus.services.addresses import text_path
    from apps.topics.models import PlaceText

    folded = fold(commune)
    found = PlaceText.objects.filter(search__contains=folded).order_by('-date', 'uri')[:most * 3]
    return [{'path': text_path(t.uri), 'title': t.title, 'date': t.date, 'issue': t.issue, 'kind': t.kind}
            for t in found if any(fold(c) == folded for c in t.communes)][:most]


def of_places(communes, most: int = 20) -> dict[str, list[dict]]:
    """`of_place` for many communes, by name as followed, in one query whatever their number: the land texts that name
    any of them, newest first, and each commune's read from those as `of_place` reads its own (both sides folded, so
    the database's match and this one agree)."""
    from functools import reduce
    from operator import or_

    from django.db.models import Q

    from apps.corpus.services.addresses import text_path
    from apps.topics.models import PlaceText

    folded = {c: fold(c) for c in dict.fromkeys(communes)}
    out = {c: of_place(c, most) for c, f in folded.items() if not f}       # a name with no letters matches every text
    wanted = {f for f in folded.values() if f}
    found = list(PlaceText.objects.filter(reduce(or_, (Q(search__contains=f) for f in wanted))).order_by('-date', 'uri')
                 .only('uri', 'title', 'date', 'issue', 'kind', 'communes', 'search')) if wanted else []
    for commune, f in folded.items():
        if f:
            first = [t for t in found if f in t.search][:most * 3]
            out[commune] = [{'path': text_path(t.uri), 'title': t.title, 'date': t.date, 'issue': t.issue, 'kind': t.kind}
                            for t in first if any(fold(c) == f for c in t.communes)][:most]
    return out
