"""A reader's report of an error reaches the review queue, kept by the article's address."""
from datetime import date

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.quality.models import Report
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db


@pytest.fixture
def law():
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7533, date=date(2026, 8, 10))
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/12-26', type='law', number='12-26',
                               title_ar='قانون رقم 12.26', first_published_in=issue)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 8, 10),
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='المادة الأولى', number='1', eid='art_1', body='نص.')
    return text


def test_a_report_is_kept_by_address(api, law):
    r = api.post('/api/quality/reports/', {'path': '/ma/loi/12-26/art_1', 'kind': 'reading',
                                           'quote': '3000', 'message': 'في الصفحة 30000'}, format='json')
    assert r.status_code == 201
    report = Report.objects.get()
    assert (report.path, report.kind, report.status) == ('/ma/loi/12-26/art_1', 'reading', 'open')
    # The article's row can be replaced by a reload; the report stays.
    Article.objects.all().delete()
    assert Report.objects.count() == 1


def test_a_report_needs_a_known_text_a_kind_and_words(api, law):
    r = api.post('/api/quality/reports/', {'path': '/ma/loi/99-99/art_1', 'kind': 'x'}, format='json')
    assert r.status_code == 400
    assert {e['field'] for e in r.json()['errors']} == {'path', 'kind', 'message'}


def test_the_issue_quality_page(api, law):
    Report.objects.create(path='/ma/loi/12-26/art_1', kind='reading', quote='x')
    r = api.get('/api/corpus/issues/general_ar/7533/quality/')
    assert r.status_code == 404          # no document for this issue in the test


def test_articles_say_how_they_were_read(api, law):
    d = api.get('/api/corpus/at/ma/loi/12-26/').json()
    assert d['articles'][0]['reading'] is None          # no page behind it in the test
