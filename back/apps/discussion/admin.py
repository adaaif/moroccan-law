"""Staff's side of the discussion in the admin: moderators to appoint and end, and every row behind the review desk for
looking up. Acts on posts and comments go through the review desk (/review), which writes the ledger in the same
transaction as the act; the admin only reads them, the ledger included. Appointing and ending a moderator write the
ledger too (`review.appoint`, `review.dismiss`)."""
from django.contrib import admin
from django.db.models import F, Q
from django.utils import timezone
from django.utils.html import format_html

from apps.discussion.models import (Action, Appeal, Ban, Check, Contribution, Discussion, Follow, Notice, Point, Report,
                                    Reviewer, Trust)
from apps.discussion.services import review
from config.admin import Large, ReadOnly, admin_link, changelist_link, on_site, rows_table, site_address

SHOWN = 20


def place_path(path: str) -> str:
    """A discussion's page on the site: a topic's place as it is, an article's thread from before 29 Oct 2026 under
    /discussion."""
    return path if path.startswith('/talk/') else f'/discussion{path}'


def post_path(c: Contribution) -> str:
    """A post's or a comment's own page: its post in a topic's place, or its article's thread."""
    path = c.discussion.path
    if path.startswith('/talk/') and path.count('/') == 2:
        return f'{path}/{c.parent_id or c.pk}' + (f'#c{c.pk}' if c.parent_id else '')
    return place_path(path)


STATES = {
    'held': ('held for a moderator', Q(held_at__isnull=False, removed_at=None, deleted_at=None, erased_at=None)),
    'hidden': ('hidden after reports', Q(hidden_at__isnull=False, removed_at=None, deleted_at=None, erased_at=None)),
    'removed': ('removed', Q(removed_at__isnull=False)),
    'deleted': ('deleted by its author', Q(deleted_at__isnull=False, removed_at=None)),
    'erased': ('erased', Q(erased_at__isnull=False)),
    'live': ('published', Q(held_at=None, hidden_at=None, removed_at=None, deleted_at=None, erased_at=None)),
}


class StateFilter(admin.SimpleListFilter):
    title, parameter_name = 'state', 'state'

    def lookups(self, request, model_admin):
        return [(k, label) for k, (label, _) in STATES.items()]

    def queryset(self, request, queryset):
        return queryset.filter(STATES[self.value()][1]) if self.value() in STATES else queryset


class LevelFilter(admin.SimpleListFilter):
    title, parameter_name = 'post or comment', 'level'

    def lookups(self, request, model_admin):
        return [('post', 'posts'), ('comment', 'comments')]

    def queryset(self, request, queryset):
        if self.value() == 'post':
            return queryset.filter(parent=None)
        if self.value() == 'comment':
            return queryset.filter(parent__isnull=False)
        return queryset


def state_of(c: Contribution) -> str:
    """The state that decides what readers see, the strongest first."""
    for key in ('erased', 'removed', 'deleted', 'hidden', 'held'):
        if getattr(c, f'{key}_at'):
            return STATES[key][0]
    return STATES['live'][0]


@admin.register(Contribution)
class ContributionAdmin(Large, ReadOnly):
    list_display = ('created_at', 'kind', 'excerpt', 'discussion__path', 'author', 'anonymous', 'state',
                    'useful_count', 'reply_count', 'on_the_site')
    list_display_links = ('created_at', 'excerpt')
    list_select_related = ('discussion', 'author')
    list_filter = (StateFilter, LevelFilter, 'kind', 'anonymous', ('created_at', admin.DateFieldListFilter))
    search_fields = ('title', 'body', 'author__username')
    search_help_text = 'Part of the title, the words or the author\'s username.'
    fieldsets = [
        ('What was written', {'fields': ('discussion', 'kind', 'author', 'anonymous', 'title', 'body', 'quote',
                                         'about', 'links', 'parent', 'reply_to', 'on_the_site')}),
        ('Voice and pictures', {'classes': ('collapse',), 'fields': ('clip', 'pictures')}),
        ('Its review', {'fields': ('state', 'held_at', 'held_reasons', 'held_spans', 'review_note', 'post_review_at',
                                   'hidden_at', 'removed_at', 'removed_by', 'removed_rule', 'deleted_at',
                                   'frozen_until', 'erased_at', 'duplicate_of', 'its_reports')}),
        ('Its earlier words', {'classes': ('collapse',), 'fields': ('revisions_table',)}),
        ('The articles it cites', {'classes': ('collapse',), 'fields': ('cites_table', 'version_on',
                                                                        'article_digest')}),
        ('Its counts', {'classes': ('collapse',), 'fields': ('useful_count', 'accepted_at', 'reply_count', 'active_at',
                                                             'answered_at', 'answer', 'conversation_count',
                                                             'people_count', 'created_at', 'edited_at')}),
    ]
    readonly_fields = ('on_the_site', 'state', 'its_reports', 'revisions_table', 'cites_table')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('discussion', 'author')

    def view_on_site(self, obj):
        return site_address(post_path(obj))

    @admin.display(description='words')
    def excerpt(self, obj):
        words = obj.title or obj.body
        return words[:80] + ('…' if len(words) > 80 else '') if words else '(a voice or pictures)'

    @admin.display(description='state')
    def state(self, obj):
        return state_of(obj)

    @admin.display(description='on the site')
    def on_the_site(self, obj):
        return on_site(post_path(obj), 'open')

    @admin.display(description='reports')
    def its_reports(self, obj):
        return changelist_link(Report, 'the reports on it', contribution=obj.pk)

    @admin.display(description='words before each edit')
    def revisions_table(self, obj):
        rows = list(obj.revisions.order_by('-created_at')[:SHOWN])
        return rows_table(('when', 'words'), [(f'{r.created_at:%Y-%m-%d %H:%M}', r.body) for r in rows])

    @admin.display(description='articles cited')
    def cites_table(self, obj):
        rows = list(obj.cites.order_by('pk')[:SHOWN])
        return rows_table(('article', 'its words then'), [(on_site(c.path), c.digest or '—') for c in rows])


@admin.register(Discussion)
class DiscussionAdmin(ReadOnly):
    list_display = ('path', 'text_path', 'count', 'open_questions', 'last_at', 'locked_at', 'on_the_site')
    list_filter = (('locked_at', admin.EmptyFieldListFilter),)
    search_fields = ('path', 'text_path')
    search_help_text = 'Part of the place\'s or the article\'s address.'
    ordering = (F('last_at').desc(nulls_last=True), '-pk')
    fields = ('path', 'text_path', 'count', 'open_questions', 'last_at', 'locked_at', 'locked_by', 'created_at',
              'its_rows')
    readonly_fields = ('its_rows',)

    def view_on_site(self, obj):
        return site_address(place_path(obj.path))

    @admin.display(description='on the site')
    def on_the_site(self, obj):
        return on_site(place_path(obj.path), 'open')

    @admin.display(description='what was written')
    def its_rows(self, obj):
        return changelist_link(Contribution, 'its posts and comments', discussion=obj.pk)


@admin.register(Report)
class ReportAdmin(ReadOnly):
    list_display = ('created_at', 'reason', 'status', 'takedown', 'reported', 'reporter', 'decided_by', 'decided_at')
    list_select_related = ('contribution__discussion', 'reporter', 'decided_by')
    list_filter = ('status', 'reason', 'takedown')
    show_facets = admin.ShowFacets.ALWAYS
    search_fields = ('details', 'reporter__username', 'contribution__author__username')
    search_help_text = 'Part of the reporter\'s details, the reporter\'s or the author\'s username.'
    ordering = ('-created_at',)
    fields = ('contribution', 'reported', 'reason', 'moment_ms', 'details', 'takedown', 'contact', 'reporter',
              'status', 'created_at', 'decided_at', 'decided_by')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('contribution__discussion', 'reporter', 'decided_by')

    @admin.display(description='reported')
    def reported(self, obj):
        return format_html('{} · {}', admin_link(obj.contribution), on_site(post_path(obj.contribution), 'on the site'))


@admin.register(Action)
class ActionAdmin(Large, ReadOnly):
    """The ledger, as it was written: never changed."""
    list_display = ('created_at', 'verb', 'actor', 'target', 'contribution', 'rule', 'path', 'note')
    list_select_related = ('actor', 'target', 'contribution')
    list_filter = ('verb', 'rule')
    search_fields = ('actor__username', 'target__username', 'path', 'note')
    search_help_text = 'Part of who acted, on whom, where, or the note.'
    ordering = ('-created_at',)


class LiveFilter(admin.SimpleListFilter):
    title, parameter_name = 'running', 'running'

    def lookups(self, request, model_admin):
        return [('yes', 'still running'), ('no', 'over')]

    def queryset(self, request, queryset):
        live = Q(ended_at=None) & (Q(until=None) | Q(until__gt=timezone.now()))
        if self.value() == 'yes':
            return queryset.filter(live)
        if self.value() == 'no':
            return queryset.exclude(live)
        return queryset


@admin.register(Ban)
class BanAdmin(ReadOnly):
    list_display = ('started_at', 'user', 'until', 'rule', 'by', 'permanent_asked_by', 'ended_at')
    list_select_related = ('user', 'by', 'permanent_asked_by')
    list_filter = (LiveFilter, 'rule')
    search_fields = ('user__username', 'note')
    search_help_text = 'Part of the paused account\'s username, or the note.'
    ordering = ('-started_at',)
    fields = ('user', 'rule', 'note', 'until', 'permanent_asked_by', 'by', 'via', 'started_at', 'ended_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'by', 'permanent_asked_by', 'via')


class WaitingFilter(admin.SimpleListFilter):
    title, parameter_name = 'decided', 'decided'

    def lookups(self, request, model_admin):
        return [('no', 'waiting'), ('yes', 'decided')]

    def queryset(self, request, queryset):
        if self.value() == 'no':
            return queryset.filter(outcome='')
        if self.value() == 'yes':
            return queryset.exclude(outcome='')
        return queryset


@admin.register(Appeal)
class AppealAdmin(ReadOnly):
    list_display = ('created_at', 'user', 'against', 'outcome', 'decided_by', 'decided_at')
    list_select_related = ('user', 'contribution', 'ban', 'decided_by')
    list_filter = (WaitingFilter, 'outcome')
    search_fields = ('user__username', 'text')
    search_help_text = 'Part of the account\'s username, or the appeal\'s words.'
    ordering = ('-created_at',)
    fields = ('user', 'against', 'text', 'created_at', 'outcome', 'decided_by', 'decided_at')
    readonly_fields = ('against',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'contribution', 'ban', 'decided_by')

    @admin.display(description='against')
    def against(self, obj):
        if obj.contribution_id:
            return format_html('the removal of {}', admin_link(obj.contribution))
        return format_html('a pause: {}', admin_link(obj.ban, f'from {obj.ban.started_at:%Y-%m-%d}')) if obj.ban_id \
            else '—'


@admin.register(Reviewer)
class ReviewerAdmin(admin.ModelAdmin):
    """Appointing a moderator, changing what they cover and ending them write the ledger (`review.appoint`,
    `review.dismiss`); an ended appointment is kept as it was."""
    list_display = ('user', 'covers', 'appointed_by', 'appointed_at', 'ended_at')
    list_select_related = ('user', 'appointed_by')
    list_filter = (('ended_at', admin.EmptyFieldListFilter),)
    search_fields = ('user__username',)
    search_help_text = 'Part of the moderator\'s username.'
    ordering = ('-appointed_at',)
    autocomplete_fields = ('user',)
    fields = ('user', 'text_paths', 'appointed_by', 'appointed_at', 'ended_at')
    readonly_fields = ('appointed_by', 'appointed_at', 'ended_at')
    actions = ('end',)

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (('user',) if obj else ())

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and not (obj and obj.ended_at)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # In the admin, an empty list is staff's own choice of «everything». A change is a new appointment: the
        # ledger says who changed it, and the old row stays as it was.
        made = review.appoint(request.user, obj.user, obj.text_paths, everywhere=not obj.text_paths)
        obj.pk = made.pk

    @admin.display(description='covers')
    def covers(self, obj):
        return ', '.join(obj.text_paths) if obj.text_paths else 'everything'

    @admin.action(permissions=['change'], description='End these moderators')
    def end(self, request, queryset):
        for r in queryset.filter(ended_at=None).select_related('user'):
            review.dismiss(request.user, r.user)


@admin.register(Trust)
class TrustAdmin(ReadOnly):
    list_display = ('created_at', 'user', 'by', 'ended_at')
    list_select_related = ('user', 'by')
    list_filter = (('ended_at', admin.EmptyFieldListFilter),)
    search_fields = ('user__username',)
    search_help_text = 'Part of the trusted author\'s username.'
    ordering = ('-created_at',)


@admin.register(Check)
class CheckAdmin(Large, ReadOnly):
    """The model's look at a post before it is published: its verdict and its price, never the words."""
    list_display = ('created_at', 'outcome', 'rule', 'failure', 'contribution', 'user', 'model', 'cost_usd', 'ms')
    list_select_related = ('contribution', 'user')
    list_filter = ('outcome', 'rule')
    search_fields = ('user__username',)
    search_help_text = 'Part of the author\'s username.'
    ordering = ('-created_at',)


@admin.register(Notice)
class NoticeAdmin(Large, ReadOnly):
    list_display = ('created_at', 'user', 'kind', 'path', 'contribution', 'seen_at', 'emailed_at', 'letter_due')
    list_select_related = ('user', 'contribution')
    list_filter = ('kind', 'letter_due', ('seen_at', admin.EmptyFieldListFilter))
    search_fields = ('user__username', 'path')
    search_help_text = 'Part of the account\'s username, or of the address it is about.'
    ordering = ('-created_at',)


@admin.register(Point)
class PointAdmin(Large, ReadOnly):
    """The ledger behind titles: the sum is private, so it is read here only."""
    list_display = ('created_at', 'user', 'source', 'ref', 'amount', 'voided_at')
    list_select_related = ('user',)
    list_filter = ('source', ('voided_at', admin.EmptyFieldListFilter))
    search_fields = ('user__username', '=ref')
    search_help_text = 'Part of the account\'s username, or the whole reference.'


@admin.register(Follow)
class FollowAdmin(ReadOnly):
    """Someone follows a discussion (D13): written by writing in it, ended by the person."""
    list_display = ('created_at', 'user', 'path')
    list_select_related = ('user',)
    search_fields = ('user__username', 'path')
    search_help_text = 'Part of the account\'s username, or of the discussion\'s address.'
    ordering = ('-pk',)
