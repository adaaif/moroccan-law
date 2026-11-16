from django.conf import settings
from django.db import models


class ItemCheck(models.Model):
    """A person checked one of a topic's items (F17 of the family plan): who, when, and the digests of the articles it
    cited that day, so an article changed since makes it «يحتاج مراجعة». Kept here, not beside the topic's files: a
    deploy replaces the code's folder. `ref` is an item the topic has («journeys/marry», «tools/inheritance»); `by` is
    the name readers see, the signed-in account's on the review desk."""

    topic = models.CharField(max_length=40)
    ref = models.CharField(max_length=120)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
                             help_text='Who checked it on the desk; none for `manage.py approve_topic`.')
    by = models.CharField(max_length=80)
    on = models.DateField()
    digests = models.JSONField(default=dict, blank=True)
    at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'topics_item_check'
        constraints = [models.UniqueConstraint(fields=['topic', 'ref'], name='topics_item_check_once')]
        # The review desk's right (/topics/<slug>/review): to read a topic's drafts and mark its items checked.
        permissions = [('review_topic', "Can mark a topic's items checked")]

    def __str__(self):
        return f'{self.topic} {self.ref} checked by {self.by} on {self.on}'


class Helped(models.Model):
    """«هل ساعدك هذا؟» (F15 of the family plan): one reader's answer about one step or page of a topic, counted in the
    weekly reader report. Nothing about the reader is kept: no account, no address, no words."""

    class Reason(models.TextChoices):
        NONE = '', 'No reason given'
        UNCLEAR = 'unclear', 'Not clear'
        NOT_MINE = 'not_mine', 'Not my case'
        WRONG = 'wrong', 'Seems wrong'

    path = models.CharField(max_length=300, help_text='The page and step: /topics/family/journeys/divorce-agreement#2.')
    helped = models.BooleanField()
    reason = models.CharField(max_length=10, choices=Reason.choices, blank=True, default='', db_default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'topics_helped'
        indexes = [models.Index(fields=['path'])]


class ToolUse(models.Model):
    """How a topic's tools are used (M1 of the road tools review), counted by day, page and event: a tool opened, an
    answer shown, a share, a picture, a reminder, a voice, a scene answered right or wrong, a door opened from search.
    Never an input, an address or a person: the counter only grows."""

    class Event(models.TextChoices):
        OPEN = 'open', 'Opened'
        SHARE = 'share', 'Shared as text'
        PICTURE = 'picture', 'Shared as a picture'
        REMIND = 'remind', 'Reminder added'
        LISTEN = 'listen', 'Read aloud'
        RIGHT = 'right', 'A scene answered right first'
        WRONG = 'wrong', 'A scene answered wrong first'
        DOOR = 'door', 'A door opened from search'
        TICK = 'tick', 'A journey step ticked'

    on = models.DateField()
    path = models.CharField(max_length=120, help_text='The page, without its query: /topics/road/tools/fine.')
    event = models.CharField(max_length=10, choices=Event.choices)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'topics_tool_use'
        constraints = [models.UniqueConstraint(fields=['on', 'path', 'event'], name='topics_tool_use_once')]


class PlaceText(models.Model):
    """A BO land text read as a place's entry (the land review, M8–M9): its kind by its title's formula, the
    communes, provinces, properties and title or requisition numbers it names, and a folded blob to match what a reader
    types. Keyed by the text's address, never a foreign key: `manage.py build_land_places` writes them all again."""

    uri = models.CharField(max_length=200, unique=True, help_text='The text\'s AKN URI.')
    kind = models.CharField(max_length=20)
    date = models.DateField(help_text='The BO issue\'s date.')
    issue = models.CharField(max_length=20, blank=True, default='', db_default='')
    page = models.PositiveIntegerField(null=True, blank=True)
    title = models.TextField()
    communes = models.JSONField(default=list, db_default=[])
    provinces = models.JSONField(default=list, db_default=[])
    properties = models.JSONField(default=list, db_default=[])
    refs = models.JSONField(default=list, db_default=[], help_text='Title and requisition numbers, compact: «f18820».')
    search = models.TextField(blank=True, default='', db_default='', help_text='Folded: title, places, refs, the rows.')
    rows = models.PositiveIntegerField(default=0, db_default=0)

    class Meta:
        db_table = 'topics_place_text'
        indexes = [models.Index(fields=['-date'])]


class Parcel(models.Model):
    """One row of a land text's table of plots, as the OCR read it (M9): the plot's number, the property and its title
    or requisition, the area, the owners as printed (the law publishes them so owners learn: C2 «names»), the notes.
    Keyed by the text's address and the row."""

    uri = models.CharField(max_length=200)
    row = models.PositiveIntegerField()
    plot = models.CharField(max_length=40, blank=True, default='', db_default='')
    property = models.TextField(blank=True, default='', db_default='')
    ref = models.CharField(max_length=60, blank=True, default='', db_default='')
    area = models.CharField(max_length=60, blank=True, default='', db_default='')
    owners = models.TextField(blank=True, default='', db_default='')
    owners_count = models.PositiveIntegerField(default=0, db_default=0)
    notes = models.TextField(blank=True, default='', db_default='')

    class Meta:
        db_table = 'topics_parcel'
        constraints = [models.UniqueConstraint(fields=['uri', 'row'], name='topics_parcel_once')]
        indexes = [models.Index(fields=['ref'])]
