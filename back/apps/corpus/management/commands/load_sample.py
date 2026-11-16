"""A small corpus to try the site with: the 2011 Constitution and one Bulletin issue of general texts, with the official
French where it exists, from apps/corpus/fixtures/sample.json. Official texts carry no copyright (law 2-00, art. 8).

    python manage.py migrate
    python manage.py load_sample             # into an empty database: the rows, then their search entries

The issue is BO 7278 (29 Feb 2024): eleven laws (the pharmacists' order, credit information bureaus, two changes to
the self-employed's health insurance and pensions, seven international agreements), its 32 pages as read, and the
French of law 01.22 from the translation edition (BO 7410). It holds no notice about a private person: no land
registration, naturalisation, identity number or personal phone (its cover prints the official printer's numbers, as
every issue does). The files themselves (the PDFs, the page images) are not in the sample: a page shows its reading.

    python manage.py load_sample --write-fixture    # the maintainers': the fixture written again from this database

--write-fixture only reads (SELECT) the database it is connected to, and writes the rows of SAMPLE with new
primary keys from 1, so that the fixture loads into any empty database.
"""
import json
from pathlib import Path

from django.core import serializers
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from apps.consolidation.models import Change
from apps.corpus.models import Alias, Article, Mention, Text, Version
from apps.sources.models import Document, Edition, Issue, Page
from apps.translations.models import FrenchArticle, FrenchText

FIXTURE = Path(__file__).resolve().parents[2] / 'fixtures' / 'sample.json'
CONSTITUTION = '/akn/ma/act/dahir/1-11-91'
ISSUE = (Edition.GENERAL_AR, 7278, '')


def sample_rows() -> list:
    """Every row of the sample, read from this database in a fixed number of queries, parents before children."""
    constitution = Text.objects.get(akn_uri=CONSTITUTION)
    edition, number, suffix = ISSUE
    issue = Issue.objects.get(edition=edition, number=number, suffix=suffix)
    texts = [constitution, *Text.objects.filter(first_published_in=issue).order_by('first_published_page', 'pk')]
    uris = [t.akn_uri for t in texts]
    issues = Issue.objects.filter(pk__in={issue.pk, constitution.first_published_in_id}).order_by('date')
    versions = list(Version.objects.filter(text__in=texts).order_by('text_id', 'language', 'valid_from', 'pk'))
    french = list(FrenchText.objects.filter(text_uri__in=uris).order_by('text_uri'))
    documents = Document.objects.filter(
        pk__in={i.document_id for i in issues} | {v.source_document_id for v in versions if v.source_document_id}
        | set(Document.objects.filter(sha256__in=[f.document_sha for f in french]).values_list('pk', flat=True))
    ).order_by('pk')
    # The French pages: those of the printed range each French text names, not the whole translation issue.
    french_pages = Page.objects.none()
    for f in french:
        low, _, high = f.pages.partition('-')
        if low.isdigit():
            french_pages |= Page.objects.filter(document__sha256=f.document_sha,
                                                printed_number__range=(int(low), int(high or low)))
    pages = (Page.objects.filter(document__in=[i.document_id for i in issues]) | french_pages).order_by('document_id', 'index')
    return [*documents, *issues, *pages, *texts, *versions,
            *Article.objects.filter(version__in=versions).order_by('version_id', 'order'),
            *Alias.objects.filter(uri__in=uris).order_by('alias'),
            *Mention.objects.filter(from_uri__in=uris).order_by('from_uri', 'from_eid', 'start', 'pk'),
            *Change.objects.filter(text_uri__in=uris).order_by('text_uri', 'number', 'pk'),
            *french, *FrenchArticle.objects.filter(text_uri__in=uris).order_by('text_uri', 'order')]


def renumbered(rows: list) -> list[dict]:
    """The rows as fixture objects, each model's keys counted again from 1 and the foreign keys that point at them
    with them."""
    objects = serializers.serialize('python', rows)
    new: dict[str, dict] = {}
    for obj in objects:
        keys = new.setdefault(obj['model'], {})
        keys[obj['pk']] = len(keys) + 1
    links = {'sources.issue': {'document': 'sources.document', 'copy_of': 'sources.issue'},
             'sources.page': {'document': 'sources.document'},
             'corpus.text': {'first_published_in': 'sources.issue'},
             'corpus.version': {'text': 'corpus.text', 'source_document': 'sources.document'},
             'corpus.article': {'version': 'corpus.version'}}
    for obj in objects:
        for field, model in links.get(obj['model'], {}).items():
            if obj['fields'][field] is not None:
                obj['fields'][field] = new[model][obj['fields'][field]]
        obj['pk'] = new[obj['model']][obj['pk']]
    return objects


class Command(BaseCommand):
    help = 'Load the sample corpus (the 2011 Constitution and BO 7278) into an empty database.'

    def add_arguments(self, parser):
        parser.add_argument('--write-fixture', action='store_true',
                            help="write the fixture again from this database's rows (reads only)")

    def handle(self, *args, write_fixture=False, **opts):
        if write_fixture:
            return self.write_fixture()
        if not FIXTURE.is_file():
            raise CommandError(f'{FIXTURE}: no such file.')
        if Text.objects.exists() or Document.objects.exists():
            raise CommandError('This database already holds texts or files: load the sample into an empty database '
                               '(a new SQLite file, or a new PostgreSQL database), after migrate.')
        from apps.corpus.services import generation
        from apps.search.services import index

        with transaction.atomic():
            call_command('loaddata', str(FIXTURE), verbosity=0)
        texts = list(Text.objects.all())
        index.rebuild(texts, log=self.stdout.write)
        generation.bump()
        articles = Article.objects.count()
        self.stdout.write(f'sample loaded: {len(texts)} texts, {articles} articles, {Page.objects.count()} pages, '
                          f'{FrenchText.objects.count()} French texts')

    def write_fixture(self):
        objects = renumbered(sample_rows())
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        lines = (json.dumps(o, ensure_ascii=False, sort_keys=True, cls=DjangoJSONEncoder) for o in objects)
        FIXTURE.write_text('[\n' + ',\n'.join(lines) + '\n]\n', encoding='utf-8')
        counts: dict[str, int] = {}
        for o in objects:
            counts[o['model']] = counts.get(o['model'], 0) + 1
        self.stdout.write(f'{FIXTURE.name}: ' + ', '.join(f'{n} {m}' for m, n in counts.items()))
