"""Explanations in the admin, for looking: people write them on the site, the text's reviewers check, keep or remove
each state there (review.covers), and every state is kept. Nothing is written here."""
from django.contrib import admin
from django.db.models import Q

from apps.explain.models import Explanation, Report, Revision
from config.admin import ReadOnly, admin_link, changelist_link, on_site, rows_table, site_address

SHOWN = 20


class ExplanationState(admin.SimpleListFilter):
    title, parameter_name = 'review', 'review'
    CASES = {
        'waiting': ('an edit waits for a reviewer', Q(pending__isnull=False)),
        'never': ('never checked', Q(reviewed_at=None)),
        'checked': ('checked', Q(reviewed_at__isnull=False, pending=None)),
    }

    def lookups(self, request, model_admin):
        return [(k, label) for k, (label, _) in self.CASES.items()]

    def queryset(self, request, queryset):
        return queryset.filter(self.CASES[self.value()][1]) if self.value() in self.CASES else queryset


@admin.register(Explanation)
class ExplanationAdmin(ReadOnly):
    list_display = ('path', 'register', 'headline', 'reviewed_at', 'reviewed_by', 'waiting', 'helpful_count',
                    'updated_at', 'on_the_site')
    list_select_related = ('reviewed_by',)
    list_filter = (ExplanationState, 'register')
    search_fields = ('path', 'headline', 'body')
    search_help_text = 'Part of the address it explains, its headline or its words.'
    ordering = ('-updated_at',)
    fieldsets = [
        ('The words readers see', {'fields': ('path', 'register', 'headline', 'body', 'sources', 'on_the_site')}),
        ('Checked', {'fields': ('reviewed_at', 'reviewed_by', 'pending', 'version_on', 'article_digest')}),
        ('Every state it had', {'fields': ('revisions_table',)}),
        ('Counts', {'classes': ('collapse',), 'fields': ('helpful_count', 'created_at', 'updated_at')}),
    ]
    readonly_fields = ('on_the_site', 'revisions_table')

    def view_on_site(self, obj):
        return site_address(f'/explain{obj.path}')

    @admin.display(description='an edit waits', boolean=True)
    def waiting(self, obj):
        return obj.pending_id is not None

    @admin.display(description='on the site')
    def on_the_site(self, obj):
        return on_site(f'/explain{obj.path}', 'open')

    @admin.display(description='states, newest first')
    def revisions_table(self, obj):
        rows = list(obj.revisions.select_related('author').order_by('-created_at', '-id')[:SHOWN + 1])
        more = changelist_link(Revision, 'every state', explanation=obj.pk) if len(rows) > SHOWN else None
        return rows_table(('when', 'by', 'headline', 'state'),
                          [(admin_link(r, f'{r.created_at:%Y-%m-%d %H:%M}'), r.author or '—', r.headline or '—',
                            revision_state(r)) for r in rows[:SHOWN]], more)


def revision_state(r: Revision) -> str:
    if r.removed_at:
        return 'removed'
    if r.checked_at:
        return 'checked'
    return 'held' if r.held_reasons else 'waiting'


class RevisionState(admin.SimpleListFilter):
    title, parameter_name = 'state', 'state'
    CASES = {
        'waiting': ('waiting for a reviewer', Q(checked_at=None, removed_at=None)),
        'held': ('held by the patterns or the check', Q(checked_at=None, removed_at=None) & ~Q(held_reasons=[])),
        'checked': ('checked', Q(checked_at__isnull=False, removed_at=None)),
        'removed': ('removed', Q(removed_at__isnull=False)),
    }

    def lookups(self, request, model_admin):
        return [(k, label) for k, (label, _) in self.CASES.items()]

    def queryset(self, request, queryset):
        return queryset.filter(self.CASES[self.value()][1]) if self.value() in self.CASES else queryset


@admin.register(Revision)
class RevisionAdmin(ReadOnly):
    list_display = ('created_at', 'explanation__path', 'explanation__register', 'author', 'headline', 'state',
                    'checked_by', 'removed_by')
    list_select_related = ('explanation', 'author', 'checked_by', 'removed_by')
    list_filter = (RevisionState, 'explanation__register')
    search_fields = ('explanation__path', 'headline', 'body', 'author__username')
    search_help_text = 'Part of the address, the headline, the words or the author\'s username.'
    fieldsets = [
        ('The words', {'fields': ('explanation', 'author', 'headline', 'body', 'sources', 'note', 'created_at')}),
        ('Held', {'fields': ('held_reasons', 'held_spans')}),
        ('Decided', {'fields': ('checked_at', 'checked_by', 'removed_at', 'removed_by', 'removed_rule')}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('explanation', 'author', 'checked_by', 'removed_by')

    @admin.display(description='state')
    def state(self, obj):
        return revision_state(obj)


@admin.register(Report)
class ReportAdmin(ReadOnly):
    list_display = ('created_at', 'reason', 'status', 'revision__explanation__path', 'reporter', 'decided_by',
                    'decided_at')
    list_select_related = ('revision__explanation', 'reporter', 'decided_by')
    list_filter = ('status', 'reason')
    show_facets = admin.ShowFacets.ALWAYS
    search_fields = ('revision__explanation__path', 'details', 'reporter__username')
    search_help_text = 'Part of the explanation\'s address, the reporter\'s details or username.'
    ordering = ('-created_at',)
    fields = ('revision', 'reason', 'details', 'reporter', 'status', 'created_at', 'decided_at', 'decided_by')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('revision__explanation', 'reporter', 'decided_by')
