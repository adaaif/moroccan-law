"""What the consolidation engine knows about each article's history and what it could not settle (row 19). Both are
kept by address — a text's AKN URI and an article's number — not by links to rows, which a reload replaces."""
from django.db import models


class Verb(models.TextChoices):
    MODIFIED = 'modified', 'Modified'
    ADDED = 'added', 'Added'
    REPLACED = 'replaced', 'Repealed and replaced'
    REPEALED = 'repealed', 'Repealed'
    WORDS = 'words', 'Words replaced'


class Change(models.Model):
    """One change to one article, as the SGG's note records it or as we read it in the amending text."""

    class Source(models.TextChoices):
        SGG = 'sgg', "The SGG's note"
        ADALA = 'adala', "Adala's footnote"
        DGI = 'dgi', "The DGI's footnote (the tax code's yearly edition)"
        READING = 'reading', 'Read in the amending text'
        MODEL = 'model', 'Read by a model where the code could not (a witness, never placed alone)'
        BILL = 'bill', 'Proposed by a bill filed in Parliament (never applied)'

    class State(models.TextChoices):
        """What the evidence allows (row L9): shown as fact when checked, confirmed or read."""
        NONE = '', 'A witness row'
        CHECKED = 'checked', 'Checked by a person'
        CONFIRMED = 'confirmed', 'The reading and another source agree'
        READ = 'read', 'Read in the BO, nothing against it'
        CONFLICT = 'conflict', 'A source disagrees'
        UNCLEAR = 'unclear', 'The code could not read or place it'
        PROPOSED = 'proposed', 'Proposed by a bill: not law, never applied'

    class Rule(models.TextChoices):
        """How the date it takes effect was found (row L6)."""
        PUBLICATION = 'publication', 'On publication'
        STATED = 'stated', 'A date the text states'
        AFTER = 'after', 'A delay after publication'
        CONDITION = 'condition', 'When a condition is met'

    class Verdict(models.TextChoices):
        NONE = '', 'Not checked'
        AGREES = 'agrees', 'Agrees with the SGG'
        PARTLY = 'partly', 'Partly agrees'
        DISAGREES = 'disagrees', 'Disagrees'
        ABSENT = 'absent', 'Article not in the SGG text'

    text_uri = models.CharField(max_length=200, help_text='The text changed: its AKN URI.')
    number = models.CharField(max_length=30, help_text='The article changed: 7-1, 5-bis; empty for the whole text.')
    verb = models.CharField(max_length=10, choices=Verb.choices)
    source = models.CharField(max_length=10, choices=Source.choices)
    by_kind = models.CharField(max_length=20, help_text='The amending text: law, decree…')
    by_number = models.CharField(max_length=40)
    by_uri = models.CharField(max_length=200, blank=True, default='', db_default='',
                              help_text='The amending text in the corpus, when it is there.')
    by_article = models.CharField(max_length=80, blank=True, default='', db_default='',
                                  help_text='Its article that makes the change, as printed.')
    issue = models.PositiveIntegerField(null=True, blank=True, help_text='The BO issue that published the change.')
    issue_bis = models.BooleanField(default=False, db_default=False)
    page = models.PositiveIntegerField(null=True, blank=True)
    published_on = models.DateField(null=True, blank=True)
    wording = models.JSONField(default=list, blank=True, help_text='The new wording as printed, by lines (a reading).')
    placed = models.BooleanField(null=True, blank=True, help_text='Applied to a version by machine; empty if not tried.')
    verdict = models.CharField(max_length=10, choices=Verdict.choices, blank=True, default='', db_default='')
    score = models.FloatField(null=True, blank=True, help_text='How much of the wording the SGG text holds, 0 to 1.')
    detail = models.JSONField(default=dict, blank=True)
    effective_on = models.DateField(null=True, blank=True, help_text='When it takes effect; empty on a condition.')
    effective_rule = models.CharField(max_length=12, choices=Rule.choices, blank=True, default='', db_default='')
    effective_words = models.TextField(blank=True, default='', db_default='', help_text='The words that set the date.')
    state = models.CharField(max_length=10, choices=State.choices, blank=True, default='', db_default='')
    witnesses = models.JSONField(default=dict, blank=True,
                                 help_text='{title, model, sgg, adala, wording}: true agrees, false disagrees.')

    class Meta:
        db_table = 'consolidation_change'
        indexes = [models.Index(fields=['text_uri', 'number']), models.Index(fields=['by_uri'])]

    def __str__(self):
        return f'{self.text_uri} {self.number} {self.verb} by {self.by_kind} {self.by_number}'


class Doubt(models.Model):
    """What the machine could not settle, for a person: an amendment it could not read or place, or a reading the
    SGG's text does not bear out."""

    class Reason(models.TextChoices):
        TARGET_UNKNOWN = 'target_unknown', 'The text it amends is not named plainly'
        UNCLEAR = 'unclear', 'The instruction is not read plainly'
        ARTICLE_MISSING = 'article_missing', 'The article it amends is not in the base version'
        UNPLACED = 'unplaced', 'The dotted wording could not be placed'
        DROPPED = 'dropped', 'Placing it dropped paragraphs no dots stood for'
        WORDS_NOT_FOUND = 'words_not_found', 'The words to replace are not in the article'
        SGG_DISAGREES = 'sgg_disagrees', "The SGG's text does not bear the reading out"
        WHEN = 'when', 'It takes effect on a condition no code can date'
        COURT = 'court', 'A Constitutional Court ruling to check'
        CORRECTION = 'correction', 'A correction (استدراك) to apply by hand'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        RESOLVED = 'resolved', 'Resolved'
        DISMISSED = 'dismissed', 'Set aside'

    text_uri = models.CharField(max_length=200, blank=True, default='', db_default='')
    number = models.CharField(max_length=30, blank=True, default='', db_default='')
    by_uri = models.CharField(max_length=200, help_text='The amending text.')
    by_article = models.CharField(max_length=80, blank=True, default='', db_default='')
    reason = models.CharField(max_length=20, choices=Reason.choices)
    detail = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_default=Status.OPEN)
    note = models.TextField(blank=True, default='', db_default='')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'consolidation_doubt'
        ordering = ['status', '-created_at']
        indexes = [models.Index(fields=['status', 'reason'])]

    def __str__(self):
        return f'{self.get_reason_display()} — {self.by_uri} → {self.text_uri} {self.number}'
