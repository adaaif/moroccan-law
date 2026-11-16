"""The tax code as the DGI's yearly edition prints it (the tax review, T1): the Arabic edition becomes a version of
the code (`consolidation='dgi'`, unofficial, the BO prevails), the French edition its French beside it, and each footnote
of the French («Article 8 de la loi de finances n° 60-24 pour l'année budgétaire 2025») a witness that that finance law
changed the article (Change, source «dgi»), which the links pipeline weighs against its own reading of the law.

    load_dgi sources/dgi/cgi_2026_ar.pdf sources/dgi/cgi_2026_fr.pdf --as-of 2026-01-01
"""
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.consolidation.models import Change
from apps.consolidation.services import dgi
from apps.consolidation.services.instructions.labels import label_key
from apps.consolidation.services.versions import save_version, text_at
from apps.corpus.models import Consolidation, Text
from apps.corpus.services import works
from apps.sources.models import DocumentKind, Source
from apps.sources.services.ingest import ingest_file
from apps.translations.models import FrenchArticle, FrenchText

URI = '/akn/ma/act/code/cgi'
TITLE = 'المدونة العامة للضرائب'
TITLE_FR = 'Code général des impôts'
URL = 'https://www.tax.gov.ma'
# The French BO that first printed the code: finance law 43-06 for 2007 (dahir 1-06-232), BO 5487 bis of 1 January 2007.
FIRST_FR = (5487, 'bis', date(2007, 1, 1))


class Command(BaseCommand):
    help = "Load the DGI's yearly edition of the tax code: the Arabic as a version, the French beside it, the footnotes as witnesses."

    def add_arguments(self, parser):
        parser.add_argument('arabic', help='the Arabic edition under CORPUS_DIR')
        parser.add_argument('french', help='the French edition under CORPUS_DIR')
        parser.add_argument('--as-of', required=True, help='the date the edition stands at (its finance law\'s 1 January)')

    def handle(self, *args, arabic, french, as_of, **opts):
        on = date.fromisoformat(as_of)
        docs = {}
        for lang, rel in (('ar', arabic), ('fr', french)):
            path = Path(settings.CORPUS_DIR) / rel
            if not path.exists():
                raise CommandError(f'{rel}: not found')
            docs[lang] = ingest_file(path, source=Source.DGI, kind=DocumentKind.CONSOLIDATED_TEXT, language=lang, url=URL)
        read = dgi.read(str(Path(settings.CORPUS_DIR) / arabic))
        articles = read.text.articles
        if len(articles) < 200:
            raise CommandError(f'{arabic}: only {len(articles)} articles read')
        fr_articles, notes = dgi.read_french(str(Path(settings.CORPUS_DIR) / french))
        with transaction.atomic():
            text, created = text_at(URI, TITLE)
            Text.objects.filter(pk=text.pk).update(title_ar=TITLE, title_fr=TITLE_FR, type='law')
            docs['ar'].meta = {**docs['ar'].meta, 'as_of': on.isoformat(), 'layer': read.text.stats}
            docs['ar'].save(update_fields=['meta'])
            rows = save_version(text, Consolidation.DGI, docs['ar'], on, articles)
            number, suffix, issued = FIRST_FR
            FrenchText.objects.update_or_create(text_uri=URI, defaults={
                'type': 'law', 'number': '', 'title': TITLE_FR, 'signed_on': date(2006, 12, 31), 'issue_number': number,
                'issue_suffix': suffix, 'issue_date': issued, 'document_sha': docs['fr'].sha256,
                'pages': f'1-{docs["fr"].page_count}', 'consolidated_to': on})
            FrenchArticle.objects.filter(text_uri=URI).delete()
            FrenchArticle.objects.bulk_create([FrenchArticle(text_uri=URI, order=k + 1, label=a['label'], number=a['number'],
                                                             body=a['body'], printed_page=a['page']) for k, a in enumerate(fr_articles)])
            Change.objects.filter(text_uri=URI, source=Change.Source.DGI).delete()
            witnesses, seen = [], set()
            for f in notes:
                if not f.article:
                    continue
                for law in dgi.footnote_laws(f.text):
                    key = (f.article, law['number'])
                    if key in seen:
                        continue
                    seen.add(key)
                    by, _ = works.resolve('law', law['number'].replace('.', '-'))
                    witnesses.append(Change(text_uri=URI, number=label_key(f'المادة {f.article}') or f.article, verb='modified',
                                            source=Change.Source.DGI, by_kind='law', by_number=works.fold(law['number'].replace('.', '-')),
                                            by_uri=by or '', by_article=law['article']))
            Change.objects.bulk_create(witnesses)
        self.stdout.write(f'{URI}: {len(rows)} articles (Arabic), {len(fr_articles)} French, {len(notes)} footnotes, '
                          f'{len(witnesses)} witnesses; layer {read.text.stats}' + ('  (new text)' if created else ''))
