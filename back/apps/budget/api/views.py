"""The budget, read-only and public: a finance law's figures, only from tables whose every check passed."""
from collections import defaultdict

from django.db.models import Prefetch
from django.http import Http404
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.budget.models import FinanceLaw, Kind, Line
from apps.consolidation.models import Change
from apps.corpus.models import Text
from apps.corpus.services import generation
from apps.corpus.services.addresses import text_path
from apps.opendata.throttles import OpenRate
from apps.sources.services.compare import fold


class PublicView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OpenRate]


def _amount(value):
    return None if value is None else str(value)


# The budget code's fourth part says whose credits a line is: 1 staff and 2 materials (or investment) of the
# ministry the sixth part names; 3, 4 and 5 are the state's own (common charges, contingencies, tax refunds),
# filed under the finance ministry's number but no ministry's spending.
STATE_WIDE = {'3': 'common', '4': 'contingencies', '5': 'tax_refunds'}


def _group(code: str) -> tuple[str, str]:
    """«1.2.1.1.0.06.000» → («06», ''); «1.2.1.3.0.13.000» → («common», 'common')."""
    parts = code.split('.')
    if len(parts) < 6:
        return '', ''
    if parts[3] in STATE_WIDE:
        return STATE_WIDE[parts[3]], STATE_WIDE[parts[3]]
    return parts[5], ''


def _name_key(name: str) -> str:
    """Tables print the same ministry «و المقاولة» or «والمقاولة»: names match without that space."""
    return fold(name).replace(' و ', ' و')


def ministries(law: FinanceLaw, shown: set[str]) -> list[dict]:
    """Each ministry or institution: running costs (table B), investment payment and commitment credits (table C),
    the posts it gets, and the pages it is printed on."""
    rows = defaultdict(lambda: {'name': '', 'state': '', 'running': 0, 'investment': 0, 'commitment': 0,
                                'posts': None, 'chapters': [], 'pages': set()})
    for table in ('B', 'C'):
        if table not in shown:
            continue
        for line in law.lines.filter(table=table, is_total=False):
            key, state = _group(line.code)
            row = rows[key]
            row['state'] = state
            if table == 'B':
                row['name'] = row['name'] or (line.label if state else line.section)
                row['running'] += line.amount or 0
                row['chapters'].append({'code': line.code, 'label': line.label, 'amount': _amount(line.amount),
                                        'page': line.page})
            else:
                row['name'] = row['name'] or (line.label.split(' - ')[-1] if state else line.label)
                row['investment'] += line.amount or 0
                row['commitment'] += line.commitment or 0
            row['pages'].add(line.page)
    if 'posts' in shown:
        by_name = {_name_key(r['name']): r for r in rows.values() if not r['state']}
        for line in law.lines.filter(table='posts', is_total=False):
            if (row := by_name.get(_name_key(line.label))) is not None:
                row['posts'] = int(line.amount)
    out = [{**r, 'code': code, 'running': str(r['running']), 'investment': str(r['investment']),
            'commitment': str(r['commitment']), 'pages': sorted(p for p in r['pages'] if p)}
           for code, r in rows.items()]
    return sorted(out, key=lambda r: -(float(r['running']) + float(r['investment'])))


def law_ref(law: FinanceLaw) -> dict:
    issue = law.text.first_published_in if law.text else None
    text = law.text
    # A bill has no BO issue: its file is the ministry's, filed on the day of its first version (the finance-bill review, P4).
    filed = None
    if law.kind == Kind.BILL and text is not None:
        first = min(text.versions.all(), key=lambda v: v.valid_from, default=None)
        filed = first and {'on': first.valid_from, 'document_id': first.source_document_id, 'path': text_path(text.akn_uri)}
    return {'year': law.year, 'kind': law.kind, 'number': law.number, 'title': law.title, 'filed': filed,
            'text_id': law.text_id, 'dahir': text.promulgating_dahir if text else '',
            'signed_on': text.signed_on if text else None, 'issue': None if issue is None else {
                'edition': issue.edition, 'key': issue.key, 'number': issue.number, 'suffix': issue.suffix,
                'date': issue.date, 'document_id': issue.document_id}}


_DIVISIONS = ('الجزء', 'الباب', 'القسم', 'الفرع', 'الكتاب', 'الفصل')


def contents(law: FinanceLaw) -> dict:
    """What the law does, from its own text: each article that carries a printed subject, under the part it sits
    in, and the texts it changes."""
    if not law.text:
        return {'articles': [], 'changes': []}
    version = law.text.versions.order_by('-valid_from').first()
    articles = []
    for a in version.articles.order_by('order'):
        subject = a.heading_path[-1] if a.heading_path and not a.heading_path[-1].startswith(_DIVISIONS) else ''
        part = next((h for h in reversed(a.heading_path) if h.startswith('الباب')), '') or \
            next((h for h in a.heading_path if h.startswith('الجزء')), '')
        if subject:
            articles.append({'number': a.number, 'eid': a.eid, 'label': a.label, 'subject': subject, 'part': part,
                             'page': a.printed_page})
    # The texts the law changes, read from its articles by code (row L3 of the links review).
    changes = defaultdict(lambda: {'title': '', 'type': '', 'number': '', 'count': 0, 'path': ''})
    source = Change.Source.BILL if law.kind == Kind.BILL else Change.Source.READING    # a bill's are proposals
    for uri in Change.objects.filter(by_uri=law.text.akn_uri, source=source).values_list('text_uri', flat=True):
        changes[uri]['count'] += 1
    # Its kind and number too: a text whose title was not read (law 25.00) is named by them, never left an empty link
    # (UX15 of the phone-test review).
    rows = {uri: (pk, title, kind, number) for pk, uri, title, kind, number in Text.objects.filter(
        akn_uri__in=list(changes)).values_list('id', 'akn_uri', 'title_ar', 'type', 'number_as_printed')}
    ids = {uri: r[0] for uri, r in rows.items()}
    for uri, row in changes.items():
        _, title, kind, number = rows.get(uri, (None, '', '', ''))
        row.update(title=title, type=kind, number=number, path=text_path(uri))
    return {'articles': articles,
            'changes': [{'id': ids.get(uri), **row} for uri, row in changes.items()]}


def headline(law: FinanceLaw) -> dict | None:
    """A year's key figures, when its balance passed every check: for the years side by side."""
    if 'balance' not in law.tables_checked():
        return None
    lines = law.head_lines if hasattr(law, 'head_lines') else list(law.lines.filter(table__in=('balance', 'posts')))
    b = {line.key: line.amount for line in lines if line.table == 'balance'}
    if not {'ordinary_revenue', 'ordinary_spending', 'investment', 'state_balance'} <= b.keys():
        return None
    posts = next((line for line in lines if line.table == 'posts' and line.is_total), None) \
        if 'posts' in law.tables_checked() else None
    created = (law.stated.get('posts') or [None])[0] if 'posts' in law.tables_checked() else None
    return {'revenue': str(b['ordinary_revenue']), 'spending': str(b['ordinary_spending'] + b['investment']),
            'deficit': str(-b['state_balance']), 'borrowing': _amount(b.get('borrowing')),
            'posts': int(created) if created else (int(posts.amount) if posts else None)}


class FinanceLawList(PublicView):
    def get(self, request):
        return generation.answer(['budget'], laws)


def laws() -> list[dict]:
    rows = FinanceLaw.objects.select_related('text__first_published_in').prefetch_related(
        'text__versions', Prefetch('lines', queryset=Line.objects.filter(table__in=('balance', 'posts')), to_attr='head_lines'))
    return [{**law_ref(law), 'headline': headline(law)} for law in rows]


class FinanceLawDetail(PublicView):
    def get(self, request, year):
        # A year asked without a kind is its law, else its bill while Parliament debates it.
        kind = request.query_params.get('kind', '')
        return generation.answer(['budget', year, kind], lambda: self.year(year, kind))

    @staticmethod
    def year(year: int, kind: str) -> dict:
        laws = FinanceLaw.objects.select_related('text__first_published_in__document').filter(year=year)
        law = laws.filter(kind=kind).first() if kind else \
            (laws.filter(kind=Kind.LAW).first() or laws.filter(kind=Kind.BILL).first())
        if law is None:
            raise Http404
        shown = law.tables_checked()
        pages = {}
        if law.document_id:
            pages = dict(law.document.pages.values_list('printed_number', 'index'))
        articles = {}
        if law.text:
            version = law.text.versions.order_by('-valid_from').first()
            articles = {a.number: {'eid': a.eid, 'page': a.printed_page} for a in version.articles.all()}
        balance = {line.key: {'amount': _amount(line.amount), 'page': line.page}
                   for line in law.lines.filter(table='balance')} if 'balance' in shown else None
        posts = [{'label': line.label, 'count': int(line.amount), 'total': line.is_total}
                 for line in law.lines.filter(table='posts')] if 'posts' in shown else None
        return {
            **law_ref(law), 'page_index': pages, 'articles': articles, 'balance': balance, 'posts': posts,
            'ministries': ministries(law, shown),
            'stated': {table: law.stated.get(table) for table in shown if table in law.stated},
            'sources': law.sources,
            'contents': contents(law),
            'checks': {'count': len(law.checks), 'passed': sum(c['ok'] for c in law.checks), 'shown': sorted(shown),
                       'items': law.checks, 'checked_at': law.checked_at},
        }
