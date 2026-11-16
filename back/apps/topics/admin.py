"""The life topics in the admin, for looking: which items a person checked (the review desk writes them, by
`topics.review_topic`), what readers said helped, and the land texts read as places and plots (`build_land_places`
writes them all again). A topic's day counts of tool use are left out: the weekly reader report sums them."""
from django.contrib import admin

from apps.corpus.admin import typed_address
from apps.corpus.services.addresses import text_path
from apps.topics.models import Helped, ItemCheck, Parcel, PlaceText
from config.admin import ReadOnly, on_site, site_address


@admin.register(ItemCheck)
class ItemCheckAdmin(ReadOnly):
    list_display = ('topic', 'ref', 'by', 'user', 'on', 'at')
    list_select_related = ('user',)
    list_filter = ('topic',)
    search_fields = ('ref', 'by')
    search_help_text = 'Part of the item\'s reference (journeys/marry) or the name it was checked under.'
    ordering = ('topic', 'ref')


@admin.register(Helped)
class HelpedAdmin(ReadOnly):
    list_display = ('created_at', 'path', 'helped', 'reason', 'on_the_site')
    list_filter = ('helped', 'reason', ('created_at', admin.DateFieldListFilter))
    search_fields = ('path',)
    search_help_text = 'Part of the page\'s address: /topics/family/journeys/divorce-agreement.'
    ordering = ('-pk',)

    @admin.display(description='on the site')
    def on_the_site(self, obj):
        return on_site(obj.path, 'open')


def by_uri(queryset, search_term):
    found = typed_address(search_term)
    return queryset.filter(uri=found[0]) if found else None


@admin.register(PlaceText)
class PlaceTextAdmin(ReadOnly):
    list_display = ('date', 'uri', 'kind', 'issue', 'page', 'short_title', 'rows')
    list_filter = ('kind',)
    search_fields = ('title', '=issue')
    search_help_text = 'A text\'s address, part of its title, or its issue\'s number.'
    ordering = ('-date',)
    exclude = ('search',)

    def view_on_site(self, obj):
        return site_address(text_path(obj.uri))

    def get_search_results(self, request, queryset, search_term):
        found = by_uri(queryset, search_term)
        return (found, False) if found is not None else super().get_search_results(request, queryset, search_term)

    @admin.display(description='title')
    def short_title(self, obj):
        return obj.title[:90]


@admin.register(Parcel)
class ParcelAdmin(ReadOnly):
    list_display = ('uri', 'row', 'plot', 'ref', 'area', 'owners_count')
    search_fields = ('=ref', '=plot')
    search_help_text = 'A text\'s address, or a whole title or requisition number as kept (f18820), or a plot\'s.'
    ordering = ('uri', 'row')

    def view_on_site(self, obj):
        return site_address(text_path(obj.uri))

    def get_search_results(self, request, queryset, search_term):
        found = by_uri(queryset, search_term)
        return (found, False) if found is not None else super().get_search_results(request, queryset, search_term)
