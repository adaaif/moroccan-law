"""The places the Bulletin names, for looking: `build_places` writes them all again from data/places.json and the
count. Their mentions and their counts by year are left out: the place's page on the site reads them."""
from django.contrib import admin

from apps.places.models import Place
from config.admin import ReadOnly, on_site, site_address


@admin.register(Place)
class PlaceAdmin(ReadOnly):
    list_display = ('name_ar', 'name_fr', 'kind', 'parent', 'texts', 'population', 'on_the_site')
    list_filter = ('kind',)
    search_fields = ('name_ar', 'name_fr', 'name_en', '=slug', '=code')
    search_help_text = 'Part of its Arabic, French or English name; or its whole slug or code.'
    ordering = ('kind', '-texts')
    fieldsets = [
        ('The place', {'fields': ('slug', 'kind', 'name_ar', 'name_fr', 'name_en', 'code', 'region', 'parent', 'town',
                                  'successor', 'lat', 'lon', 'population', 'foreigners')}),
        ('What the count found', {'fields': ('texts', 'first', 'spellings')}),
        ('The names it is looked for by', {'classes': ('collapse',), 'fields': ('forms', 'old', 'latin')}),
    ]

    def view_on_site(self, obj):
        return site_address(f'/places/{obj.slug}')

    @admin.display(description='on the site')
    def on_the_site(self, obj):
        return on_site(f'/places/{obj.slug}', 'open')
