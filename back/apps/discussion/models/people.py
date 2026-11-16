"""What a person gives and is told beside their words: «مفيد» and the points it earns, what they follow, their
notices."""
from django.conf import settings
from django.db import models

from apps.discussion.models.posts import PATH_MAX, Contribution


class Useful(models.Model):
    """«مفيد» (D2), the one vote. It ranks only from an account with a proven email, three days old when it voted
    (`counted`); the others are kept and shown nowhere."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    contribution = models.ForeignKey(Contribution, on_delete=models.CASCADE, related_name='votes')
    counted = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discussion_useful'
        constraints = [models.UniqueConstraint(fields=['user', 'contribution'], name='discussion_useful_once')]


class Point(models.Model):
    """The ledger behind titles: a point per counted «مفيد», five per «أفادني». A removal voids the points the
    contribution earned and a restore gives them back. The sum is private; others see the title."""

    class Source(models.TextChoices):
        USEFUL = 'useful', 'A counted «مفيد»'
        ACCEPTED = 'accepted', 'An answer the asker marked'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    source = models.CharField(max_length=8, choices=Source.choices)
    ref = models.CharField(max_length=40)
    amount = models.SmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    voided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'discussion_point'
        constraints = [models.UniqueConstraint(fields=['source', 'ref'], name='discussion_point_once')]
        indexes = [models.Index(fields=['user', 'voided_at'], name='discussion_point_user_idx')]


class Follow(models.Model):
    """Someone follows an article's discussion: an email when someone writes there (D13, phase 3). Writing in a
    discussion follows it."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    path = models.CharField(max_length=PATH_MAX)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discussion_follow'
        constraints = [models.UniqueConstraint(fields=['user', 'path'], name='discussion_follow_once')]


class Notice(models.Model):
    """What a person is told: an answer, a new contribution where they follow, a decision about their words."""

    class Kind(models.TextChoices):
        ANSWER = 'answer', 'Someone answered'
        NEW = 'new', 'New in a followed discussion'
        ACCEPTED = 'accepted', 'The asker marked the answer'
        APPROVED = 'approved', 'A held contribution was published'
        REMOVED = 'removed', 'A contribution was removed'
        RESTORED = 'restored', 'A contribution was restored'
        REPORT = 'report', 'A report was decided'
        BANNED = 'banned', 'Writing paused'
        APPEAL = 'appeal', 'An appeal was decided'
        BADGE = 'badge', 'A profession badge was decided'
        SENT_BACK = 'sent_back', 'A reviewer asks for an edit'
        REDACTED = 'redacted', 'A reviewer removed words'
        DUPLICATE = 'duplicate', 'A question was marked as a repeat'
        DIGEST = 'digest', 'Contributions wait for review'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notices')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    path = models.CharField(max_length=PATH_MAX, blank=True, default='', db_default='')
    contribution = models.ForeignKey(Contribution, null=True, blank=True, on_delete=models.CASCADE, related_name='+')
    # A rule, an outcome, a profession: what the sentence needs.
    detail = models.CharField(max_length=40, blank=True, default='', db_default='')
    created_at = models.DateTimeField(auto_now_add=True)
    seen_at = models.DateTimeField(null=True, blank=True)
    # When its letter was claimed (the six hours between two letters count from it); `letter_due` until the job
    # `send_notice_letters` sends it: no letter leaves inside the request that made the notice.
    emailed_at = models.DateTimeField(null=True, blank=True)
    letter_due = models.BooleanField(default=False, db_default=False)

    class Meta:
        db_table = 'discussion_notice'
        indexes = [models.Index(fields=['user', '-created_at'], name='discussion_notice_user_idx'),
                   models.Index(fields=['created_at'], condition=models.Q(letter_due=True),
                                name='discussion_notice_due_idx')]
