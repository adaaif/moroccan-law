"""What people add to a contribution: a voice (D4) or pictures (D5). The bytes live under UPLOADS_DIR, never in
a public folder; the row says whose it is and what may see it.

A file is a DRAFT from its upload until the contribution carrying it is published (deleted after DRAFT_HOURS if it
never is), LIVE while that contribution is, EVIDENCE while it is removed or frozen for the reviewers, and ERASED
once the bytes are gone (the row stays, so a contribution can say its voice was erased)."""
import uuid

from django.conf import settings
from django.db import models


class State(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    LIVE = 'live', 'Live'
    EVIDENCE = 'evidence', 'Evidence'
    ERASED = 'erased', 'Erased'


class Clip(models.Model):
    """One recording, at most VOICE_SECONDS, always AAC in MP4 once stored (the browser's WebM/Opus is converted:
    an iPhone plays no WebM). The waveform was measured at the microphone."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    state = models.CharField(max_length=8, choices=State.choices, default=State.DRAFT, db_default=State.DRAFT)
    duration_ms = models.PositiveIntegerField()
    size = models.PositiveIntegerField()
    # 0..1, at most 200 bars.
    peaks = models.JSONField(default=list)
    file_name = models.CharField(max_length=64, blank=True, default='', db_default='')
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    erased_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'media_clip'
        indexes = [models.Index(fields=['state', 'created_at'], name='media_clip_state_idx')]

    def __str__(self):
        return f'clip {self.pk} ({self.state})'


class Picture(models.Model):
    """One picture, re-encoded to WebP in two sizes with no metadata at all (no EXIF, no GPS). Names and numbers
    were blurred in the browser before it left the device."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    state = models.CharField(max_length=8, choices=State.choices, default=State.DRAFT, db_default=State.DRAFT)
    full_name = models.CharField(max_length=64, blank=True, default='', db_default='')
    thumb_name = models.CharField(max_length=64, blank=True, default='', db_default='')
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    # A reviewer covered part of it (M3): the new picture took its place; this one is kept 90 days as evidence.
    replaced_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    erased_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'media_picture'
        indexes = [models.Index(fields=['state', 'created_at'], name='media_picture_state_idx')]

    def __str__(self):
        return f'picture {self.pk} ({self.state})'
