"""A reader's report of an error in a reading («بلّغ عن خطأ»), kept by the article's address — not by a
link to its row, which a reload replaces — until a person fixes it or sets it aside."""
from django.db import models
from django.db.models.functions import MD5


class Report(models.Model):
    class Kind(models.TextChoices):
        READING = 'reading', 'A word or number misread'
        LINK = 'link', 'A wrong link'
        MISSING = 'missing', 'Something missing'
        OTHER = 'other', 'Something else'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        FIXED = 'fixed', 'Fixed'
        DISMISSED = 'dismissed', 'Set aside'

    path = models.CharField(max_length=300, help_text='The article as addressed on the site: /ma/loi/2025/50-25/art_6.')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    quote = models.TextField(blank=True, default='', db_default='', help_text='The words concerned, as the reader gave them.')
    message = models.TextField(blank=True, default='', db_default='')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_default=Status.OPEN)
    note = models.TextField(blank=True, default='', db_default='', help_text="The reviewer's note.")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'quality_report'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'created_at']), models.Index(fields=['path'])]

    def __str__(self):
        return f'{self.get_kind_display()} — {self.path}'


class PageTiming(models.Model):
    """How long a page took to show its main content on a reader's device (row 20): one in five page loads, the
    kind of page and the milliseconds, by day. No address, person or session; read by the weekly report."""

    class Kind(models.TextChoices):
        HOME = 'home', 'Home'
        SEARCH = 'search', 'Search'
        TEXT = 'text', 'A text'
        ARTICLE = 'article', 'An article'
        ISSUE = 'issue', 'A BO issue'
        OTHER = 'other', 'Another page'

    kind = models.CharField(max_length=10, choices=Kind.choices)
    ms = models.PositiveIntegerField()
    on = models.DateField(auto_now_add=True)

    class Meta:
        db_table = 'quality_page_timing'
        indexes = [models.Index(fields=['on', 'kind'])]



class Correction(models.Model):
    """A word put right in an article (R7 of the for-everyone review): proposed by the proofreader, a reader's report or a
    person reading, and applied only once a person confirmed it. Kept by the article's address and the words around
    it, so a reload of the text applies it again, and /corrections lists what was put right."""

    class Source(models.TextChoices):
        PROOFREAD = 'proofread', 'The proofreader: a word the BO never prints, turned into one it prints'
        CONTEXT = 'context', 'The proofreader: a pair of words the BO never prints, turned into a pair it prints'
        REPORT = 'report', "A reader's report"
        REVIEW = 'review', 'Found by a person reading'
        PAGE = 'page', "Read against the page's image"
        WITNESS = 'witness', "The page's second reading, where the first read letters of another alphabet"
        READING = 'reading', "The page's own reading, which the cut into articles lost"
        SPLIT = 'split', 'The proofreader: a word a stray space cut in two, joined into one the BO prints'

    class Status(models.TextChoices):
        SUGGESTED = 'suggested', 'Waiting for a person'
        APPLIED = 'applied', 'Applied'
        REJECTED = 'rejected', 'Set aside'

    path = models.CharField(max_length=300, help_text='The article: /ma/loi/70-03/art_171.')
    # A passage out of order or a note glued into an article is put right whole (the land review, M16): text, not 200.
    wrong = models.TextField()
    right = models.TextField(blank=True)
    before = models.CharField(max_length=200, blank=True, default='', db_default='', help_text='The word before it.')
    after = models.CharField(max_length=200, blank=True, default='', db_default='', help_text='The word after it.')
    source = models.CharField(max_length=10, choices=Source.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SUGGESTED,
                              db_default=Status.SUGGESTED)
    evidence = models.JSONField(default=dict, blank=True, help_text='How often the BO prints each form.')
    report = models.ForeignKey(Report, null=True, blank=True, on_delete=models.SET_NULL, related_name='corrections')
    decided_by = models.ForeignKey('accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quality_correction'
        ordering = ['-decided_at', '-created_at']
        # On the hash of «wrong»: a whole-page correction (a column lost, 6 Nov 2026) is longer than a btree row may be.
        constraints = [models.UniqueConstraint(models.F('path'), MD5('wrong'), models.F('before'), models.F('after'),
                                               name='quality_correction_once')]
        indexes = [models.Index(fields=['status', 'path'])]

    def __str__(self):
        return f'{self.path}: {self.wrong} → {self.right}'


class Suspect(models.Model):
    """A word a reading may have wrong, found by a free signal (FX9 of the mended-Bulletin review), for a person to
    confirm or set aside. Kept by its page (a page's row survives a text's reload). A confirmed one is put right in
    the page and in the articles printed there, as a correction read against the page's image."""

    class Signal(models.TextChoices):
        RARE = 'rare', 'Found nowhere else, its dotted neighbour common'
        COPIES = 'copies', 'Another reading of the same page reads it otherwise'
        TESSERACT = 'tesseract', 'Tesseract reads its dots otherwise'
        GLUED = 'glued', 'Latin letters glued to Arabic ones'
        REREAD = 'reread', 'A second reading (FX10) reads it otherwise, both words plausible'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        CONFIRMED = 'confirmed', 'Confirmed and put right'
        REJECTED = 'rejected', 'Set aside: the reading was right'

    page = models.ForeignKey('sources.Page', on_delete=models.CASCADE, related_name='suspects')
    word = models.CharField(max_length=120, help_text='As the reading has it.')
    suggestion = models.CharField(max_length=120, blank=True, default='', db_default='',
                                  help_text='What the page likely prints; empty when no signal says.')
    context = models.CharField(max_length=300, blank=True, default='', db_default='', help_text='The words around it.')
    signal = models.CharField(max_length=10, choices=Signal.choices)
    evidence = models.JSONField(default=dict, blank=True, help_text='Counts, the other readings, what Tesseract read.')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_default=Status.OPEN)
    decided_by = models.ForeignKey('accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Where the word stands on its page's image (apps/quality/services/place.py): null, not looked for yet; {}, looked
    # for and not found (it is not asked); else the strip's box and the word's mark, as shares of the page.
    place = models.JSONField(null=True, blank=True, default=None)
    asked = models.PositiveIntegerField(default=0, db_default=0, help_text='How many answers people gave about it.')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['page', 'word', 'suggestion', 'signal'],
                                               name='suspect_page_word_unique')]
        indexes = [models.Index(fields=['status', 'signal']),
                   # The words a visitor may be asked, the least asked first (services/words.py `one`).
                   models.Index(fields=['asked'], name='suspect_placed_asked',
                                condition=models.Q(status='open') & models.Q(place__has_key='box'))]

    def __str__(self):
        return f'{self.word} → {self.suggestion or "?"} ({self.signal})'


class Answer(models.Model):
    """What one person said a doubtful word's printed line holds, on the page «ساهم» (/open-source): the word, the answer
    and the time. Nothing about the person: no account, address or device."""

    class Says(models.TextChoices):
        WORD = 'word', 'The reading as it stands'
        SUGGESTION = 'suggestion', 'The suggestion'
        NEITHER = 'neither', 'Neither'
        UNCLEAR = 'unclear', 'The image is unclear'

    suspect = models.ForeignKey(Suspect, on_delete=models.CASCADE, related_name='answers')
    says = models.CharField(max_length=10, choices=Says.choices)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f'{self.suspect_id}: {self.says}'
