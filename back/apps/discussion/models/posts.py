"""A place's discussion and what is written in it: posts and the comments under them, the articles they cite, their
earlier wordings; the limits on what is written, its kinds, and the site's rules a removal names."""
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Coalesce

PATH_MAX = 300
TITLE_MAX = 140
BODY_MAX = 3000
QUOTE_MAX = 500
PICTURES_MAX = 3
NOTE_MAX = 500
APPEAL_MAX = 1000


class Kind(models.TextChoices):
    """A post is a question or a post (C4 of 29 Oct 2026); what is written under it is a comment. The other three are
    the kinds of the article threads before, kept for their rows."""
    QUESTION = 'question', 'Question'
    POST = 'post', 'Post'
    COMMENT = 'comment', 'Comment'
    EXPLANATION = 'explanation', 'Explanation'
    EXPERIENCE = 'experience', 'Experience'
    SOURCE = 'source', 'Source'
    REMARK = 'remark', 'Remark'


POST_KINDS = (Kind.QUESTION, Kind.POST)


class Rule(models.TextChoices):
    """The site's rules, in the order the rules page prints them: a removal names one, and the author is told
    which."""
    PRIVACY = 'privacy', '1. Nobody’s personal information'
    RESPECT = 'respect', '2. No insult, harassment or threat'
    SOLICITING = 'soliciting', '3. No advertising, no soliciting clients'
    LAWFUL = 'lawful', '4. No fraud, no call to break the law'
    DECENT = 'decent', '5. Nothing sexual or violent'
    ON_TOPIC = 'on_topic', '6. On the article, and no repeats'
    HONEST = 'honest', '7. No false claim of a profession'


class Discussion(models.Model):
    """A topic's discussion (a place: /talk/family), or an article's from before 29 Oct 2026: its counts (recounted on
    every change, never incremented) and its lock. `text_path` is the place itself for a topic, so a moderator
    appointed for ['/talk/family'] reviews that topic (review.covers)."""

    path = models.CharField(max_length=PATH_MAX, unique=True)
    text_path = models.CharField(max_length=PATH_MAX, db_index=True)
    # Published contributions, answers included; questions nobody else has answered.
    count = models.PositiveIntegerField(default=0, db_default=0)
    open_questions = models.PositiveIntegerField(default=0, db_default=0)
    last_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discussion_discussion'

    def __str__(self):
        return self.path


class Contribution(models.Model):
    """A question, an explanation, an experience, a source or a remark on an article; or an answer under one (two
    levels, never more). Text, a voice or up to three pictures, alone or together."""

    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name='contributions')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    # The answer this one replies to, when it was written under an answer (answers stay two levels: W7).
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contributions')
    kind = models.CharField(max_length=12, choices=Kind.choices)
    # A post's title; a comment has none.
    title = models.CharField(max_length=TITLE_MAX, blank=True, default='', db_default='')
    body = models.TextField(blank=True, default='', db_default='')
    # The citations read in the body, as links: [{start, end, path}].
    links = models.JSONField(default=list, blank=True)
    # The article a post was started from («اسأل على هاد المادة»), and words taken from it, checked against it.
    about = models.CharField(max_length=PATH_MAX, blank=True, default='', db_default='')
    quote = models.TextField(blank=True, default='', db_default='')
    # «بدون اسم» (D6): hidden from readers and reviewers, never from staff. Text and pictures only.
    anonymous = models.BooleanField(default=False, db_default=False)
    clip = models.OneToOneField('media.Clip', null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='contribution')
    pictures = models.ManyToManyField('media.Picture', blank=True, related_name='contributions')
    # The article as it read when this was written: its version's date, and a digest of its words.
    version_on = models.DateField(null=True, blank=True)
    article_digest = models.CharField(max_length=40, blank=True, default='', db_default='')
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    # Waiting for a reviewer: a newcomer's first contributions, a picture, a phone number in the text… The reasons
    # are codes; the spans [start, end, code] show a reviewer what was matched.
    held_at = models.DateTimeField(null=True, blank=True)
    held_reasons = models.JSONField(default=list, blank=True)
    held_spans = models.JSONField(default=list, blank=True)
    # A reviewer sent it back to its author with this note (M4); it stays held until the author edits it.
    review_note = models.CharField(max_length=NOTE_MAX, blank=True, default='', db_default='')
    # Published at once, to be looked at after (a newcomer's second and third: W8). Cleared once a reviewer has.
    post_review_at = models.DateTimeField(null=True, blank=True)
    # Hidden from readers until a reviewer decides: three serious reports from proven accounts (M11).
    hidden_at = models.DateTimeField(null=True, blank=True)
    # The question this one repeats (M9): readers are sent there.
    duplicate_of = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='duplicates')
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='+')
    removed_rule = models.CharField(max_length=12, choices=Rule.choices, blank=True, default='', db_default='')
    # Deleted by its author. Under an open report it stays for the reviewers until they decide, 30 days at most.
    deleted_at = models.DateTimeField(null=True, blank=True)
    frozen_until = models.DateTimeField(null=True, blank=True)
    # The words and files are gone; the row stays while replies hang under it.
    erased_at = models.DateTimeField(null=True, blank=True)
    # Counted «مفيد» (votes from proven accounts three days old) and the asker's «أفادني».
    useful_count = models.PositiveIntegerField(default=0, db_default=0)
    accepted_at = models.DateTimeField(null=True, blank=True)
    reply_count = models.PositiveIntegerField(default=0, db_default=0)
    # A post's last sign of life: itself, or its latest published comment (recounted with reply_count).
    active_at = models.DateTimeField(null=True, blank=True)
    # A post's latest published comment by someone other than its author (none: nobody else answered yet), and its
    # answer: the comment its asker marked, else the most useful, else the first of the others'. Recounted with
    # reply_count, so the lists of questions waiting and answered read them instead of every comment (the load test
    # of 30 Oct 2026: computed for each question, «answered» timed out over ten million comments).
    answered_at = models.DateTimeField(null=True, blank=True)
    answer = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    # Its first-level published comments (its conversations) and the people who wrote under it, recounted with them.
    conversation_count = models.PositiveIntegerField(default=0, db_default=0)
    people_count = models.PositiveIntegerField(default=0, db_default=0)

    class Meta:
        db_table = 'discussion_contribution'
        indexes = [
            models.Index(fields=['discussion', 'parent', 'created_at'], name='discussion_thread_idx'),
            models.Index(fields=['discussion', 'parent', 'active_at'], name='discussion_active_idx'),
            models.Index(fields=['author', '-created_at'], name='discussion_author_idx'),
            models.Index(fields=['held_at'], name='discussion_held_idx'),
            models.Index(fields=['created_at'], name='discussion_created_idx'),
            # The feeds' orders, posts only: a topic's and every topic's, by life (thread.LIFE) and by date.
            models.Index(F('discussion'), Coalesce('active_at', 'created_at').desc(), F('created_at').desc(),
                         name='discussion_place_life_idx', condition=Q(parent=None)),
            models.Index(Coalesce('active_at', 'created_at').desc(), F('created_at').desc(),
                         name='discussion_life_idx', condition=Q(parent=None)),
            models.Index(F('created_at').desc(), name='discussion_posts_new_idx', condition=Q(parent=None)),
            # «الأنفع» over any period (thread.PERIODS): walked in its order, the period filtered on the way.
            models.Index(F('useful_count').desc(), F('reply_count').desc(), F('created_at').desc(),
                         name='discussion_posts_top_idx', condition=Q(parent=None)),
            # The questions waiting (few) and those answered, the latest answered first.
            models.Index(fields=['discussion', 'created_at'], name='discussion_waiting_idx',
                         condition=Q(parent=None, kind='question', answered_at=None)),
            models.Index(F('answered_at').desc(), name='discussion_answered_idx',
                         condition=Q(parent=None, kind='question', answered_at__isnull=False)),
            # A post's conversations in the page's orders («best» after the marked one: the most useful; «new», «old»),
            # read a page at a time; and its few comments not published, which the page must place.
            models.Index(F('parent'), F('useful_count').desc(), F('created_at'), F('id'), name='discussion_best_idx',
                         condition=Q(parent__isnull=False, reply_to=None)),
            models.Index(fields=['parent', 'created_at', 'id'], name='discussion_first_idx',
                         condition=Q(parent__isnull=False, reply_to=None)),
            models.Index(fields=['parent'], name='discussion_unpublished_idx',
                         condition=~Q(held_at=None, hidden_at=None, removed_at=None, deleted_at=None, erased_at=None)),
            # Those ever held, for the month's numbers.
            models.Index(fields=['created_at'], name='discussion_held_once_idx', condition=~Q(held_reasons=[])),
        ]

    def __str__(self):
        return f'{self.kind} {self.pk} on {self.discussion_id}'

    @property
    def published(self) -> bool:
        return not (self.held_at or self.hidden_at or self.removed_at or self.deleted_at or self.erased_at)


class Cite(models.Model):
    """An article a post or a comment cites, or started from: the article's page lists what cites it (C3 of 29 Oct
    2026), and the post says when the article changed after it (D14)."""

    contribution = models.ForeignKey(Contribution, on_delete=models.CASCADE, related_name='cites')
    path = models.CharField(max_length=PATH_MAX, db_index=True)
    text_path = models.CharField(max_length=PATH_MAX, db_index=True)
    # The article's words when it was cited, as a digest (anchors.digest).
    digest = models.CharField(max_length=40, blank=True, default='', db_default='')

    class Meta:
        db_table = 'discussion_cite'
        constraints = [models.UniqueConstraint(fields=['contribution', 'path'], name='discussion_cite_once')]


class Revision(models.Model):
    """The text before an edit, for the reviewers."""

    contribution = models.ForeignKey(Contribution, on_delete=models.CASCADE, related_name='revisions')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discussion_revision'
        ordering = ['created_at']
