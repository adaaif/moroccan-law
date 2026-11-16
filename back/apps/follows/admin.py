"""What accounts follow (R13), for looking: written by following on the site, and by the letters that tell what
changed."""
from django.contrib import admin

from apps.follows.models import Follow
from config.admin import ReadOnly, on_site


@admin.register(Follow)
class FollowAdmin(ReadOnly):
    list_display = ('created_at', 'user', 'path', 'on_the_site')
    list_select_related = ('user',)
    search_fields = ('user__username', 'path')
    search_help_text = 'Part of the account\'s username, or of the address followed.'
    ordering = ('-pk',)
    fields = ('user', 'path', 'created_at', 'told')

    @admin.display(description='on the site')
    def on_the_site(self, obj):
        return on_site(obj.path, 'open')
