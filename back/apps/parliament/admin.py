"""The bills' explanatory memoranda as read from Parliament's files, for looking: a command reads them."""
from django.contrib import admin

from apps.corpus.admin import typed_address
from apps.corpus.services.addresses import text_path
from apps.parliament.models import Explanation
from config.admin import ReadOnly, site_address


@admin.register(Explanation)
class ExplanationAdmin(ReadOnly):
    list_display = ('text_uri', 'kind', 'pages', 'read_at')
    list_filter = ('kind',)
    search_fields = ('text_uri', 'body')
    search_help_text = 'Part of the text\'s address (or one pasted from the site), or of the memorandum\'s words.'
    ordering = ('-read_at',)

    def view_on_site(self, obj):
        return site_address(text_path(obj.text_uri))

    def get_search_results(self, request, queryset, search_term):
        found = typed_address(search_term)
        if found:
            return queryset.filter(text_uri=found[0]), False
        return super().get_search_results(request, queryset, search_term)
