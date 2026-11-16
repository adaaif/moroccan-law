"""The admin site and the few pieces its pages share (12 Nov 2026).

- `Site`: the site's name, its apps in the order staff look for them (the law and its sources, what readers write,
  the accounts, the record), and on the index one line of what waits for a person; the counts' report
  (/admin/analytics/), its one page that lists no model.
- `ReadOnly`: a page for looking. The law's rows come from the pipeline and are put right through the quality app's
  corrections; the ledgers, the logs and every row a service writes are read here, never typed over.
- `Large`: a table of hundreds of thousands of rows or more, listed without counting it: PostgreSQL's estimate for an
  unfiltered list (`EstimatedCount`), no facet counts, no second count of the whole table.
- `on_site`, `admin_link`, `rows_table`: the links and the small tables the change pages show.

This module is loaded with INSTALLED_APPS (`AdminConfig`), so it names models by their labels and imports none.
"""
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.apps import AdminConfig as DjangoAdminConfig
from django.core.paginator import Paginator
from django.db import connections
from django.db.models import Q
from django.urls import path, reverse
from django.utils.functional import cached_property
from django.utils.html import format_html, format_html_join
from django.utils.http import urlencode

# The index's order: each app with a name that says what it holds, and its models in the order they are looked at.
# An app or a model not named here comes after, alphabetically.
SECTIONS = [
    ('corpus', 'The law: texts, versions, articles', ['Text', 'Version', 'Article', 'Mention', 'Alias']),
    ('sources', 'Sources: the files, the Bulletin\'s issues and pages', ['Issue', 'Document', 'Page', 'OcrRun']),
    ('consolidation', 'Consolidation: changes and doubts', ['Doubt', 'Change']),
    ('quality', 'Quality: readers\' reports, corrections, suspect words', ['Report', 'Correction', 'Suspect']),
    ('translations', 'The official French', ['FrenchText', 'FrenchArticle']),
    ('parliament', 'Parliament', []),
    ('budget', 'Finance laws', ['FinanceLaw', 'Line']),
    ('discussion', 'The discussion', ['Report', 'Contribution', 'Appeal', 'Ban', 'Action', 'Discussion', 'Reviewer',
                                     'Trust', 'Check', 'Notice', 'Point', 'Follow']),
    ('explain', 'Explanations', ['Explanation', 'Revision', 'Report']),
    ('media', 'Voices and pictures', ['Clip', 'Picture']),
    ('topics', 'Life topics', ['ItemCheck', 'Helped', 'PlaceText', 'Parcel']),
    ('places', 'Places', []),
    ('follows', 'Follows', []),
    ('search', 'Search', ['SearchLog', 'SearchEntry']),
    ('accounts', 'Accounts', ['User', 'EmailCode']),
    ('auth', 'Groups', []),
    ('token_blacklist', 'Sign-in tokens', ['OutstandingToken', 'BlacklistedToken']),
    ('oauth', 'Assistants\' connections', ['Grant', 'Client']),
    ('opendata', 'Open data: access requests, accesses, keys', ['Request', 'Access', 'Event', 'ApiKey', 'AccessDay',
                                                              'Download']),
    ('mcp', 'Assistants\' shares', []),
    ('analytics', 'What readers do: the counts', []),
    ('admin', 'The admin\'s own log', []),
]

# The admin's one page that lists no model: the counts' report (apps/analytics/admin.py), at /admin/analytics/, for
# staff with the view right on the day counts. The index and the side bar list it in its app's place.
REPORT = {'label': 'analytics', 'name': 'The report', 'url': 'admin:analytics_report',
          'right': 'analytics.view_daycount'}

# Plurals Django makes by adding an «s» («aliass»), and a name that says what a list holds: the index and the side
# bar say them right. The lists' own titles keep the models' verbose names, which only a migration changes.
PLURALS = {'corpus.alias': 'Aliases', 'search.searchentry': 'Search entries',
           'topics.helped': 'Did it help (readers\' answers)', 'opendata.request': 'Access requests'}

# What waits for a person, on the index: (model label, words, the list's filter, the rows).
WAITING = [
    ('quality.Report', 'readers\' reports', 'status__exact=open', Q(status='open')),
    ('quality.Correction', 'suggested corrections', 'status__exact=suggested', Q(status='suggested')),
    ('quality.Suspect', 'suspect words', 'status__exact=open', Q(status='open')),
    ('consolidation.Doubt', 'doubts', 'status__exact=open', Q(status='open')),
    ('discussion.Report', 'reports on posts', 'status__exact=open', Q(status='open')),
    ('discussion.Contribution', 'held posts and comments', 'state=held',
     Q(held_at__isnull=False, removed_at=None, deleted_at=None, erased_at=None)),
    ('discussion.Appeal', 'appeals', 'decided=no', Q(outcome='')),
    ('explain.Report', 'reports on explanations', 'status__exact=open', Q(status='open')),
    ('opendata.Request', 'requests for access', 'state=waiting', Q(state='waiting')),
]


class Site(admin.AdminSite):
    index_title = 'The admin'
    empty_value_display = '—'               # as the columns that build their own empty cell say it

    @property
    def site_header(self):
        return settings.SITE_NAME

    @property
    def site_title(self):
        return f'{settings.SITE_NAME} admin'

    @property
    def site_url(self):
        """«View site» opens the reader's site, not Django's own root."""
        return settings.SITE_URL

    def get_urls(self):
        from apps.analytics.admin import report     # read when the addresses are, once the apps are loaded
        return [path('analytics/', self.admin_view(report), name='analytics_report'), *super().get_urls()]

    def get_app_list(self, request, app_label=None):
        apps_ = self._build_app_dict(request, app_label)
        if app_label in (None, REPORT['label']) and request.user.has_perm(REPORT['right']):
            url = reverse(REPORT['url'])
            # Shaped as Django lists a model's page; `model` is read only for its label (PLURALS, below).
            apps_[REPORT['label']] = {
                'name': REPORT['label'], 'app_label': REPORT['label'], 'app_url': url, 'has_module_perms': True,
                'models': [{'model': apps.get_model('analytics.DayCount'), 'name': REPORT['name'], 'object_name': 'Report',
                            'perms': {'view': True}, 'admin_url': url, 'add_url': None, 'view_only': True}]}
        place = {label: (i, name, models) for i, (label, name, models) in enumerate(SECTIONS)}
        for label, app in apps_.items():
            for m in app['models']:
                m['name'] = PLURALS.get(m['model']._meta.label_lower, m['name'])
            if label in place:
                app['name'] = place[label][1]
                order = place[label][2]
                app['models'].sort(key=lambda m: (order.index(m['object_name']) if m['object_name'] in order
                                                  else len(order), m['name']))
            else:
                app['models'].sort(key=lambda m: m['name'])
        return sorted(apps_.values(), key=lambda a: (place.get(a['app_label'], (len(SECTIONS),))[0], a['name'].lower()))

    def index(self, request, extra_context=None):
        return super().index(request, {'subtitle': self.waiting(request), **(extra_context or {})})

    def waiting(self, request):
        """One count a queue, each opening its list filtered: what a person has to look at today."""
        found = []
        for label, words, query, rows in WAITING:
            model = apps.get_model(label)
            model_admin = self._registry.get(model)
            if model_admin is None or not model_admin.has_view_permission(request):
                continue
            n = model.objects.filter(rows).count()
            if n:
                url = reverse(f'{self.name}:{model._meta.app_label}_{model._meta.model_name}_changelist')
                found.append((f'{url}?{query}', f'{n:,}', words))
        if not found:
            return 'Nothing waits for a person.'
        return format_html('Waiting for a person: {}',
                           format_html_join(' · ', '<a href="{}">{} {}</a>', found))


class AdminConfig(DjangoAdminConfig):
    default_site = 'config.admin.Site'

    def ready(self):
        super().ready()
        from django.contrib.admin.models import LogEntry
        self.module.site.register(LogEntry, LogEntryAdmin)


def estimate(model, using: str = 'default') -> int | None:
    """PostgreSQL's estimate of a table's rows (pg_class.reltuples, kept by ANALYZE and autovacuum); None elsewhere, or
    before the table was ever analysed."""
    connection = connections[using]
    if connection.vendor != 'postgresql':
        return None
    with connection.cursor() as cursor:
        cursor.execute('SELECT reltuples::bigint FROM pg_class WHERE oid = to_regclass(%s)', [model._meta.db_table])
        row = cursor.fetchone()
    return row[0] if row and row[0] is not None and row[0] >= 0 else None


class EstimatedCount(Paginator):
    """Counts an unfiltered list of a large table from the estimate instead of COUNT(*) over every row (seconds on
    650,000 articles, more on the request log); a filtered or searched list, a table under EXACT_BELOW rows and SQLite
    count exactly. Such a list's count is the estimate, and a last page past the real rows is empty."""
    EXACT_BELOW = 10_000

    @cached_property
    def count(self):
        rows = self.object_list
        if hasattr(rows, 'query') and not rows.query.where and not rows.query.distinct:
            n = estimate(rows.model, rows.db)
            if n is not None and n >= self.EXACT_BELOW:
                return n
        return super().count


class ReadOnly(admin.ModelAdmin):
    """Rows staff look at and never add, change or delete here."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class Large:
    """A table of hundreds of thousands of rows: its list is never counted whole, shows no facet counts (each one a
    count over the table), and is ordered by its key unless the admin says otherwise."""
    paginator = EstimatedCount
    show_full_result_count = False
    show_facets = admin.ShowFacets.NEVER
    list_per_page = 50
    ordering = ('-pk',)


class LogEntryAdmin(ReadOnly):
    """The admin's own log: who added, changed or deleted what here, and when (Django writes it; the index shows a
    person's last ten)."""
    list_display = ('action_time', 'user', 'action_flag', 'content_type', 'the_row', 'what')
    list_select_related = ('user', 'content_type')
    list_filter = ('action_flag', 'content_type')
    search_fields = ('object_repr', 'user__username')
    search_help_text = 'Part of the row\'s name as it was then, or of the username.'
    ordering = ('-action_time',)

    @admin.display(description='row', ordering='object_repr')
    def the_row(self, obj):
        url = obj.get_admin_url()
        return format_html('<a href="{}">{}</a>', url, obj.object_repr) if url else obj.object_repr

    @admin.display(description='what changed')
    def what(self, obj):
        return obj.get_change_message()


def on_site(path: str, label: str | None = None):
    """A link that opens an address of the reader's site in a new tab."""
    if not path:
        return '—'
    return format_html('<a href="{}{}" target="_blank" rel="noopener">{}</a>', settings.SITE_URL.rstrip('/'), path,
                       label or path)


def site_address(path: str) -> str:
    """An address of the reader's site, whole (for `view_on_site`)."""
    return f'{settings.SITE_URL.rstrip("/")}{path}'


def admin_link(obj, label: str | None = None):
    """A link to a row's own page in this admin."""
    if obj is None:
        return '—'
    url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=[obj.pk])
    return format_html('<a href="{}">{}</a>', url, label if label is not None else obj)


def changelist_link(model, label: str, **lookups):
    """A link to a model's list filtered by `lookups` (local fields: the admin allows them in the address)."""
    url = reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist')
    return format_html('<a href="{}?{}">{}</a>', url, urlencode(lookups), label)


def rows_table(heads, rows, more=None):
    """A small table of related rows on a change page: `rows` bounded by the caller, `more` a link to the rest."""
    if not rows:
        return '—'
    head = format_html_join('', '<th>{}</th>', ((h,) for h in heads))
    body = format_html_join('', '<tr>{}</tr>', ((format_html_join('', '<td>{}</td>', ((c,) for c in row)),)
                                                for row in rows))
    return format_html('<table><thead><tr>{}</tr></thead><tbody>{}</tbody></table>{}', head, body,
                       format_html('<p>{}</p>', more) if more else '')
