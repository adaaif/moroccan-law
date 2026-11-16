"""The official explanations beside a law (row 11): the bill's explanatory memorandum («المذكرة التقديمية») as
the government filed it with Parliament. Kept by the law's address, not by a link to its row."""
from django.db import models


class Explanation(models.Model):
    class Kind(models.TextChoices):
        MEMORANDUM = 'memorandum', "The bill's explanatory memorandum"

    text_uri = models.CharField(max_length=200, help_text='The law it explains: its AKN URI.')
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.MEMORANDUM, db_default=Kind.MEMORANDUM)
    body = models.TextField(help_text='As read from the bill, paragraphs on their own lines.')
    source_url = models.URLField(max_length=500, help_text="The bill on the Chamber of Representatives' site.")
    document_sha = models.CharField(max_length=64, help_text='The fetched file (sources.Document) by its hash.')
    pages = models.CharField(max_length=20, blank=True, default='', db_default='', help_text='Pages of the file read, e.g. 1-2.')
    read_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'parliament_explanation'
        constraints = [models.UniqueConstraint(fields=['text_uri', 'kind'], name='explanation_text_kind_unique')]

    def __str__(self):
        return f'{self.get_kind_display()} — {self.text_uri}'
