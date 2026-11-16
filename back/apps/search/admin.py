"""Search in the admin, for looking: what readers typed and what it found (the empty ones teach the everyday words),
with what they did next; and the index's own rows, rebuilt from the corpus by `build_search_index`. The meaning
model's passages are left out: vectors, rebuilt by their command."""
from django.contrib import admin

from apps.corpus.admin import typed_address
from apps.corpus.services.addresses import article_path, text_path
from apps.search.models import SearchEntry, SearchLog
from config.admin import Large, ReadOnly, on_site, rows_table

SHOWN = 30


class AnsweredFilter(admin.SimpleListFilter):
    title, parameter_name = 'answered', 'answered'

    def lookups(self, request, model_admin):
        return [('no', 'found nothing'), ('yes', 'found something')]

    def queryset(self, request, queryset):
        if self.value() == 'no':
            return queryset.filter(results=0)
        if self.value() == 'yes':
            return queryset.filter(results__gt=0)
        return queryset


class ViaFilter(admin.SimpleListFilter):
    title, parameter_name = 'asked by', 'via'

    def lookups(self, request, model_admin):
        return [('site', 'a reader on the site'), ('mcp', 'an assistant')]

    def queryset(self, request, queryset):
        if self.value() == 'site':
            return queryset.filter(via='')
        if self.value() == 'mcp':
            return queryset.filter(via='mcp')
        return queryset


@admin.register(SearchLog)
class SearchLogAdmin(Large, ReadOnly):
    list_display = ('at', 'query', 'results', 'understood_as', 'opened', 'via')
    list_filter = (AnsweredFilter, ViaFilter, ('at', admin.DateFieldListFilter))
    search_fields = ('query',)
    search_help_text = 'Part of what was typed.'
    ordering = ('-pk',)
    fields = ('query', 'folded', 'understood_as', 'results', 'opened', 'shown', 'via', 'at', 'events_table')
    readonly_fields = ('events_table',)

    @admin.display(description='what the reader did next')
    def events_table(self, obj):
        rows = list(obj.events.order_by('at', 'pk')[:SHOWN])
        return rows_table(('when', 'what', 'answer', 'rank', 'seconds'),
                          [(f'{e.at:%H:%M:%S}', e.get_kind_display(), on_site(e.path) if e.path else '—',
                            e.rank or '—', e.seconds or '—') for e in rows])


@admin.register(SearchEntry)
class SearchEntryAdmin(Large, ReadOnly):
    list_display = ('path', 'kind', 'label', 'text_type', 'year', 'in_force', 'in_corpus', 'weight')
    list_filter = ('kind', 'in_force', 'in_corpus')
    search_fields = ('=path', '=text_path')
    search_help_text = 'A text\'s or an article\'s address (/ma/loi/2013/67-12, /ma/loi/2013/67-12/art_34).'
    fieldsets = [
        ('The row', {'fields': ('kind', 'path', 'text_path', 'eid', 'label', 'order', 'title', 'name',
                                'number_as_printed', 'issue', 'page')}),
        ('What it weighs', {'fields': ('text_type', 'year', 'signed_year', 'in_force', 'in_corpus', 'status', 'weight',
                                       'version_from', 'consolidation', 'changes')}),
        ('Its words', {'classes': ('collapse',), 'fields': ('heading_path', 'body')}),
        ('The terms indexed', {'classes': ('collapse',), 'fields': ('terms', 'title_terms', 'lemma_terms',
                                                                    'title_folded')}),
    ]

    def get_search_results(self, request, queryset, search_term):
        found = typed_address(search_term)
        if found:
            uri, eid = found
            path = article_path(uri, eid) if eid else text_path(uri)
            return queryset.filter(path=path), False
        return super().get_search_results(request, queryset, search_term)
