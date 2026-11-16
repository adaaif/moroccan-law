"""An article's discussion page carries the article whole: its words count against the day of reading, as on its text's
page (OP17 of the open-source audit: /api/discussion/cited/ let article text leave unmetered)."""
import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.corpus.tests.test_reading_budget import counted
from apps.discussion.tests.conftest import ARTICLE, lease  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db
READER = {'HTTP_CF_CONNECTING_IP': '105.155.1.2', 'HTTP_X_FORWARDED_FOR': '105.155.1.2, 127.0.0.1'}


@pytest.fixture(autouse=True)
def fresh():
    cache.clear()
    yield
    cache.clear()


@override_settings(READING_BUDGET=2)
def test_the_article_on_its_discussions_page_counts_as_one(api, lease):
    first = api.get('/api/discussion/cited/', {'path': ARTICLE}, **READER)
    assert first.status_code == 200 and first.json()['article']['label'] == 'المادة 34'
    assert counted() == 1
    missing = api.get('/api/discussion/cited/', {'path': '/ma/loi/2013/67-12/art_99'}, **READER)
    assert missing.status_code == 404 and counted() == 1       # nothing given, nothing counted
    assert api.get('/api/discussion/cited/', {'path': ARTICLE}, **READER).status_code == 200
    past = api.get('/api/discussion/cited/', {'path': ARTICLE}, **READER)
    assert past.status_code == 429 and past.json() == {'errors': [{'field': 'reading', 'code': 'limit'}]}
