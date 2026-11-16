"""Finance laws as checked data, for looking: `load_finance_law` reads each law's figures from its articles and
tables and re-does its arithmetic (services/checks.py); a table is shown on the site only when every check passes."""
from django.contrib import admin

from apps.budget.models import FinanceLaw, Line
from config.admin import ReadOnly, changelist_link, site_address


@admin.register(FinanceLaw)
class FinanceLawAdmin(ReadOnly):
    list_display = ('year', 'kind', 'number', 'title', 'text', 'checked_at', 'checks_passed')
    list_select_related = ('text',)
    list_filter = ('kind',)
    search_fields = ('=number', 'title')
    search_help_text = 'A law\'s whole number, or part of its title.'
    fieldsets = [
        ('The law', {'fields': ('year', 'kind', 'number', 'title', 'text', 'document', 'checked_at', 'its_lines')}),
        ('Its figures, their sources and their checks', {'classes': ('collapse',),
                                                         'fields': ('stated', 'sources', 'checks')}),
    ]
    readonly_fields = ('its_lines',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('text', 'document')

    def view_on_site(self, obj):
        return site_address(f'/budget/{obj.year}')

    @admin.display(description='checks passed')
    def checks_passed(self, obj):
        checks = obj.checks or []
        return f'{sum(1 for c in checks if c.get("ok"))} / {len(checks)}' if checks else '—'

    @admin.display(description='lines')
    def its_lines(self, obj):
        return changelist_link(Line, 'its lines', finance_law=obj.pk)


@admin.register(Line)
class LineAdmin(ReadOnly):
    list_display = ('finance_law', 'table', 'order', 'code', 'section', 'label', 'amount', 'commitment', 'is_total',
                    'page')
    list_select_related = ('finance_law',)
    list_filter = ('finance_law', 'table', 'is_total')
    search_fields = ('label', '=code')
    search_help_text = 'Part of the line\'s label, or its whole code.'
