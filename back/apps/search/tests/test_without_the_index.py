"""On SQLite (a first run on the sample) there is no search index: the search says so in the site's error shape, and
warming a worker does not ask the index anything."""
import pytest
from django.db import connection

from apps.search.services.search import suggestions

pytestmark = [pytest.mark.django_db,
              pytest.mark.skipif(connection.vendor == 'postgresql', reason='the index is there on PostgreSQL')]


def test_search_answers_a_refusal_not_a_crash(client):
    answer = client.get('/api/search/', {'q': 'الطرد'})
    assert answer.status_code == 503
    assert answer.json() == {'errors': [{'field': 'search', 'code': 'needs_postgres'}]}


def test_warming_a_worker_leaves_the_index_alone(monkeypatch):
    asked = []
    monkeypatch.setattr(suggestions, 'search', lambda *a, **k: asked.append(a))
    suggestions.warm()
    assert asked == []
