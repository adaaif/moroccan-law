"""The citation checker (POST /api/search/resolve/; OP15 of the open-source audit): it resolved up to 300 citations one
by one, about nine queries each, some 2,700 queries a request with no account. All of them now come in a fixed
number of queries, with the very answers `resolve` gives one at a time; a field of another type is no 500."""
from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.consolidation.models import Change
from apps.corpus.models import Article, Status, Text, Version
from apps.corpus.services.citations import resolve, resolve_many
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db


def held(uri: str, *, articles=(), type='law', status=Status.IN_FORCE, title='قانون') -> Text:
    text = Text.objects.create(akn_uri=uri, type=type, number=uri.rsplit('/', 1)[1], status=status, title_ar=title)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2020, 1, 1))
    for i, n in enumerate(articles):
        Article.objects.create(version=v, order=i + 1, label=f'المادة {n}', number=n, eid=f'art_{n}', body='نص.')
    return text


@pytest.fixture
def corpus():
    law = held('/akn/ma/act/loi/12-26', articles=('1', '2', '3'))
    by = held('/akn/ma/act/loi/5-25')
    for number, day in (('2', date(2025, 6, 1)), ('2', date(2026, 3, 1)), ('', date(2026, 4, 1)), ('3', date(2026, 5, 1))):
        Change.objects.create(text_uri=law.akn_uri, number=number, verb='amended', source='reading', state='read',
                              by_uri=by.akn_uri, by_kind='law', by_number='5-25', published_on=day)
    held('/akn/ma/act/code/doc', articles=('230',), title='قانون الالتزامات والعقود')
    held('/akn/ma/act/loi/1-58', articles=('1',), status=Status.REPEALED)
    held('/akn/ma/act/projet-loi/60-26', articles=('7',), type='bill', title='مشروع قانون المالية رقم 60.26')
    Issue.objects.create(edition=Edition.GENERAL_AR, number=7533, date=date(2026, 8, 10))


CITATIONS = [
    {'kind': 'article', 'raw': 'المادة 2 من القانون رقم 12.26', 'article': '2', 'text_kind': 'law', 'text_number': '12-26'},
    {'kind': 'article', 'raw': 'المادة 9 من القانون رقم 12.26', 'article': '9', 'text_kind': 'law', 'text_number': '12-26'},
    {'kind': 'text', 'raw': 'القانون رقم 12.26', 'text_kind': 'law', 'text_number': '12-26'},
    {'kind': 'article', 'raw': 'الفصل 230 من ق.ل.ع', 'article': '230', 'code': 'doc'},
    {'kind': 'article', 'raw': 'المادة 3 من مدونة الأسرة', 'article': '3', 'code': 'family'},
    {'kind': 'article', 'raw': 'الفصل 1 من القانون رقم 1.58', 'article': '1', 'text_kind': 'law', 'text_number': '1-58'},
    {'kind': 'article', 'raw': 'المادة 7 من القانون رقم 60.26', 'article': '7', 'text_kind': 'law', 'text_number': '60-26'},
    {'kind': 'text', 'raw': 'القانون رقم 99.99', 'text_kind': 'law', 'text_number': '99-99'},
    {'kind': 'issue', 'raw': 'ج.ر 7533', 'issue': 7533},
    {'kind': 'issue', 'raw': 'ج.ر 9999', 'issue': '9999'},
    {'kind': 'article', 'raw': 'المادة 5'},
]


def test_the_list_is_answered_as_each_citation_alone(corpus):
    from apps.search.api.views import _cited
    clean = [_cited(c) for c in CITATIONS]
    for since in (None, date(2026, 1, 1)):
        assert resolve_many(clean, checker=True, since=since) == [resolve(c, since) for c in clean]
    states = [r['state'] for r in resolve_many(clean, checker=True)]
    assert states == ['found', 'text_only', 'found', 'found', 'not_in_corpus', 'repealed', 'found', 'not_in_corpus',
                      'issue', 'not_in_corpus', 'unknown']


@pytest.mark.parametrize('times', [1, 20])
def test_the_checker_asks_the_same_queries_whatever_the_citations(api, corpus, times):
    with CaptureQueriesContext(connection) as asked:
        r = api.post('/api/search/resolve/', {'citations': CITATIONS * times, 'since': '2026-01-01'}, format='json')
    assert r.status_code == 200 and len(r.json()['results']) == len(CITATIONS) * times
    assert r.json()['results'][0]['changes'][0]['published'] == '2026-03-01'
    assert len(asked) <= 8, len(asked)          # 66 for these eleven before, one resolve a citation


def test_a_field_of_another_type_is_no_error(api, corpus):
    odd = [{'kind': 'article', 'article': 2, 'text_kind': 'law', 'text_number': '12-26'},
           {'kind': 'article', 'article': '230', 'code': ['doc']},
           {'kind': 'issue', 'issue': 'سبعة'}, {'kind': 'issue', 'issue': True}, 'not a citation']
    r = api.post('/api/search/resolve/', {'citations': odd}, format='json')
    assert r.status_code == 200
    assert [x['state'] for x in r.json()['results']] == ['found', 'unknown', 'unknown', 'unknown']
    assert api.post('/api/search/resolve/', [{'citations': []}], format='json').status_code == 400
