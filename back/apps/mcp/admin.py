"""The assistants' shares: each time a platform spent half its share for the hour or the day (a sign to widen the
share), written by the quotas, read here."""
from django.contrib import admin

from apps.mcp.models import Alert
from config.admin import ReadOnly


@admin.register(Alert)
class AlertAdmin(ReadOnly):
    list_display = ('at', 'origin', 'share', 'period', 'limit')
    list_filter = ('share', 'period')
    search_fields = ('origin',)
    search_help_text = 'Part of the platform\'s name.'
    date_hierarchy = 'at'
    ordering = ('-at',)
