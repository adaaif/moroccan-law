"""A translation that comes back with fewer articles than were sent is kept out of the file, and the file says why: «articles
differ», not the API's ordinary stop reason («end_turn»), which says nothing of what went wrong."""
import json
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.corpus.tests import claude
from apps.sources.models import Document, Edition, Issue
from apps.translations.models import FrenchArticle, FrenchText

pytestmark = pytest.mark.django_db


def test_a_translation_short_of_an_article_is_refused_as_such(tmp_path, settings, monkeypatch):
    claude.install(monkeypatch, settings, tmp_path, lambda cid, params: {
        'title': 'قرار بعقوبة', 'articles': [{'key': 'a0', 'label': 'المادة الأولى', 'body': 'يعاقب.'}]})
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='e' * 64, path='issues/bo_fr/BO_18_fr.pdf',
                                  mime='application/pdf', language='fr', bytes=1, fetched_at=timezone.now(), page_count=1)
    Issue.objects.create(edition=Edition.TRANSLATION_FR, number=18, date=date(1913, 3, 21), document=doc)
    uri = '/akn/ma/act/decision/1913-03-21/bofr18-9'
    FrenchText.objects.create(text_uri=uri, type='decision', title='Décision portant punition', issue_number=18,
                              issue_date=date(1913, 3, 21), document_sha='e' * 64, pages='79-79')
    for k in (1, 2):
        FrenchArticle.objects.create(text_uri=uri, order=k, label=f'Article {k}', number=str(k), body='Il est puni.')
    call_command('translate_french', '18', '--write', out=str(tmp_path), stdout=StringIO())
    data = json.loads((tmp_path / 'bo_18_fr.json').read_text())
    assert data['texts'] == [] and data['refused'] == [{'text_uri': uri, 'why': 'articles differ'}]
