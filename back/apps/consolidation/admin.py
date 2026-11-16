"""The links pipeline in the admin. The doubts are a queue: what the machine could not settle, each opening the amending
text and the text it amends on the site; a person marks it resolved or sets it aside, with a note. The changes are
read from the texts, weighed and applied by the pipeline: they are for looking."""
from django.contrib import admin
from django.db.models import Q
from django.utils import timezone

from apps.consolidation.models import Change, Doubt
from apps.corpus.admin import typed_address
from apps.corpus.services.addresses import text_path
from config.admin import ReadOnly, on_site, site_address


def by_address(queryset, search_term, *fields):
    """A text's address pasted into the search box: the rows that name it in any of `fields`."""
    found = typed_address(search_term)
    if not found:
        return None
    q = Q()
    for field in fields:
        q |= Q(**{field: found[0]})
    return queryset.filter(q)


@admin.register(Doubt)
class DoubtAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'reason', 'status', 'amending', 'amended', 'number', 'by_article')
    list_filter = ('status', 'reason')
    show_facets = admin.ShowFacets.ALWAYS
    search_fields = ('text_uri', 'by_uri', '=number')
    search_help_text = 'Part of either text\'s address (or one pasted from the site), or the article\'s number.'
    fieldsets = [
        ('What the machine could not settle', {'fields': ('reason', 'amending', 'by_article', 'amended', 'number',
                                                          'detail', 'created_at')}),
        ('The decision', {'fields': ('status', 'note', 'resolved_at')}),
    ]
    readonly_fields = ('reason', 'amending', 'by_article', 'amended', 'number', 'detail', 'created_at', 'resolved_at')
    actions = ('mark_resolved', 'set_aside')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_search_results(self, request, queryset, search_term):
        found = by_address(queryset, search_term, 'text_uri', 'by_uri')
        return (found, False) if found is not None else super().get_search_results(request, queryset, search_term)

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data:
            obj.resolved_at = None if obj.status == Doubt.Status.OPEN else timezone.now()
        super().save_model(request, obj, form, change)

    @admin.display(description='amending text', ordering='by_uri')
    def amending(self, obj):
        return on_site(text_path(obj.by_uri), obj.by_uri) if obj.by_uri else '—'

    @admin.display(description='amended text', ordering='text_uri')
    def amended(self, obj):
        return on_site(text_path(obj.text_uri), obj.text_uri) if obj.text_uri else '—'

    @admin.action(permissions=['change'], description='Mark as resolved')
    def mark_resolved(self, request, queryset):
        queryset.update(status=Doubt.Status.RESOLVED, resolved_at=timezone.now())

    @admin.action(permissions=['change'], description='Set aside')
    def set_aside(self, request, queryset):
        queryset.update(status=Doubt.Status.DISMISSED, resolved_at=timezone.now())


@admin.register(Change)
class ChangeAdmin(ReadOnly):
    list_display = ('text_uri', 'number', 'verb', 'by', 'source', 'state', 'effective_on', 'placed', 'verdict', 'score')
    list_filter = ('source', 'state', 'verb', 'effective_rule', 'verdict', 'placed')
    search_fields = ('text_uri', 'by_uri', '=by_number', '=number')
    search_help_text = ('Part of the changed or the changing text\'s address (or one pasted from the site), the '
                        'changing text\'s number, or the article\'s number.')
    ordering = ('-pk',)
    fieldsets = [
        ('What changes', {'fields': ('text_uri', 'number', 'verb', 'wording')}),
        ('By what', {'fields': ('by_kind', 'by_number', 'by_uri', 'by_article', 'issue', 'issue_bis', 'page',
                                'published_on')}),
        ('When it applies', {'fields': ('effective_on', 'effective_rule', 'effective_words')}),
        ('How it was weighed', {'fields': ('source', 'state', 'placed', 'verdict', 'score', 'witnesses', 'detail')}),
    ]

    def view_on_site(self, obj):
        return site_address(text_path(obj.text_uri))

    def get_search_results(self, request, queryset, search_term):
        found = by_address(queryset, search_term, 'text_uri', 'by_uri')
        return (found, False) if found is not None else super().get_search_results(request, queryset, search_term)

    @admin.display(description='by', ordering='by_number')
    def by(self, obj):
        return f'{obj.by_kind} {obj.by_number}'.strip() or '—'
