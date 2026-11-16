"""Load a `translate_french` file: each text's official French (FrenchText, FrenchArticle) and its machine-translated
Arabic, a version of its own (`consolidation='translation'`, `translated_from='fr'`), with no API, the same words in
every database. A text whose Arabic the site holds from the Bulletin is never touched; a reload replaces only the
translation. Each loaded text is indexed for search.

    load_translated apps/translations/data/translated/bo_7410_fr.json"""
import json
from datetime import date, datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Edition, Issue
from apps.translations.models import FrenchArticle, FrenchText


def arabic_number(number: str) -> str:
    """A text's number as the Arabic Bulletin prints it: «1-25-39» is «1.25.39»."""
    return number.replace('-', '.')


class Command(BaseCommand):
    help = 'Load a file of texts machine-translated from the official French edition.'

    def add_arguments(self, parser):
        parser.add_argument('path')

    def handle(self, *args, path, **opts):
        data = json.loads(Path(path).read_text())
        day = date.fromisoformat(data['date'])
        at = datetime.fromisoformat(data['translated_at'])
        # Before 1956 the French edition printed texts the Arabic never did (A of the Bulletin-from-No.-1 review): such a text
        # was first published in its French issue, which lists it and gives its stamp. BO 7410's texts were printed in an
        # Arabic issue that is only not online: they keep none.
        french_issue = (Issue.objects.filter(edition=Edition.TRANSLATION_FR, number=data['french']['number'],
                                             suffix=data['french']['suffix']).first() if day.year < 1956 else None)
        loaded, held = [], []
        with transaction.atomic():
            for t in data['texts']:
                FrenchText.objects.update_or_create(text_uri=t['text_uri'], defaults={
                    'type': t['type'], 'number': t['number'], 'title': t['title_fr'][:2000],
                    'signed_on': t['signed_on'] and date.fromisoformat(t['signed_on']),
                    'issue_number': data['french']['number'], 'issue_suffix': data['french']['suffix'],
                    'issue_date': date.fromisoformat(data['french']['date']), 'document_sha': data['french']['sha256'],
                    'pages': t['pages_fr']})
                FrenchArticle.objects.filter(text_uri=t['text_uri']).delete()
                FrenchArticle.objects.bulk_create([
                    FrenchArticle(text_uri=t['text_uri'], order=a['order'], label=a['label_fr'][:80], number=a['number'],
                                  body=a['body_fr'], printed_page=a['page_fr']) for a in t['articles']])
                text, _ = Text.objects.get_or_create(akn_uri=t['text_uri'], defaults={
                    'type': t['type'], 'number': t['number'], 'number_as_printed': arabic_number(t['number'])})
                if text.versions.filter(language='ar').exclude(consolidation=Consolidation.TRANSLATION).exists():
                    held.append(t['text_uri'])        # the Bulletin's Arabic stands: the translation is not loaded
                    continue
                text.title_ar = text.title_ar or t['title_ar']
                text.title_fr = t['title_fr'][:2000]
                text.signed_on = text.signed_on or (t['signed_on'] and date.fromisoformat(t['signed_on']))
                text.number_as_printed = text.number_as_printed or arabic_number(t['number'])
                if french_issue and not text.first_published_in_id:
                    text.first_published_in = french_issue
                    first = (t['pages_fr'] or '').split('-')[0]
                    text.first_published_page = int(first) if first.isdigit() else None
                text.save()
                text.versions.filter(consolidation=Consolidation.TRANSLATION).delete()
                version = Version.objects.create(
                    text=text, language='ar', valid_from=day, consolidation=Consolidation.TRANSLATION,
                    source_pages=t['pages_fr'], translated_from=data['translated_from'],
                    translated_by=data['translated_by'], translated_at=at)
                Article.objects.bulk_create([
                    Article(version=version, order=a['order'], label=a['label_ar'][:80], number=a['number'],
                            eid=f"art_{a['number']}" if a['number'] else f"art_o{a['order']}", body=a['body_ar'])
                    for a in t['articles']])
                loaded.append(text)
        from apps.search.services.index import rebuild
        indexed = rebuild(loaded) if loaded else None
        self.stdout.write(f'{len(loaded)} texts loaded from {Path(path).name}, {len(held)} held in Arabic left as they are'
                          f'{f"; search: {indexed}" if indexed else ""}')
