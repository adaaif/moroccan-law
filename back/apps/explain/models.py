"""The people's words beside the law (R8 of the for-everyone review, 19 Oct 2026): one shared explanation for each address
— an article's «باختصار», a text's summary and plain headline, a word's page — in plain Arabic, in Darija or in French,
that anyone who may write can improve, every change kept, reviewed by the text's reviewers, and tied to the version of
the article it explains. It is never shown as law, and no model writes it.

Keyed by address (the site's path), never by a foreign key to Text or Article, which a reload deletes and recreates;
an article's explanation keeps a digest of the words it explained, so it can say the article changed after it."""
from django.conf import settings
from django.db import models

from apps.discussion.models import Report as TalkReport, Rule

PATH_MAX = 300
HEADLINE_MAX = 200
BODY_MAX = 4000
NOTE_MAX = 200
SOURCES_MAX = 12


class Register(models.TextChoices):
    """How it is said: plain standard Arabic, Darija, French. The law stays as printed in every register."""
    AR = 'ar', 'Plain Arabic'
    DARIJA = 'darija', 'Darija'
    FR = 'fr', 'French'


class Explanation(models.Model):
    path = models.CharField(max_length=PATH_MAX)
    register = models.CharField(max_length=8, choices=Register.choices, default=Register.AR, db_default=Register.AR)
    headline = models.CharField(max_length=HEADLINE_MAX, blank=True, default='', db_default='')
    body = models.TextField()
    # The addresses it rests on, beyond its own: «المادتان 32 و33».
    sources = models.JSONField(default=list, blank=True)
    # The article's version and words it explained (an article's explanation only).
    version_on = models.DateField(null=True, blank=True)
    article_digest = models.CharField(max_length=40, blank=True, default='', db_default='')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    # The newest edit waiting for a reviewer. Readers keep the checked words above (headline, body, sources) meanwhile.
    pending = models.ForeignKey('Revision', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    helpful_count = models.PositiveIntegerField(default=0, db_default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'explain_explanation'
        constraints = [models.UniqueConstraint(fields=['path', 'register'], name='explain_one_per_path_register')]
        indexes = [models.Index(fields=['path'])]

    def __str__(self):
        return f'{self.path} ({self.register})'


class Revision(models.Model):
    """Every state the explanation has had, with who wrote it and why. Readers see the states a reviewer checked; one
    that waits, or was never checked, is its author's and the reviewers' to read."""
    explanation = models.ForeignKey(Explanation, on_delete=models.CASCADE, related_name='revisions')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    headline = models.CharField(max_length=HEADLINE_MAX, blank=True, default='', db_default='')
    body = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    note = models.CharField(max_length=NOTE_MAX, blank=True, default='', db_default='')
    # What the discussion's fixed patterns and its check found in it, as the discussion's hold codes; the spans
    # [start, end, code] point into the body.
    held_reasons = models.JSONField(default=list, blank=True)
    held_spans = models.JSONField(default=list, blank=True)
    # A reviewer of its text made it the words readers see.
    checked_at = models.DateTimeField(null=True, blank=True)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    # A reviewer took it out, under one of the site's rules: out of the history and off the page.
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    removed_rule = models.CharField(max_length=12, choices=Rule.choices, blank=True, default='', db_default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'explain_revision'
        ordering = ['-created_at', '-id']


class Report(models.Model):
    """A reader's report of a state of an explanation readers can see, once a person, with the discussion's reasons
    and statuses. The reporter is never shown; a reviewer of the text keeps it or removes the state."""
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    revision = models.ForeignKey(Revision, on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=12, choices=TalkReport.Reason.choices)
    details = models.CharField(max_length=500, blank=True, default='', db_default='')
    status = models.CharField(max_length=8, choices=TalkReport.Status.choices, default=TalkReport.Status.OPEN,
                              db_default=TalkReport.Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        db_table = 'explain_report'
        constraints = [models.UniqueConstraint(fields=['reporter', 'revision'], name='explain_report_once')]
        indexes = [models.Index(fields=['status', 'created_at'], name='explain_report_queue_idx')]


class Helpful(models.Model):
    """«مفيد» on an explanation, as on a contribution: one a person, no downvote; from an account too new or without a
    proven email it is kept and counts nothing."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    explanation = models.ForeignKey(Explanation, on_delete=models.CASCADE, related_name='votes')
    counted = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'explain_helpful'
        constraints = [models.UniqueConstraint(fields=['user', 'explanation'], name='explain_helpful_once')]
