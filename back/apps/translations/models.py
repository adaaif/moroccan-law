"""The official French translation of a text (decision C3): the BO's translation edition, beside the Arabic,
which alone is authoritative. Kept by the Arabic text's address and its articles' numbers, not by links to rows,
so either edition can be read first and a reload of one never touches the other."""
from django.db import models


class FrenchText(models.Model):
    text_uri = models.CharField(max_length=200, unique=True, help_text="The Arabic text's AKN URI.")
    type = models.CharField(max_length=20)
    number = models.CharField(max_length=40, blank=True, default='', db_default='')
    title = models.TextField()
    signed_on = models.DateField(null=True, blank=True)
    issue_number = models.PositiveIntegerField(help_text='The translation edition issue that printed it.')
    issue_suffix = models.CharField(max_length=10, blank=True, default='', db_default='')
    issue_date = models.DateField()
    document_sha = models.CharField(max_length=64, help_text='The issue\'s file (sources.Document) by its hash.')
    pages = models.CharField(max_length=20, blank=True, default='', db_default='')
    consolidated_to = models.DateField(null=True, blank=True, help_text='A consolidation (Adala\'s) stands at this '
                                       'date: the French of an article changed since is older than its Arabic.')
    loaded_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'translations_text'

    def __str__(self):
        return f'{self.title[:80]} (BO {self.issue_number} fr)'


class FrenchArticle(models.Model):
    text_uri = models.CharField(max_length=200)
    order = models.PositiveIntegerField()
    label = models.CharField(max_length=80, help_text='As printed: «Article premier», «Article 2 bis».')
    number = models.CharField(max_length=30, help_text='As the Arabic article\'s: 1, 2-bis.')
    body = models.TextField()
    printed_page = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'translations_article'
        ordering = ['text_uri', 'order']
        indexes = [models.Index(fields=['text_uri', 'number'])]

    def __str__(self):
        return f'{self.label} ({self.text_uri})'
