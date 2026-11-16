"""The assistants' connections, for looking: the clients as they identified themselves and each person's grants, with
what they did day by day. A person ends a grant from their account page; codes, tokens and requests are kept only as
digests and are left out."""
from django.contrib import admin

from apps.oauth.models import Client, Grant
from config.admin import ReadOnly, changelist_link, rows_table

SHOWN = 30


@admin.register(Client)
class ClientAdmin(ReadOnly):
    list_display = ('name', 'domain', 'kind', 'created_at', 'used_at')
    list_filter = ('kind',)
    search_fields = ('name', 'domain', 'client_id')
    search_help_text = 'Part of its name, its redirects\' domain or its client id.'
    ordering = ('-pk',)
    fields = ('name', 'domain', 'kind', 'client_id', 'redirect_uris', 'created_at', 'fetched_at', 'used_at', 'grants')
    readonly_fields = ('grants',)

    @admin.display(description='connections')
    def grants(self, obj):
        return changelist_link(Grant, 'its connections', client=obj.pk)


@admin.register(Grant)
class GrantAdmin(ReadOnly):
    list_display = ('created_at', 'user', 'client', 'used_at', 'revoked_at')
    list_select_related = ('user', 'client')
    list_filter = (('revoked_at', admin.EmptyFieldListFilter),)
    search_fields = ('user__username', 'client__name')
    search_help_text = 'Part of the account\'s username or the assistant\'s name.'
    ordering = ('-pk',)
    fields = ('user', 'client', 'scope', 'resource', 'created_at', 'used_at', 'revoked_at', 'days_table')
    readonly_fields = ('days_table',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'client')

    @admin.display(description='its days, newest first')
    def days_table(self, obj):
        rows = list(obj.days.order_by('-day')[:SHOWN])
        return rows_table(('day', 'calls', 'articles', 'tools'),
                          [(d.day, d.calls, d.articles, ', '.join(f'{k} {v}' for k, v in sorted(d.tools.items())))
                           for d in rows])
