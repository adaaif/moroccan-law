"""Voices and pictures people added, for looking: whose, in what state and which post or comment carries them. Their
state follows the contribution's through the review desk; the files are never served from here."""
from django.contrib import admin

from apps.discussion.models import Contribution
from apps.media.models import Clip, Picture
from config.admin import ReadOnly, changelist_link


class MediaAdmin(ReadOnly):
    list_select_related = ('owner',)
    list_filter = ('state', ('created_at', admin.DateFieldListFilter))
    search_fields = ('owner__username',)
    search_help_text = 'Part of the username of the account that added it.'
    ordering = ('-created_at',)


@admin.register(Clip)
class ClipAdmin(MediaAdmin):
    list_display = ('created_at', 'owner', 'state', 'seconds', 'size', 'published_at', 'erased_at')
    fields = ('owner', 'state', 'duration_ms', 'size', 'file_name', 'created_at', 'published_at', 'erased_at',
              'carried_by')
    readonly_fields = ('carried_by',)

    @admin.display(description='seconds', ordering='duration_ms')
    def seconds(self, obj):
        return round(obj.duration_ms / 1000, 1)

    @admin.display(description='carried by')
    def carried_by(self, obj):
        return changelist_link(Contribution, 'the post or comment', clip=obj.pk)


@admin.register(Picture)
class PictureAdmin(MediaAdmin):
    list_display = ('created_at', 'owner', 'state', 'width', 'height', 'replaced_by', 'published_at', 'erased_at')
    list_select_related = ('owner', 'replaced_by')
    fields = ('owner', 'state', 'width', 'height', 'full_name', 'thumb_name', 'replaced_by', 'created_at',
              'published_at', 'erased_at', 'carried_by')
    readonly_fields = ('carried_by',)

    @admin.display(description='carried by')
    def carried_by(self, obj):
        return changelist_link(Contribution, 'the posts or comments', pictures=obj.pk)
