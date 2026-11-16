"""Each read of v1 costs the same number of queries on a small corpus and on one several times its size: more
articles, more changes, more texts in an issue, more issues, more references and more search results. The key is warm
(kept a minute, apps/opendata/services/keys.py) and the counts' once-a-minute writes are left out (they are
usage.py's, measured in test_usage.py): what is counted is the read itself."""
from datetime import timedelta
from unittest import mock

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.corpus.models import Article, Version
from apps.mcp.tests.conftest import labour  # noqa: F401  (a fixture)
from apps.opendata.models import Access
from apps.opendata.services import usage
from apps.opendata.tests.helpers import accepted, keyed
from apps.opendata.tests.test_v1 import (FOUND, ago, change_of, get, issue_of, law_of, made,  # noqa: F401  (fixtures)
                                         post, requests_open)
from apps.translations.models import FrenchArticle

pytestmark = pytest.mark.django_db
# One of each kind a list of references asks its own queries for (apps/mcp/tests/test_loops.py).
REFERENCES = ['المادة 51 من القانون رقم 65.99', 'القانون رقم 12.26', 'ج.ر 7533', 'الفصل 230 من ق.ل.ع', 'شكرا']


def grow(made) -> None:
    """The corpus several times over: forty more articles in each of the labour code's versions with their French,
    twenty changes to it, thirty more texts in the newest issue, ten older issues."""
    for version in Version.objects.filter(text=made['labour']):
        Article.objects.bulk_create(Article(version=version, order=100 + n, label=f'المادة {n}', number=str(n),
                                            eid=f'art_{n}', body=f'نص المادة {n}.', heading_path=['باب']) for n in range(55, 95))
    FrenchArticle.objects.bulk_create(FrenchArticle(text_uri=made['labour'].akn_uri, order=100 + n, label=f'Article {n}',
                                                    number=str(n), body=f'Article {n}.') for n in range(55, 95))
    for n in range(30):
        text = law_of(f'{100 + n}-26', made['recent'], page=200 + n, articles=3)
        change_of(text, number=str(49 + n % 6))
        change_of(text, number=str(55 + n))
    for k in range(10):
        older = issue_of(7000 + k, ago(400 + k))
        law_of(f'{200 + k}-20', older)


def cost(api, key, send) -> int:
    """The queries of `send`'s second call: the first fills what a process keeps for itself (the codes' table, a text's
    address), which is not the read's to count."""
    send()
    with CaptureQueriesContext(connection) as queries:
        response = send()
    assert response.status_code == 200, response.content
    return len(queries)


READS = {
    'search': lambda api, key, big: get(api, '/api/v1/search?q=مدونة الشغل', key),
    'article': lambda api, key, big: get(api, '/api/v1/texts/ma/loi/65-99/art_51', key),
    'text': lambda api, key, big: get(api, '/api/v1/texts/ma/loi/65-99', key),
    'issue': lambda api, key, big: get(api, '/api/v1/texts/bo/7533', key),
    'articles': lambda api, key, big: get(api, f'/api/v1/articles/ma/loi/65-99?count={20 if big else 2}&french=1', key),
    'articles on a day': lambda api, key, big: get(api, '/api/v1/articles/ma/loi/65-99?on=2010-01-01&count=5', key),
    'references': lambda api, key, big: post(api, '/api/v1/references', {
        'references': (REFERENCES * 10) if big else REFERENCES, 'since': str(ago(60))}, key),
    'bulletin': lambda api, key, big: get(api, '/api/v1/bulletin/', key),
    'one issue': lambda api, key, big: get(api, '/api/v1/bulletin/7533', key),
    'changes': lambda api, key, big: get(api, f'/api/v1/changes?since={ago(30)}', key),
}


def found(big: bool) -> dict:
    """The site's search answer: three results, or ten texts of ten articles each."""
    if not big:
        return FOUND
    return {**FOUND, 'results': [
        {'text': {'path': f'/ma/loi/{100 + t}-26', 'title': 'قانون', 'status': 'in_force', 'name': {'ar': 'قانون'},
                  'type': 'law'}, 'title_match': False,
         'articles': [{'label': f'المادة {a}', 'path': f'/ma/loi/{100 + t}-26/art_{a}', 'snippet': [{'t': 'نص'}]}
                      for a in range(1, 11)]} for t in range(10)]}


@pytest.mark.parametrize('read', READS)
def test_a_read_costs_the_same_whatever_the_corpus_holds(api, made, read, monkeypatch):
    monkeypatch.setattr(usage, '_written', lambda holder, now: None)
    _, key = keyed(accepted(size=Access.Size.PARTNER, minute=1000, calls=1000, articles=10_000))
    assert get(api, '/api/v1/bulletin/5167', key).status_code == 200            # the key, kept
    send = READS[read]
    with mock.patch('apps.search.services.search.search', return_value=found(False)):
        small = cost(api, key, lambda: send(api, key, False))
    grow(made)
    with mock.patch('apps.search.services.search.search', return_value=found(True)):
        big = cost(api, key, lambda: send(api, key, True))
    assert big == small, (read, small, big)


def test_the_latest_week_costs_the_same_whatever_its_issues_hold(api, made, monkeypatch, django_assert_max_num_queries):
    """The week's issues are read one by one (six at most, each kept by the site's answers): their texts and the
    issues before the week cost nothing more."""
    monkeypatch.setattr(usage, '_written', lambda holder, now: None)
    _, key = keyed()
    get(api, '/api/v1/bulletin/5167', key)
    for k in range(5):
        law_of(f'{300 + k}-26', issue_of(7534 + k, ago(19 - k)))                # a week of six issues
    full = cost(api, key, lambda: get(api, '/api/v1/bulletin/', key))
    grow(made)
    with django_assert_max_num_queries(full):
        r = get(api, '/api/v1/bulletin/', key)
    assert len(r.json()['issues']) == 6
    for k in range(3):                                                          # a newer week: one issue, fewer
        issue_of(7600 + k, ago(0) + timedelta(days=0))
    assert cost(api, key, lambda: get(api, '/api/v1/bulletin/', key)) <= full
