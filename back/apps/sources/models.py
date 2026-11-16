"""Where the law comes from: files exactly as fetched, Bulletin Officiel issues, pages, OCR runs.

Everything in `corpus` points back here: a text, a version or an article is only as good as the
page it was read from.
"""
from django.db import models


class Source(models.TextChoices):
    SGG_BO = 'sgg_bo', 'SGG, Bulletin Officiel'
    SGG_CONSOLIDATED = 'sgg_consolidated', 'SGG, consolidated texts'
    ADALA = 'adala', 'Adala, Ministry of Justice'
    CONSTITUTIONAL_COURT = 'constitutional_court', 'Constitutional Court'
    CSPJ = 'cspj', 'CSPJ judicial portal'
    PARLIAMENT = 'parliament', 'Parliament'
    LOCAL_AUTHORITIES = 'local_authorities', 'Local authorities bulletin'
    DGI = 'dgi', 'DGI, the tax administration'
    MEF = 'mef', 'Ministry of Economy and Finance (finance bills and their reports)'
    OTHER = 'other', 'Other official site'


class DocumentKind(models.TextChoices):
    BO_ISSUE = 'bo_issue', 'Bulletin Officiel issue'
    CONSOLIDATED_TEXT = 'consolidated_text', 'Consolidated text'
    TEXT = 'text', 'Legal text'
    COURT_DECISION = 'court_decision', 'Court decision'
    PARLIAMENT = 'parliament', 'Bill or committee report'
    BULLETIN = 'bulletin', 'Other bulletin'
    CODE_PAGE = 'code_page', 'Code published as web pages'


class Language(models.TextChoices):
    ARABIC = 'ar', 'Arabic'
    FRENCH = 'fr', 'French'


class Document(models.Model):
    """One file exactly as fetched. Never edited; the hash proves where a text came from."""

    source = models.CharField(max_length=30, choices=Source.choices)
    kind = models.CharField(max_length=30, choices=DocumentKind.choices)
    url = models.URLField(max_length=1000, blank=True)
    sha256 = models.CharField(max_length=64, unique=True)
    path = models.CharField(max_length=500, help_text='Relative to settings.CORPUS_DIR.')
    mime = models.CharField(max_length=80)
    bytes = models.PositiveBigIntegerField()
    language = models.CharField(max_length=2, choices=Language.choices)
    title = models.CharField(max_length=500, blank=True, default='', db_default='')
    page_count = models.PositiveIntegerField(null=True, blank=True)
    producer = models.CharField(max_length=200, blank=True, default='', db_default='',
                                help_text="The PDF's producer: tells a scan from a born-digital file.")
    fetched_at = models.DateTimeField()
    meta = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.title or self.path


class Edition(models.TextChoices):
    GENERAL_AR = 'general_ar', 'General edition (Arabic, authoritative)'
    TRANSLATION_FR = 'translation_fr', 'Official translation (French)'
    CONVENTIONS_AR = 'conventions_ar', 'International conventions (Arabic)'
    CONVENTIONS_FR = 'conventions_fr', 'International conventions (French)'
    ANNOUNCEMENTS_LEGAL = 'announcements_legal', 'Legal, judicial and administrative announcements'
    ANNOUNCEMENTS_LAND = 'announcements_land', 'Land registration announcements'


class Issue(models.Model):
    """One Bulletin Officiel issue in one edition."""

    edition = models.CharField(max_length=30, choices=Edition.choices)
    number = models.PositiveIntegerField()
    suffix = models.CharField(max_length=10, blank=True, default='', db_default='',
                              help_text='«bis», «ter»: a second issue under the same number.')
    date = models.DateField()
    hijri_date = models.CharField(max_length=80, blank=True, default='', db_default='',
                                  help_text='As printed; never recomputed (months follow local sighting).')
    document = models.OneToOneField(Document, null=True, blank=True, on_delete=models.PROTECT,
                                    related_name='issue')
    first_page_number = models.PositiveIntegerField(
        null=True, blank=True, help_text="BO pages run on through the year: this issue's first printed page.")
    copy_of = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT, related_name='copies',
        help_text='The issue whose cover also bears this number («عدد 610 — 637»): the SGG keeps one copy of the '
                  'file per number. A copy has no pages of its own; its number leads to the cover (FX3).')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['edition', 'number', 'suffix'],
                                               name='issue_edition_number_unique')]
        ordering = ['-date']

    def __str__(self):
        return f'BO {self.key} ({self.get_edition_display()}, {self.date})'

    @property
    def key(self) -> str:
        """The issue as it is cited and addressed: «7533», «7465-bis»."""
        return f'{self.number}-{self.suffix}' if self.suffix else str(self.number)

    @staticmethod
    def parse_key(key: str) -> tuple[int, str]:
        number, _, suffix = str(key).partition('-')
        return int(number), suffix


class PageKind(models.TextChoices):
    TEXT_LAYER = 'text_layer', 'Selectable text'
    SCAN = 'scan', 'Scan, needs OCR'
    MIXED = 'mixed', 'Some text, mostly image'
    BLANK = 'blank', 'Blank'


class TextSource(models.TextChoices):
    NONE = 'none', 'No text yet'
    LAYER = 'layer', 'PDF text layer'
    OCR = 'ocr', 'OCR'
    CHECKED = 'checked', 'Checked by a person'


class Page(models.Model):
    """One page of a document, with the best text we have for it."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='pages')
    index = models.PositiveIntegerField(help_text='0-based position in the file.')
    printed_number = models.PositiveIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=20, choices=PageKind.choices)
    layer_text = models.TextField(blank=True, default='', db_default='',
                                  help_text='As extracted, defects included (lam-alef order, visual order).')
    layer_letters = models.PositiveIntegerField(default=0, db_default=0)
    text = models.TextField(blank=True, default='', db_default='')
    text_source = models.CharField(max_length=10, choices=TextSource.choices,
                                   default=TextSource.NONE, db_default=TextSource.NONE)
    # How the page was read and what its layer confirms, worked out when its reading is chosen and kept with the
    # fingerprint of that reading (S11 of the performance audit: an issue's quality page counted every page's letters
    # on each visit): {'of', 'reading', 'check'}. sources.services.quality.measured() reads it.
    quality = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['document', 'index'], name='page_document_index_unique')]
        ordering = ['document', 'index']

    def __str__(self):
        return f'{self.document} p.{self.index + 1}'


class OcrRun(models.Model):
    """One engine reading one page. Every run is kept with its price, so engines can be compared."""

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='ocr_runs')
    engine = models.CharField(max_length=60, help_text='claude-opus-5-5, claude-sonnet-5-5, tesseract-5…')
    variant = models.CharField(max_length=40, blank=True, default='', db_default='',
                               help_text='How the page was sent: whole page, column crops…')
    prompt_version = models.CharField(max_length=20, blank=True, default='', db_default='')
    image_px = models.CharField(max_length=20, blank=True, default='', db_default='')
    input_tokens = models.PositiveIntegerField(default=0, db_default=0)
    output_tokens = models.PositiveIntegerField(default=0, db_default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0, db_default=0)
    batch_id = models.CharField(max_length=100, blank=True, default='', db_default='')
    stop_reason = models.CharField(max_length=40, blank=True, default='', db_default='')
    seconds = models.FloatField(null=True, blank=True)
    text = models.TextField(blank=True, default='', db_default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.engine} on {self.page}'
