"""The official French translation as read from the French Bulletin, for looking: `load_bo_french` reads it, a text
at a time, and keeps it by the Arabic text's address."""
from django.contrib import admin

from apps.corpus.admin import typed_address
from apps.corpus.services.addresses import text_path
from apps.translations.models import FrenchArticle, FrenchText
from config.admin import ReadOnly, admin_link, changelist_link, rows_table, site_address

SHOWN = 20


def by_text(queryset, search_term):
    found = typed_address(search_term)
    return queryset.filter(text_uri=found[0]) if found else None


@admin.register(FrenchText)
class FrenchTextAdmin(ReadOnly):
    list_display = ('title', 'number', 'issue_number', 'issue_date', 'text_uri')
    search_fields = ('title', '=number', '=issue_number')
    search_help_text = ('The Arabic text\'s address (or one pasted from the site), part of the French title, or a '
                        'whole number: the text\'s or its issue\'s.')
    ordering = ('-issue_date', '-pk')
    fields = ('text_uri', 'type', 'number', 'title', 'signed_on', 'issue_number', 'issue_suffix', 'issue_date',
              'pages', 'document_sha', 'consolidated_to', 'loaded_at', 'articles_table')
    readonly_fields = ('articles_table',)

    def view_on_site(self, obj):
        return site_address(text_path(obj.text_uri))

    def get_search_results(self, request, queryset, search_term):
        found = by_text(queryset, search_term)
        return (found, False) if found is not None else super().get_search_results(request, queryset, search_term)

    @admin.display(description='articles (in order)')
    def articles_table(self, obj):
        rows = list(FrenchArticle.objects.filter(text_uri=obj.text_uri).order_by('order')
                    .only('pk', 'order', 'label', 'printed_page')[:SHOWN + 1])
        more = changelist_link(FrenchArticle, 'every article', text_uri=obj.text_uri) if len(rows) > SHOWN else None
        return rows_table(('order', 'label', 'page'),
                          [(a.order, admin_link(a, a.label), a.printed_page or '—') for a in rows[:SHOWN]], more)


@admin.register(FrenchArticle)
class FrenchArticleAdmin(ReadOnly):
    list_display = ('label', 'text_uri', 'order', 'printed_page')
    search_fields = ('=number',)
    search_help_text = 'The Arabic text\'s address (or an article\'s, pasted from the site), or an article\'s number.'
    ordering = ('text_uri', 'order')

    def view_on_site(self, obj):
        return site_address(text_path(obj.text_uri))

    def get_search_results(self, request, queryset, search_term):
        found = typed_address(search_term)
        if found:
            uri, eid = found
            rows = queryset.filter(text_uri=uri)
            return (rows.filter(number=eid.removeprefix('art_')) if eid else rows), False
        return super().get_search_results(request, queryset, search_term)
