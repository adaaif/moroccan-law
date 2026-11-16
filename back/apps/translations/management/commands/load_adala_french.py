"""A French consolidation from Adala beside its Arabic text (T1 of the work plan):

    fetch_adala ".../code du travail-1714463246806.pdf" --name labour_65_99_fr --language fr
    load_adala_french sources/adala/labour_65_99_fr.pdf --text /akn/ma/act/loi/65-99 --as-of 2011-10-26 \
        --issue 5210 --issue-date 2004-05-06 --title "Loi n° 65-99 relative au Code du travail"

The French BO issue that first printed the text is kept as its source; `consolidated_to` says the file stands at
Adala's date, so an article changed since shows its French as older than its Arabic.
"""
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.consolidation.services import sgg
from apps.corpus.models import Text
from apps.sources.models import Document, Source
from apps.sources.services.ingest import corpus_path
from apps.translations.models import FrenchArticle, FrenchText
from apps.translations.services import adala_fr


class Command(BaseCommand):
    help = "Load an Adala French consolidation as a text's French."

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--text', required=True, help='the Arabic text\'s AKN URI')
        parser.add_argument('--title', required=True)
        parser.add_argument('--as-of', required=True, help='Adala\'s «version consolidée en date du», YYYY-MM-DD')
        parser.add_argument('--issue', type=int, required=True, help='the French BO issue that first printed it')
        parser.add_argument('--issue-date', required=True)

    def handle(self, *args, path, text, title, as_of, issue, issue_date, **opts):
        doc = Document.objects.filter(source=Source.ADALA, path=path).first()
        arabic = Text.objects.filter(akn_uri=text).first()
        if doc is None or arabic is None:
            raise CommandError(f'{path} or {text}: not found')
        articles = adala_fr.read(str(corpus_path(doc)))
        if not articles:
            raise CommandError(f'{path}: no article read')
        articles += [{'label': e['label'], 'number': e['article'], 'body': e['table'], 'page': e.get('page', 1)}
                     for e in sgg.page_entries(Path(path).stem) if 'from' not in e]      # an annex read in the session
        FrenchText.objects.update_or_create(text_uri=text, defaults={
            'type': arabic.type, 'number': arabic.number, 'title': title, 'signed_on': arabic.signed_on,
            'issue_number': issue, 'issue_date': date.fromisoformat(issue_date), 'document_sha': doc.sha256,
            'pages': f'1-{doc.page_count}', 'consolidated_to': date.fromisoformat(as_of)})
        FrenchArticle.objects.filter(text_uri=text).delete()
        FrenchArticle.objects.bulk_create([FrenchArticle(text_uri=text, order=k + 1, label=a['label'], number=a['number'],
                                                         body=a['body'], printed_page=a['page']) for k, a in enumerate(articles)])
        Text.objects.filter(akn_uri=text, title_fr='').update(title_fr=title)
        self.stdout.write(f'{text}: {len(articles)} French articles, from {articles[0]["label"]} to {articles[-1]["label"]}')
