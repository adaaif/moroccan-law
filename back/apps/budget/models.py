"""The state budget as data: each finance law's figures, read from its BO pages and checked against its own totals."""
from django.db import models

from apps.corpus.models import Text
from apps.sources.models import Document


class Kind(models.TextChoices):
    BILL = 'bill', 'Finance bill (مشروع قانون المالية)'
    LAW = 'law', 'Finance law (قانون المالية)'
    AMENDING = 'amending', 'Amending finance law (قانون المالية المعدل)'
    SETTLEMENT = 'settlement', 'Settlement law (قانون التصفية)'


class FinanceLaw(models.Model):
    """One budget year at one stage: the bill, the law, an amending law, or the settlement law."""

    year = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=12, choices=Kind.choices)
    number = models.CharField(max_length=20, help_text='As printed: «50.25».')
    title = models.CharField(max_length=500)
    text = models.ForeignKey(Text, null=True, blank=True, on_delete=models.SET_NULL, related_name='finance_laws',
                             help_text='The law in the corpus, its articles and pages.')
    document = models.ForeignKey(Document, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    stated = models.JSONField(default=dict, db_default={}, blank=True,
                              help_text='What the articles state in figures, by table: {"B": ["347490689000"], ...}.')
    sources = models.JSONField(default=dict, db_default={}, blank=True,
                               help_text='The article each figure comes from: {"balance": "37", "posts": "20", "B": "42"}.')
    checks = models.JSONField(default=list, db_default=[], blank=True,
                              help_text='Every arithmetic check run on its figures: name, expected, found, ok.')
    checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['year', 'kind', 'number'], name='finance_law_unique')]
        ordering = ['-year', 'kind']

    def __str__(self):
        return f'{self.get_kind_display()} {self.year} ({self.number})'

    def tables_checked(self) -> set[str]:
        """The tables whose every check passed: only their figures are shown."""
        failed = {t for c in self.checks if not c['ok'] for t in c['tables']}
        return {t for c in self.checks if c['ok'] for t in c['tables']} - failed


class Table(models.TextChoices):
    BALANCE = 'balance', 'The balance (art. 37)'
    POSTS = 'posts', 'Budget posts created'
    A = 'A', 'Table A: revenue'
    B = 'B', 'Table B: running costs by ministry'
    C = 'C', 'Table C: investment by ministry'
    D = 'D', 'Table D: public debt'
    E = 'E', 'Table E: autonomous services, running costs'
    F = 'F', 'Table F: autonomous services, investment'
    G = 'G', 'Table G: Treasury special accounts'


class Line(models.Model):
    """One figure: a line of the balance, a ministry's chapter, a revenue, a count of posts."""

    finance_law = models.ForeignKey(FinanceLaw, on_delete=models.CASCADE, related_name='lines')
    table = models.CharField(max_length=10, choices=Table.choices)
    order = models.PositiveIntegerField()
    key = models.CharField(max_length=40, blank=True, default='', db_default='',
                           help_text='A stable name for a balance line («tax_revenue»), for checks and pages.')
    code = models.CharField(max_length=40, blank=True, default='', db_default='',
                            help_text='The budget code as printed: «1.2.1.1.0.06.000».')
    section = models.CharField(max_length=300, blank=True, default='', db_default='',
                               help_text='The ministry or heading the line sits under, as printed.')
    label = models.CharField(max_length=500)
    amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True,
                                 help_text='Dirhams (payment credits where a table has two columns), or a count.')
    commitment = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True,
                                     help_text='Commitment credits, in the tables that give them.')
    is_total = models.BooleanField(default=False, db_default=False)
    page = models.PositiveIntegerField(null=True, blank=True, help_text='The printed BO page.')

    class Meta:
        ordering = ['finance_law', 'table', 'order']
        indexes = [models.Index(fields=['finance_law', 'table'])]

    def __str__(self):
        return f'{self.table} {self.code or self.key} {self.label[:40]}: {self.amount}'
