"""The quality queues in the admin: readers' reports, open first, each opening its article on the site; the corrections
a person applies or sets aside (the machine only proposes, R7); the words a reading may have wrong (FX9). A person
decides through the actions, which write through the services (a correction applied is applied again after every
reload); the form changes only the words a person may put right before deciding and the notes."""
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, F, Q
from django.utils import timezone
from django.utils.html import format_html

from apps.accounts.services.refusals import Refused
from apps.quality.models import Correction, Report, Suspect
from apps.quality.services import corrections
from config.admin import on_site


class Queue(admin.ModelAdmin):
    """Rows readers or the machine write and a person decides: none added or deleted here."""
    show_facets = admin.ShowFacets.ALWAYS

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Report)
class ReportAdmin(Queue):
    list_display = ('created_at', 'kind', 'status', 'article', 'quote')
    list_filter = ('status', 'kind')
    search_fields = ('path', 'quote', 'message')
    search_help_text = 'Part of the article\'s address, the words quoted or the reader\'s message.'
    fields = ('path', 'article', 'kind', 'quote', 'message', 'created_at', 'status', 'note', 'resolved_at')
    readonly_fields = ('path', 'article', 'kind', 'quote', 'message', 'created_at', 'resolved_at')
    actions = ('mark_fixed', 'set_aside')

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data:
            obj.resolved_at = None if obj.status == Report.Status.OPEN else timezone.now()
        super().save_model(request, obj, form, change)

    @admin.display(description='article', ordering='path')
    def article(self, obj):
        return on_site(obj.path)

    @admin.action(permissions=['change'], description='Mark as fixed')
    def mark_fixed(self, request, queryset):
        queryset.update(status=Report.Status.FIXED, resolved_at=timezone.now())

    @admin.action(permissions=['change'], description='Set aside')
    def set_aside(self, request, queryset):
        queryset.update(status=Report.Status.DISMISSED, resolved_at=timezone.now())


@admin.register(Correction)
class CorrectionAdmin(Queue):
    """Applying writes the article through `corrections.apply`; a status typed in the form would not, so the status is
    set by the actions alone. The right words may be put right first."""
    list_display = ('created_at', 'status', 'source', 'article', 'wrong', 'right', 'before', 'after', 'decided_by')
    list_select_related = ('decided_by',)
    list_filter = ('status', 'source')
    search_fields = ('path', 'wrong', 'right')
    search_help_text = 'Part of the article\'s address, the wrong words or the right ones.'
    fieldsets = [
        ('Where', {'fields': ('path', 'article', 'before', 'after')}),
        ('The words', {'fields': ('wrong', 'right')}),
        ('Why', {'fields': ('source', 'evidence', 'report', 'created_at')}),
        ('The decision', {'fields': ('status', 'decided_by', 'decided_at')}),
    ]
    readonly_fields = ('path', 'article', 'wrong', 'before', 'after', 'source', 'evidence', 'report', 'status',
                       'decided_by', 'decided_at', 'created_at')
    actions = ('apply_them', 'set_them_aside')

    @admin.display(description='article', ordering='path')
    def article(self, obj):
        return on_site(obj.path)

    @admin.action(permissions=['change'], description='Apply (I checked each against the printed page)')
    def apply_them(self, request, queryset):
        for c in queryset:
            try:
                corrections.apply(request.user, c.pk)
            except Refused:
                self.message_user(request, f'Not found in the text any more: {c}')

    @admin.action(permissions=['change'], description='Set aside')
    def set_them_aside(self, request, queryset):
        for c in queryset:
            corrections.reject(request.user, c.pk)


SAYS = ('suggestion', 'word', 'neither', 'unclear')


class Said(admin.SimpleListFilter):
    """What the people asked on «ساهم» said, once WORD_ANSWERS of them answered, or while fewer did."""
    title = 'what people said'
    parameter_name = 'said'

    def lookups(self, request, model_admin):
        n = settings.WORD_ANSWERS
        return [('suggestion', f'{n} agreed on the suggestion'), ('word', f'{n} agreed on the word as it stands'),
                ('disagree', 'People disagree'), ('asking', f'Asked, not yet {n}')]

    def queryset(self, request, queryset):
        n = settings.WORD_ANSWERS
        if self.value() in ('suggestion', 'word'):
            return queryset.filter(**{f'said_{self.value()}__gte': n}, asked=F(f'said_{self.value()}'))
        if self.value() == 'disagree':
            return queryset.filter(asked__gte=n).exclude(said_suggestion=F('asked')).exclude(said_word=F('asked'))
        if self.value() == 'asking':
            return queryset.filter(asked__gt=0, asked__lt=n)
        return queryset


@admin.register(Suspect)
class SuspectAdmin(Queue):
    """FX9 of the mended-Bulletin review: words a reading may have wrong, to read against the page image and confirm (the
    suggestion is put in place in the page and its articles) or set aside. The suggestion may be put right first. A
    word placed on its page shows its printed line, and what the people asked on «ساهم» said (counted in the list's
    one query)."""
    list_display = ('word', 'suggestion', 'line', 'said', 'signal', 'status', 'context', 'on_page')
    list_select_related = ('page__document__issue',)
    list_filter = (Said, 'signal', 'status')
    search_fields = ('word', 'suggestion', 'context')
    search_help_text = 'Part of the word, its suggestion or the words around it.'
    fieldsets = [
        ('The word', {'fields': ('word', 'context', 'page', 'on_page', 'signal', 'evidence', 'created_at')}),
        ('On its printed page', {'fields': ('line', 'said', 'asked')}),
        ('What it should be', {'fields': ('suggestion',)}),
        ('The decision', {'fields': ('status', 'decided_by', 'decided_at')}),
    ]
    readonly_fields = ('word', 'context', 'page', 'on_page', 'signal', 'evidence', 'status', 'decided_by',
                       'decided_at', 'created_at', 'line', 'said', 'asked')
    actions = ('confirm', 'set_aside')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('page__document__issue').annotate(
            **{f'said_{k}': Count('answers', filter=Q(answers__says=k)) for k in SAYS})

    @admin.display(description='printed line')
    def line(self, s):
        if not (s.place or {}).get('box'):
            return '—'
        return format_html('<img src="/api/quality/words/{}/strip/" alt="" loading="lazy" style="height:40px">', s.pk)

    @admin.display(description='people said', ordering='asked')
    def said(self, s):
        counts = [(k, getattr(s, f'said_{k}', 0)) for k in SAYS]
        return ', '.join(f'{k} {n}' for k, n in counts if n) or '—'

    @admin.display(description='page')
    def on_page(self, s):
        try:
            issue = s.page.document.issue
        except ObjectDoesNotExist:          # a file that is no issue of the Bulletin
            return on_site(f'/pages/{s.page.document_id}/{s.page.index}', f'p. {s.page.index + 1}')
        page = s.page.printed_number or s.page.index + 1
        return on_site(f'/bo/{issue.edition}/{issue.key}', f'BO {issue.key} p. {page}')

    @admin.action(permissions=['change'], description='Confirm: put the suggestion in place (page and articles)')
    def confirm(self, request, queryset):
        from apps.quality.services.suspects import confirm
        done = changed = 0
        for s in queryset.filter(status=Suspect.Status.OPEN).exclude(suggestion=''):
            changed += confirm(s, request.user)
            done += 1
        self.message_user(request, f'{done} confirmed, {changed} articles put right')

    @admin.action(permissions=['change'], description='Set aside: the reading was right')
    def set_aside(self, request, queryset):
        n = queryset.filter(status=Suspect.Status.OPEN).update(status=Suspect.Status.REJECTED, decided_by=request.user,
                                                                decided_at=timezone.now())
        self.message_user(request, f'{n} set aside')
