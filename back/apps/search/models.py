"""The search index: one row an article (and one a text, for its title), its words folded and stemmed by ma_law exactly
as a query is, under a ParadeDB BM25 index. Built from the corpus by `build_search_index`.

B24 of the search plan (24 Oct 2026): rows are keyed by address, never by a corpus row, and each holds what an answer
shows (the text's name and stamp, the article's label, headings, page and words), so a search reads no corpus table to
answer. A reload of a text leaves its rows as they were until the index is built again; a build replaces a text's
rows in one transaction, so readers see the old rows or the new ones, never half."""
from django.db import models
from pgvector.django import HalfVectorField


class SearchEntry(models.Model):
    class Kind(models.TextChoices):
        ARTICLE = 'article', 'Article'
        TEXT = 'text', 'Text (its title)'

    kind = models.CharField(max_length=10, choices=Kind.choices)
    text_path = models.CharField(max_length=160, db_index=True, default='', db_default='',
                                 help_text="The text's address: /ma/loi/67-12.")
    # Indexed (31 Oct 2026): the meaning stage fetches its entries by address, a scan of 549,313 rows (770 ms on the
    # server) without it.
    path = models.CharField(max_length=200, default='', db_default='', db_index=True,
                            help_text="The article's address (/ma/loi/67-12/art_34), or the text's for its title row.")
    terms = models.TextField(blank=True, default='', db_default='',
                             help_text="The article's words, folded and stemmed (ma_law.index_terms).")
    title_terms = models.TextField(blank=True, default='', db_default='',
                                   help_text="The text's title, number and popular names, folded and stemmed.")
    lemma_terms = models.TextField(blank=True, default='', db_default='',
                                   help_text="The article's stems as their lemmas' stems (B4): «عقود» as «عقد».")
    title_folded = models.TextField(blank=True, default='', db_default='',
                                    help_text='The title folded, not stemmed: what as-you-type matches a prefix in.')
    text_type = models.CharField(max_length=20)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    in_force = models.BooleanField(default=True, db_default=True,
                                   help_text='False only for a text known to be repealed.')
    weight = models.FloatField(default=1.0, db_default=1.0,
                               help_text='Laws and codes above decrees, decrees above orders and decisions.')
    order = models.PositiveIntegerField(default=0, db_default=0, help_text="The article's place in its text.")
    # What an answer shows: the article.
    eid = models.CharField(max_length=60, blank=True, default='', db_default='')
    label = models.CharField(max_length=80, blank=True, default='', db_default='')
    heading_path = models.JSONField(default=list, blank=True, db_default=[])
    body = models.TextField(blank=True, default='', db_default='', help_text="The article's words, as the version reads.")
    page = models.PositiveIntegerField(null=True, blank=True, help_text='The BO page it was printed on (as published only).')
    # B16 of the search plan: an amending article's sound changes (read, confirmed or checked; never a repeal) to an
    # article the site holds, as an answer shows them: [{path, label, verb, name}].
    changes = models.JSONField(default=list, blank=True, db_default=[])
    # The version the row was read from.
    version_from = models.DateField(null=True, blank=True)
    consolidation = models.CharField(max_length=20, blank=True, default='', db_default='')
    # What an answer shows: the text (on its title row; a page of answers reads its texts' rows once).
    name = models.JSONField(default=dict, blank=True, db_default={}, help_text='codes.display_name: {ar, fr}.')
    title = models.TextField(blank=True, default='', db_default='')
    number_as_printed = models.CharField(max_length=60, blank=True, default='', db_default='')
    status = models.CharField(max_length=20, blank=True, default='', db_default='')
    issue = models.CharField(max_length=20, blank=True, default='', db_default='', help_text='The BO issue that printed it.')
    in_corpus = models.BooleanField(default=True, db_default=True, help_text='False for a text known by name only.')
    signed_year = models.PositiveSmallIntegerField(null=True, blank=True, help_text='The year it was signed, when known.')

    class Meta:
        db_table = 'search_entry'
        indexes = [models.Index(fields=['kind', 'text_type', 'year'])]


class SearchLog(models.Model):
    """A search as typed and what it found: the empty ones are read every week to grow the everyday-words list.
    No person, address or session is kept."""

    query = models.CharField(max_length=300)
    folded = models.CharField(max_length=300)
    results = models.PositiveIntegerField()
    understood_as = models.CharField(max_length=40, blank=True, default='', db_default='',
                                     help_text='citation, repaired (keyboard), words, some_words.')
    opened = models.PositiveSmallIntegerField(null=True, blank=True,
                                              help_text='Where the first answer opened stood (0 = the citation card, '
                                                        '1 = the first text); empty when none was opened.')
    shown = models.JSONField(default=list, blank=True, db_default=[],
                             help_text='The addresses of the articles the first page showed, in order (B3).')
    # Who searched: the site (empty), or an assistant through the MCP server (MC18 of the MCP review): still no
    # person, only where the words came from, to learn how assistants ask.
    via = models.CharField(max_length=8, blank=True, default='', db_default='')
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'search_log'
        indexes = [models.Index(fields=['results', 'at'])]


class SearchEvent(models.Model):
    """What a reader did after a search (B3 of the search plan, 24 Oct 2026): opened, saved, shared or copied an answer,
    or said whether the search found it. Tied to the search's own row, never to a person, a device or an address; the
    words typed go after 90 days (`prune_search_logs`), the events stay as counts."""

    class Kind(models.TextChoices):
        OPENED = 'opened', 'Opened'
        READ = 'read', 'Stayed open (seconds)'
        SAVED = 'saved', 'Saved on the device'
        SHARED = 'shared', 'Shared'
        COPIED = 'copied', 'Copied'
        FOUND = 'found', 'Said: I found the answer'
        NOT_FOUND = 'not_found', 'Said: I did not find it'

    log = models.ForeignKey(SearchLog, on_delete=models.CASCADE, related_name='events')
    kind = models.CharField(max_length=12, choices=Kind.choices)
    path = models.CharField(max_length=200, blank=True, default='', db_default='')
    rank = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Where it stood in the answers (1 = first).')
    seconds = models.PositiveIntegerField(null=True, blank=True,
                                          help_text='How long the article stayed open, rounded up to 10, 60, 300 or 900.')
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'search_event'
        indexes = [models.Index(fields=['kind', 'at'])]


class SearchPassage(models.Model):
    """A passage of an article, as the meaning model reads it (B7 of the search plan): the article whole, or a piece of
    a long one, opened by its header (the text's name › its headings › the article's label); its official French as a
    passage of its own. Keyed by address like the index; `model` says which model wrote the vector."""

    path = models.CharField(max_length=200, db_index=True, help_text="The article's address.")
    text_path = models.CharField(max_length=160)
    part = models.PositiveSmallIntegerField(default=0, db_default=0, help_text='The piece of a long article, from 0.')
    lang = models.CharField(max_length=2, default='ar', db_default='ar')
    model = models.CharField(max_length=40)
    version_from = models.DateField(null=True, blank=True)
    in_force = models.BooleanField(default=True, db_default=True)
    text_type = models.CharField(max_length=20, blank=True, default='', db_default='')
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    vector = HalfVectorField(dimensions=1024)

    class Meta:
        db_table = 'search_passage'
        constraints = [models.UniqueConstraint(fields=['path', 'part', 'lang', 'model'], name='search_passage_one')]
