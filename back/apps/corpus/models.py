"""The law, organised: texts, their dated versions, articles, and the links between them.

A text is the Work (Akoma Ntoso's FRBR model); a version is one language as of one date; articles belong
to a version, so every version is whole and two versions can be compared article by article.
"""
from datetime import date

from django.db import models

from apps.sources.models import Document, Issue, Language


class TextType(models.TextChoices):
    CONSTITUTION = 'constitution', 'Constitution'
    ORGANIC_LAW = 'organic_law', 'Organic law'
    LAW = 'law', 'Law'
    DAHIR = 'dahir', 'Dahir'
    DECREE_LAW = 'decree_law', 'Decree-law'
    DECREE = 'decree', 'Decree'
    ORDER = 'order', 'Order (arrêté)'
    DECISION = 'decision', 'Decision'
    CIRCULAR = 'circular', 'Circular'
    CONVENTION = 'convention', 'International convention'
    BILL = 'bill', 'Bill filed in Parliament (not law)'
    OTHER = 'other', 'Other'


class Status(models.TextChoices):
    IN_FORCE = 'in_force', 'In force'
    PARTLY_REPEALED = 'partly_repealed', 'Partly repealed'
    REPEALED = 'repealed', 'Repealed'
    NOT_YET_IN_FORCE = 'not_yet_in_force', 'Not yet in force'
    UNKNOWN = 'unknown', 'Unknown'


class Text(models.Model):
    """A legal text in every language and every version: «loi n° 65-99», «dahir n° 1-03-194»."""

    akn_uri = models.CharField(max_length=200, unique=True,
                               help_text='Akoma Ntoso work address, e.g. /akn/ma/act/loi/2003/65-99.')
    type = models.CharField(max_length=20, choices=TextType.choices)
    number = models.CharField(max_length=40, blank=True, default='', db_default='',
                              help_text='Normalised with dashes: 65-99, 1-03-194.')
    number_as_printed = models.CharField(max_length=60, blank=True, default='', db_default='',
                                         help_text='65.99 in Arabic, 65-99 in French.')
    title_ar = models.TextField(blank=True, default='', db_default='')
    title_fr = models.TextField(blank=True, default='', db_default='')
    signed_on = models.DateField(null=True, blank=True)
    signed_on_hijri = models.CharField(max_length=80, blank=True, default='', db_default='',
                                       help_text='As printed: «14 من رجب 1424».')
    authority = models.CharField(max_length=200, blank=True, default='', db_default='')
    promulgating_dahir = models.CharField(max_length=40, blank=True, default='', db_default='',
                                          help_text='The dahir that promulgates a law, as printed: 1.26.68.')
    rubric = models.CharField(max_length=300, blank=True, default='', db_default='',
                              help_text="The BO's subject heading above the text: «الصفقات العمومية».")
    bo_section = models.CharField(max_length=20, blank=True, default='', db_default='',
                                  help_text='general («نصوص عامة») or special («نصوص خاصة»).')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNKNOWN,
                              db_default=Status.UNKNOWN)
    aliases = models.JSONField(default=list, blank=True,
                               help_text='Popular names: «مدونة الشغل», «Code du travail».')
    first_published_in = models.ForeignKey(Issue, null=True, blank=True, on_delete=models.PROTECT,
                                           related_name='texts_first_published')
    first_published_page = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # The shelf, the topics and search's codes find a law by its kind and number (S10 of the performance audit).
        indexes = [models.Index(fields=['type', 'number'], name='corpus_text_type_number')]

    def __str__(self):
        return f'{self.get_type_display()} {self.number or self.akn_uri}'

    @property
    def in_corpus(self) -> bool:
        """Whether the site holds its words: read from the query that brought the text when it says so (an annotated
        `has_versions`, prefetched versions), else asked."""
        if hasattr(self, 'has_versions'):
            return self.has_versions
        if 'versions' in getattr(self, '_prefetched_objects_cache', {}):
            return bool(self.versions.all())
        return self.versions.exists()

    def latest_version(self):
        """The newest version in force today; on a day several start, the one RANK puts first (H2 of the housing plan:
        18.00's Adala consolidation of 16 Jul 2026, 101 articles, before the machine's of that day, built on an older
        base). A version dated later is not yet in force (the health review, S3: Adala's copy of 65.00 holds law
        54.23, which applies from 1 Feb 2027); the earliest one is read only when none stands yet."""
        return min(self.versions.all(), default=None, key=lambda v: standing(v.valid_from, v.consolidation, v.id))


class Consolidation(models.TextChoices):
    AS_PUBLISHED = 'as_published', 'As published in the BO'
    MACHINE = 'machine', 'Consolidated by machine (unofficial)'
    CHECKED = 'checked', 'Consolidated and checked by a person (unofficial)'
    SGG = 'sgg', 'Consolidated by the SGG (for information; the BO prevails)'
    ADALA = 'adala', 'Consolidated by Adala, the Ministry of Justice (for information; the BO prevails)'
    DGI = 'dgi', "The DGI's yearly edition of the tax code (for information; the BO prevails)"
    BILL = 'bill', 'A bill as filed in Parliament, or as a chamber voted it (not law)'
    # 31 Oct 2026: an Arabic issue the SGG never put online (BO 7410: a 404) whose official French edition is held is
    # given Arabic by a model, always said to be a translation from the French. Never the law's words.
    TRANSLATION = 'translation', 'Machine-translated from the official French translation (not the official text)'


# Which version stands when several start the same day: a person's check; then the SGG's, Adala's or the DGI's consolidation,
# which stands at that day and so holds its changes; then the machine's chain; then the BO's.
# A machine translation comes last: the Arabic as printed takes its place the day it is found.
RANK = {'checked': 0, 'sgg': 1, 'adala': 2, 'dgi': 2, 'machine': 3, 'as_published': 4, 'bill': 5, 'translation': 6}


def standing(valid_from, consolidation: str, pk: int) -> tuple:
    """The order `Text.latest_version()` reads versions in: those in force today before those not yet, the newest first
    (of those not yet, the soonest), then RANK, then the newest row."""
    future = valid_from > date.today()
    return future, (valid_from.toordinal() if future else -valid_from.toordinal()), RANK.get(consolidation, 9), -pk


def latest_ids(rows) -> dict[int, int]:
    """Each text's newest version id, from (version id, text id, valid_from, consolidation) rows: what
    `Text.latest_version()` picks, for many texts in one query."""
    best: dict[int, tuple] = {}
    for pk, text_id, valid_from, consolidation in rows:
        key = standing(valid_from, consolidation, pk)
        if text_id not in best or key < best[text_id][0]:
            best[text_id] = (key, pk)
    return {text_id: pk for text_id, (_, pk) in best.items()}


class Version(models.Model):
    """One language of a text as it stood from one date to the next."""

    text = models.ForeignKey(Text, on_delete=models.CASCADE, related_name='versions')
    language = models.CharField(max_length=2, choices=Language.choices)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True, help_text='Empty while this is the version in force.')
    consolidation = models.CharField(max_length=20, choices=Consolidation.choices)
    source_document = models.ForeignKey(Document, null=True, blank=True, on_delete=models.PROTECT,
                                        related_name='versions')
    source_pages = models.CharField(max_length=40, blank=True, default='', db_default='',
                                    help_text='Printed pages, e.g. 1112-1118.')
    preamble = models.TextField(blank=True, default='', db_default='',
                                help_text='The visas («بناء على …»), one per line.')
    closing = models.TextField(blank=True, default='', db_default='',
                               help_text='Place, date and signatures, as printed.')
    # A `translation` version: the language it was translated from (the official French edition), the engine that
    # translated it (kept, never shown: readers see «الذكاء الاصطناعي»), and when.
    translated_from = models.CharField(max_length=2, blank=True, default='', db_default='',
                                       help_text='The language this version was machine-translated from; empty when not.')
    translated_by = models.CharField(max_length=60, blank=True, default='', db_default='')
    translated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Two sources may date a version the same day (the SGG's last change and the machine's).
        constraints = [models.UniqueConstraint(fields=['text', 'language', 'valid_from', 'consolidation'],
                                               name='version_text_language_from_source_unique')]
        ordering = ['text', 'language', '-valid_from']

    def __str__(self):
        return f'{self.text} [{self.language}] from {self.valid_from}'


class Article(models.Model):
    """The unit people search, cite and share."""

    version = models.ForeignKey(Version, on_delete=models.CASCADE, related_name='articles')
    order = models.PositiveIntegerField()
    label = models.CharField(max_length=80, help_text='As printed: «الفصل 488», «المادة 5 مكرر», «Article 8».')
    number = models.CharField(max_length=30, blank=True, default='', db_default='',
                              help_text='Normalised: 488, 618-1, 5-bis.')
    heading_path = models.JSONField(default=list, blank=True,
                                    help_text='Book, title, chapter, section headings above it.')
    body = models.TextField()
    eid = models.CharField(max_length=60, blank=True, default='', db_default='',
                           help_text='Akoma Ntoso element id, e.g. art_8: the anchor in a URL.')
    printed_page = models.PositiveIntegerField(null=True, blank=True,
                                               help_text='The printed page the article starts on.')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['version', 'order'], name='article_version_order_unique')]
        ordering = ['version', 'order']

    def __str__(self):
        return f'{self.label} ({self.version})'


class Alias(models.Model):
    """Another address that leads to a text (row L1 of the links review): the address it had before addresses were
    worked out from kind and number, an empty twin merged into it, or the dahir that promulgated it
    («/akn/ma/act/dahir/1-00-20» is law 2.00). Kept by address, like everything a reload must not break."""

    class Reason(models.TextChoices):
        MOVED = 'moved', 'Its address before 19 Oct 2026'
        MERGED = 'merged', 'A twin row merged into it'
        DAHIR = 'dahir', 'The dahir that promulgated it'
        COPY = 'copy', 'The same text cut from a copy of its issue (FX3)'
        TWIN = 'twin', 'The same printed text cut twice in its issue (FX7)'

    alias = models.CharField(max_length=200, unique=True)
    uri = models.CharField(max_length=200, db_index=True, help_text='The text\'s AKN URI.')
    reason = models.CharField(max_length=10, choices=Reason.choices)

    def __str__(self):
        return f'{self.alias} → {self.uri}'


class Mention(models.Model):
    """A text, or one of its articles, pointing at another text without changing it (row L4): a citation, a decree
    applying a law («بتطبيق»), references redirected to it, decrees it keeps in force, a correction, a court's
    ruling on it. Kept by address, with the words as printed and where they stand in the article."""

    class Kind(models.TextChoices):
        CITES = 'cites', 'Cites'
        APPLIES = 'applies', 'Applies'
        REDIRECTS = 'redirects', 'Takes over the references to'
        KEEPS = 'keeps', 'Keeps the implementing texts of'
        CORRECTS = 'corrects', 'Corrects'
        RULES_ON = 'rules_on', 'Rules on'

    class State(models.TextChoices):
        RESOLVED = 'resolved', 'One text answers'
        AMBIGUOUS = 'ambiguous', 'Two texts could answer'
        UNRESOLVED = 'unresolved', 'Names no text the site can address'
        SELF = 'self', 'This text'

    from_uri = models.CharField(max_length=200, db_index=True)
    from_eid = models.CharField(max_length=60, blank=True, default='', db_default='',
                                help_text='The article\'s eid; «preamble» for a visa; empty for the title.')
    start = models.PositiveIntegerField(default=0, db_default=0)
    end = models.PositiveIntegerField(default=0, db_default=0)
    words = models.TextField()
    kind = models.CharField(max_length=10, choices=Kind.choices)
    to_uri = models.CharField(max_length=200, blank=True, default='', db_default='')
    to_number = models.CharField(max_length=30, blank=True, default='', db_default='',
                                 help_text='The article named, as the corpus numbers them: 5, 7-1.')
    state = models.CharField(max_length=10, choices=State.choices)

    class Meta:
        indexes = [models.Index(fields=['to_uri', 'kind'])]

    def __str__(self):
        return f'{self.from_uri} {self.from_eid} {self.kind} {self.to_uri or self.words[:40]}'
