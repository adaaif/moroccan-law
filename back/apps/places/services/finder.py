"""The finder «البلدان والمدن» (PL19–PL22 of the places review, 1 Nov 2026): every place, what a reader types,
a place's profile, and the articles that name it, newest first, a page at a time (keyset: no count of a list, as the
discussion's lists since the load fixes). Read from what `build_places` wrote; a fixed number of queries each."""
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

from django.db.models import Count, Q

from apps.corpus.models import Article, Consolidation, Text
from apps.corpus.services import generation
from apps.corpus.services.addresses import article_path, text_path
from apps.places.models import Mention, Place, PlaceYear, Year
from apps.places.services.names import FOREIGN_KINDS, HOME_KINDS, fold
from apps.sources.models import Issue, Page

PAGE = 20
FIRST_YEAR = 1913     # the Arabic edition's No. 1; a place's years and its total count from the same year
KINDS = {k for k, _ in FOREIGN_KINDS} | {k for k, _ in HOME_KINDS} | {'other'}
LIST_FIELDS = ('slug', 'kind', 'name_ar', 'name_fr', 'name_en', 'texts', 'lat', 'lon', 'parent', 'population', 'region', 'successor', 'town')
WIDE = 90     # letters each side of a name in a snippet


def path(slug: str) -> str:
    return f'/places/{slug}'


def card(p) -> dict:
    """A place as a list shows it."""
    get = (lambda f: p[f]) if isinstance(p, dict) else (lambda f: getattr(p, f))
    out = {'slug': get('slug'), 'kind': get('kind'), 'ar': get('name_ar'), 'fr': get('name_fr') or get('name_en'),
           'texts': get('texts'), 'path': path(get('slug'))}
    for f in ('lat', 'lon', 'population', 'parent', 'successor', 'town'):
        if get(f) not in (None, ''):
            out[f] = get(f)
    return out


def listing() -> dict:
    """Every state and gone state, region, province and city, the busiest first; the communes counted (they are found
    by typing). The years' totals for the shares."""
    rows = list(Place.objects.exclude(kind=Place.Kind.COMMUNE).order_by('-texts', 'slug').values(*LIST_FIELDS))
    group = lambda *kinds: [card(r) for r in rows if r['kind'] in kinds]
    return {'countries': group('country', 'gone'), 'regions': group('region'), 'provinces': group('province'),
            'cities': group('city'), 'communes': Place.objects.filter(kind=Place.Kind.COMMUNE, texts__gt=0).count(),
            'years': [{'year': y.year, 'texts': y.texts, 'foreign': y.foreign} for y in Year.objects.order_by('year')]}


def _names() -> list:
    """[slug, kind, texts, names a reader may type folded, card] for every place, kept by the generation."""
    return generation.kept(['places-names'], _read_names)


def _read_names() -> list:
    out = []
    for p in Place.objects.order_by('-texts').values(*LIST_FIELDS, 'forms', 'old', 'latin'):
        typed = {fold(p['name_ar']), *(p['forms']), *(p['old']), *(fold(x) for x in p['latin'] + [p['name_fr'], p['name_en']] if x)}
        out.append((p['slug'], p['kind'], p['texts'], sorted(x for x in typed if x), card(p)))
    return out


def typed(q: str, most: int = 10) -> dict:
    """What a reader types (Arabic or Latin, any spelling the Bulletin printed): the places whose names start with it,
    then those that hold it, the most named first."""
    f = fold(q)
    if len(f) < 2:
        return {'query': q, 'places': []}
    starts, holds = [], []
    for _slug, _kind, _texts, names, c in _names():
        if any(n.startswith((f, 'ال' + f)) for n in names):
            starts.append(c)
        elif any(f in n for n in names):
            holds.append(c)
    return {'query': q, 'places': (starts + holds)[:most]}


def door(q: str) -> dict | None:
    """A place whose name is the whole query («الصين», «chine», «casa»): search opens its page first (PL21)."""
    f = fold(q)
    if len(f) < 2:
        return None
    for _slug, _kind, texts, names, c in _names():
        if f in names and texts:
            return c
    return None


def _issue_pages(keys: set[tuple[str, str, int]]) -> dict:
    """{(edition, issue key, printed page): (document id, page index)}: two queries."""
    if not keys:
        return {}
    wanted = {(e, *Issue.parse_key(k)) for e, k, _ in keys}
    docs = {(i.edition, i.key): i.document_id for i in Issue.objects.filter(
        edition__in={e for e, _, _ in wanted}, number__in={n for _, n, _ in wanted}).only('edition', 'number', 'suffix', 'document_id')}
    pages = {(d, n): ix for d, n, ix in Page.objects.filter(
        document_id__in={d for d in docs.values() if d}, printed_number__in={p for _, _, p in keys if p})
        .values_list('document_id', 'printed_number', 'index')}
    out = {}
    for e, k, p in keys:
        d = docs.get((e, k))
        if d and (d, p) in pages:
            out[(e, k, p)] = (d, pages[(d, p)])
    return out


def _stamp(edition, issue, page, pages) -> dict:
    found = pages.get((edition, issue, page))
    return {'issue': issue, 'edition': edition, 'page': page,
            'to': f'/pages/{found[0]}/{found[1]}' if found else None}


def profile(slug: str) -> dict | None:
    p = Place.objects.filter(slug=slug).first()
    if p is None:
        return None
    years = {y.year: y for y in PlaceYear.objects.filter(place=p)}
    totals = list(Year.objects.order_by('year'))
    kinds = Counter()
    for y in years.values():
        kinds.update(y.kinds)
    near = [card(x) for x in Place.objects.filter(
        Q(slug__in=[s for s in (p.parent, p.town, p.successor) if s]) | Q(parent=slug) & Q(texts__gt=0) | Q(town=slug) | Q(successor=slug))
        .order_by('-texts')[:24]]
    types = dict(Mention.objects.filter(place=p).values_list('text_type').annotate(n=Count('uri', distinct=True)).order_by('-n')[:8])
    first = dict(p.first) if p.first else None
    if first:
        first['path'] = article_path(first['uri'], first['eid']) if first['eid'] else text_path(first['uri'])
        first['stamp'] = _stamp(first['edition'], first['issue'], first['page'], _issue_pages({(first['edition'], first['issue'], first['page'])}))
    return {
        'place': {**card(p), 'en': p.name_en, 'code': p.code, 'population': p.population, 'foreigners': p.foreigners,
                  'old': [fold(x) for x in p.old], 'spellings': p.spellings, 'first': first},
        'years': [{'year': t.year, 'texts': years[t.year].texts if t.year in years else 0, 'total': t.texts} for t in totals
                  if t.year >= FIRST_YEAR],
        'kinds': dict(kinds.most_common()), 'types': types, 'near': near,
    }


# The fields Ask.read refuses by name: an answer sends one of these, never an error's own words.
ASKED = ('from', 'to', 'kind', 'type', 'with', 'after')


@dataclass(frozen=True)
class Ask:
    since: int | None = None
    until: int | None = None
    kind: str = ''
    type: str = ''
    title: bool = False
    with_: str = ''
    after: str = ''

    @classmethod
    def read(cls, params) -> 'Ask':
        def year(name):
            v = params.get(name, '')
            if not v:
                return None
            if not re.fullmatch(r'1[89]\d\d|20\d\d', v):
                raise ValueError(name)
            return int(v)
        kind, ttype, other, after = (params.get(k, '') for k in ('kind', 'type', 'with', 'after'))
        if kind and kind not in KINDS:
            raise ValueError('kind')
        if ttype and not re.fullmatch(r'[a-z_]{1,20}', ttype):
            raise ValueError('type')
        if other and not re.fullmatch(r'[a-z0-9-]{1,90}', other):
            raise ValueError('with')
        if after and not re.fullmatch(r'\d{4}-\d\d-\d\d\|/akn/[\w./-]{1,190}\|-?\d{1,6}', after):
            raise ValueError('after')
        if after:
            # The pattern lets «2024-99-99» through: the day is read here, where a refusal is a 400, not in mentions().
            try:
                date.fromisoformat(after.split('|')[0])
            except ValueError:
                raise ValueError('after') from None
        return cls(year('from'), year('to'), kind, ttype, params.get('title') == '1', other, after)

    def key(self) -> list:
        return [self.since, self.until, self.kind, self.type, self.title, self.with_, self.after]


def _snippet(body: str, at: int, size: int) -> dict:
    start, end = max(0, at - WIDE), min(len(body), at + size + WIDE)
    while start > 0 and not body[start - 1].isspace() and at - start < WIDE + 20:
        start -= 1
    while end < len(body) and not body[end].isspace() and end - at < size + WIDE + 20:
        end += 1
    clean = lambda s: ' '.join(s.replace('|', ' ').split())
    return {'before': ('… ' if start else '') + clean(body[start:at]), 'hit': clean(body[at:at + size]),
            'after': clean(body[at + size:end]) + (' …' if end < len(body) else '')}


def mentions(slug: str, ask: Ask) -> dict | None:
    p = Place.objects.filter(slug=slug).values('pk', 'slug', 'name_ar', 'name_fr').first()
    if p is None:
        return None
    rows = Mention.objects.filter(place_id=p['pk'])
    if ask.since:
        rows = rows.filter(date__gte=date(ask.since, 1, 1))
    if ask.until:
        rows = rows.filter(date__lte=date(ask.until, 12, 31))
    if ask.kind:
        rows = rows.filter(kind=ask.kind)
    if ask.type:
        rows = rows.filter(text_type=ask.type)
    if ask.title:
        rows = rows.filter(eid='')
    if ask.with_:
        rows = rows.filter(uri__in=Mention.objects.filter(place__slug=ask.with_).values('uri'))
    if ask.after:
        d, uri, order = ask.after.split('|')
        d, order = date.fromisoformat(d), int(order)
        rows = rows.filter(Q(date__lt=d) | Q(date=d, uri__gt=uri) | Q(date=d, uri=uri, order__gt=order))
    page = list(rows.order_by('-date', 'uri', 'order').values(
        'uri', 'eid', 'order', 'date', 'issue', 'edition', 'page', 'text_type', 'kind', 'form', 'at', 'printed')[:PAGE + 1])
    more = len(page) > PAGE
    page = page[:PAGE]
    uris = {m['uri'] for m in page}
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in=uris).only('akn_uri', 'title_ar', 'title_fr', 'type', 'number')}
    bodies = {}
    for uri, eid, label, body, consolidation in (Article.objects.filter(
            version__text__akn_uri__in=uris, version__language='ar', eid__in={m['eid'] for m in page if m['eid']})
            .order_by('version__valid_from').values_list('version__text__akn_uri', 'eid', 'label', 'body', 'version__consolidation')):
        mine = bodies.get((uri, eid))
        printed = consolidation == Consolidation.AS_PUBLISHED
        if mine is None or (printed and not mine[2]) or (not printed and not mine[2]):
            bodies[(uri, eid)] = (label, body, printed)
    pages = _issue_pages({(m['edition'], m['issue'], m['page']) for m in page if m['page']})
    from apps.corpus.services.codes import display_name
    out = []
    for m in page:
        t = texts.get(m['uri'])
        if m['eid']:
            label, body, _ = bodies.get((m['uri'], m['eid']), ('', '', True))
        else:
            label, body = '', (t.title_ar if t else '')
        size = len(m['form'])
        out.append({'path': article_path(m['uri'], m['eid']) if m['eid'] else text_path(m['uri']),
                    'text': text_path(m['uri']), 'label': label, 'title': t.title_ar if t else '',
                    'name': display_name(t) if t else {'ar': '', 'fr': None}, 'date': m['date'].isoformat(),
                    'kind': m['kind'], 'type': m['text_type'], 'in_title': not m['eid'],
                    'stamp': _stamp(m['edition'], m['issue'], m['page'], pages),
                    'snippet': _snippet(body, m['at'], size) if body[m['at']:m['at'] + size] == m['form'] else None})
    last = page[-1] if page and more else None
    return {'place': {'slug': p['slug'], 'ar': p['name_ar'], 'fr': p['name_fr']}, 'rows': out,
            'next': f"{last['date'].isoformat()}|{last['uri']}|{last['order']}" if last else None}


def recent(slug: str, most: int = 20) -> list[dict]:
    """The newest texts naming a place, for its followers' news (PL22): one per text."""
    return recent_many([slug], most).get(slug, [])


def recent_many(slugs, most: int = 20) -> dict[str, list[dict]]:
    """`recent` for many places, by slug, in two queries whatever their number (the follows' letters and news read one
    place at a time): each place's newest mentions ranked by the database, a text once."""
    from django.db.models import F, Window
    from django.db.models.functions import RowNumber

    rank = Window(RowNumber(), partition_by=[F('place_id')], order_by=[F('date').desc(), F('uri'), F('order')])
    rows = (Mention.objects.filter(place__slug__in=set(slugs)).annotate(rank=rank).filter(rank__lte=most * 4)
            .order_by('place_id', 'rank').values('place__slug', 'uri', 'date', 'issue', 'edition', 'page', 'kind'))
    seen: dict[str, set] = {}
    out: dict[str, list[dict]] = {}
    for m in rows:
        slug = m.pop('place__slug')
        mine, kept = seen.setdefault(slug, set()), out.setdefault(slug, [])
        if m['uri'] in mine or len(kept) >= most:
            continue
        mine.add(m['uri'])
        kept.append(m)
    titles = dict(Text.objects.filter(akn_uri__in=set().union(*seen.values())).values_list('akn_uri', 'title_ar')) \
        if seen else {}
    return {slug: [{**m, 'title': titles.get(m['uri'], ''), 'path': text_path(m['uri'])} for m in kept]
            for slug, kept in out.items()}
