"""Who looks after the words and what they do: reviewers, readers' reports, the ledger of every act of power,
pauses, appeals, trusted authors, and the model's check before a post or a comment is published."""
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.discussion.models.posts import APPEAL_MAX, NOTE_MAX, PATH_MAX, Contribution, Rule


class Reviewer(models.Model):
    """Someone staff appointed to review contributions (D10), for some texts (their paths) or for all (none)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    text_paths = models.JSONField(default=list, blank=True)
    appointed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='+')
    appointed_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'discussion_reviewer'
        constraints = [models.UniqueConstraint(fields=['user'], condition=Q(ended_at=None),
                                               name='discussion_reviewer_one_live')]

    def __str__(self):
        return f'reviewer {self.user_id}'


class Report(models.Model):
    """A reader's report of a contribution, once per person and contribution. A report names only the
    contribution; the reporter is never shown to its author. The reporter is told: waiting, acted on, or reviewed,
    never "dismissed"."""

    class Reason(models.TextChoices):
        EXPOSING = 'exposing', 'Exposes someone’s personal information'
        ABUSE = 'abuse', 'Insult or harassment'
        SOLICITING = 'soliciting', 'Advertising or soliciting clients'
        FRAUD = 'fraud', 'Fraud or a call to break the law'
        SEXUAL = 'sexual', 'Sexual or violent content'
        OFF_TOPIC = 'off_topic', 'Repeated or off the article'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        ACTED = 'acted', 'Acted on'
        REVIEWED = 'reviewed', 'Reviewed'

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='+')
    contribution = models.ForeignKey(Contribution, on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=12, choices=Reason.choices)
    # «عند 1:24»: the moment in a voice.
    moment_ms = models.PositiveIntegerField(null=True, blank=True)
    details = models.CharField(max_length=NOTE_MAX, blank=True, default='', db_default='')
    # A person named in a contribution asking for it to go, with or without an account (M11, law 09-08): how to
    # reach them, as they gave it. Seen by reviewers only.
    takedown = models.BooleanField(default=False, db_default=False)
    contact = models.CharField(max_length=200, blank=True, default='', db_default='')
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN, db_default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='+')

    class Meta:
        db_table = 'discussion_report'
        constraints = [models.UniqueConstraint(fields=['reporter', 'contribution'], name='discussion_report_once')]
        indexes = [models.Index(fields=['status', 'created_at'], name='discussion_report_queue_idx')]


class Action(models.Model):
    """The ledger: every act of power is a row, written in the same transaction as the act."""

    class Verb(models.TextChoices):
        APPROVE = 'approve', 'Published a held contribution'
        KEEP = 'keep', 'Kept after reports'
        REMOVE = 'remove', 'Removed'
        RESTORE = 'restore', 'Restored'
        LOCK = 'lock', 'Locked a discussion'
        UNLOCK = 'unlock', 'Unlocked a discussion'
        BAN = 'ban', 'Paused writing'
        BAN_ASK = 'ban_ask', 'Asked for a permanent pause'
        BAN_CONFIRM = 'ban_confirm', 'Confirmed a permanent pause'
        UNBAN = 'unban', 'Lifted a pause'
        APPEAL_LIFT = 'appeal_lift', 'Appeal: lifted'
        APPEAL_KEEP = 'appeal_keep', 'Appeal: kept'
        REVEAL = 'reveal', 'Revealed an anonymous author'
        APPOINT = 'appoint', 'Appointed a reviewer'
        DISMISS = 'dismiss', 'Ended a reviewer'
        BADGE = 'badge', 'Granted a profession badge'
        BADGE_REFUSE = 'badge_refuse', 'Refused a profession badge'
        BADGE_END = 'badge_end', 'Ended a profession badge'
        REDACT = 'redact', 'Removed words or part of a picture'
        SEND_BACK = 'send_back', 'Sent back to its author'
        CHECK = 'check', 'Looked at after publication'
        TRUST = 'trust', 'Trusted an author'
        UNTRUST = 'untrust', 'Ended a trust'
        DUPLICATE = 'duplicate', 'Marked a repeated question'
        HIDE = 'hide', 'Hidden after serious reports'

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='+')
    verb = models.CharField(max_length=12, choices=Verb.choices)
    contribution = models.ForeignKey(Contribution, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='+')
    path = models.CharField(max_length=PATH_MAX, blank=True, default='', db_default='')
    target = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name='+')
    # The act concerned an anonymous author: a reviewer's ledger never names them.
    target_hidden = models.BooleanField(default=False, db_default=False)
    rule = models.CharField(max_length=12, choices=Rule.choices, blank=True, default='', db_default='')
    note = models.CharField(max_length=NOTE_MAX, blank=True, default='', db_default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discussion_action'
        indexes = [models.Index(fields=['-created_at'], name='discussion_ledger_idx')]


class Ban(models.Model):
    """A pause on writing, voting and reporting (reading never pauses): 3, 7 or 28 days, or for good. A reviewer
    who asks for good waits for a second reviewer or staff («جوج عينين»); meanwhile 28 days run."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    until = models.DateTimeField(null=True, blank=True)
    permanent_asked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                           on_delete=models.SET_NULL, related_name='+')
    rule = models.CharField(max_length=12, choices=Rule.choices)
    note = models.CharField(max_length=NOTE_MAX, blank=True, default='', db_default='')
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                           related_name='+')
    # Through an anonymous contribution: the reviewer never learns who.
    via = models.ForeignKey(Contribution, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'discussion_ban'
        indexes = [models.Index(fields=['user', 'ended_at'], name='discussion_ban_user_idx')]


class Appeal(models.Model):
    """One written appeal against a removal or a pause, decided by someone other than who acted."""

    class Outcome(models.TextChoices):
        LIFTED = 'lifted', 'Lifted'
        KEPT = 'kept', 'Kept'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    contribution = models.OneToOneField(Contribution, null=True, blank=True, on_delete=models.CASCADE,
                                        related_name='appeal')
    ban = models.OneToOneField(Ban, null=True, blank=True, on_delete=models.CASCADE, related_name='appeal')
    text = models.TextField(max_length=APPEAL_MAX)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='+')
    outcome = models.CharField(max_length=6, choices=Outcome.choices, blank=True, default='', db_default='')

    class Meta:
        db_table = 'discussion_appeal'
        constraints = [models.CheckConstraint(
            condition=Q(contribution__isnull=False, ban__isnull=True) | Q(contribution__isnull=True, ban__isnull=False),
            name='discussion_appeal_one_target')]


class Trust(models.Model):
    """An author a reviewer trusts (M8): no newcomer's wait, pictures published at once. Any removal of their words
    ends it."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'discussion_trust'
        constraints = [models.UniqueConstraint(fields=['user'], condition=Q(ended_at=None),
                                               name='discussion_trust_one_live')]


class Check(models.Model):
    """The model's look at a post or a comment before it is published (29 Oct 2026): its verdict, never
    its words. Kept 90 days for appeals and the month's numbers; what it cost counts against the month's budget. A
    returned post is not kept: only that it was returned, and under which rule."""

    class Outcome(models.TextChoices):
        PUBLISH = 'publish', 'Published'
        RETURN = 'return', 'Returned to its author'
        HOLD = 'hold', 'Held for a moderator'
        UNAVAILABLE = 'unavailable', 'The check could not run: held'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='+')
    contribution = models.ForeignKey(Contribution, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='checks')
    outcome = models.CharField(max_length=12, choices=Outcome.choices)
    rule = models.CharField(max_length=12, choices=Rule.choices, blank=True, default='', db_default='')
    # Why it could not run: timeout, error, refusal, budget, no_key, limit (the account's looks for the day are spent).
    failure = models.CharField(max_length=12, blank=True, default='', db_default='')
    model = models.CharField(max_length=40, blank=True, default='', db_default='')
    prompt_version = models.CharField(max_length=12, blank=True, default='', db_default='')
    input_tokens = models.PositiveIntegerField(default=0, db_default=0)
    output_tokens = models.PositiveIntegerField(default=0, db_default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0, db_default=0)
    ms = models.PositiveIntegerField(default=0, db_default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discussion_check'
        indexes = [models.Index(fields=['created_at'], name='discussion_check_when_idx')]
