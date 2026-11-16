"""B3 of the search plan: what a reader did after a search, kept on the search's anonymous row; the words go after
90 days, the counts stay."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.search.models import SearchEvent, SearchLog
from apps.search.services.events import bucket, prune

pytestmark = pytest.mark.django_db


@pytest.fixture
def log():
    return SearchLog.objects.create(query='عقد الكراء', folded='عقد الكراء', results=3, shown=['/ma/loi/67-12/art_1'])


def test_an_answer_opened_saved_or_read_is_kept_on_the_search_row(api, log):
    assert api.post('/api/search/opened/', {'log': log.pk, 'rank': 2, 'path': '/ma/loi/67-12/art_1'}, format='json').status_code == 204
    assert api.post('/api/search/event/', {'log': log.pk, 'kind': 'saved', 'path': '/ma/loi/67-12/art_1'}, format='json').status_code == 204
    assert api.post('/api/search/event/', {'log': log.pk, 'kind': 'read', 'path': '/ma/loi/67-12/art_1', 'seconds': 42},
                    format='json').status_code == 204
    assert api.post('/api/search/event/', {'log': log.pk, 'kind': 'found'}, format='json').status_code == 204
    log.refresh_from_db()
    assert log.opened == 2
    kept = list(SearchEvent.objects.filter(log=log).order_by('id').values_list('kind', 'path', 'rank', 'seconds'))
    assert kept == [('opened', '/ma/loi/67-12/art_1', 2, None), ('saved', '/ma/loi/67-12/art_1', None, None),
                    ('read', '/ma/loi/67-12/art_1', None, 60), ('found', '', None, None)]
    # The first answer opened stays the first.
    api.post('/api/search/opened/', {'log': log.pk, 'rank': 5}, format='json')
    log.refresh_from_db()
    assert log.opened == 2


def test_a_wrong_event_is_refused_in_the_one_error_shape(api, log):
    r = api.post('/api/search/event/', {'log': log.pk, 'kind': 'liked'}, format='json')
    assert r.status_code == 400 and r.json() == {'errors': [{'field': 'kind', 'code': 'invalid'}]}
    r = api.post('/api/search/event/', {'log': log.pk, 'kind': 'shared', 'path': 'javascript:alert(1)'}, format='json')
    assert r.json() == {'errors': [{'field': 'path', 'code': 'invalid'}]}
    r = api.post('/api/search/event/', {'log': 10 ** 9, 'kind': 'shared'}, format='json')
    assert r.status_code == 404 and r.json() == {'errors': [{'field': 'log', 'code': 'not_found'}]}
    assert not SearchEvent.objects.exists()


def test_how_long_rounds_up_to_a_few_lengths():
    assert [bucket(s) for s in (0, 9, 11, 59, 61, 299, 1200)] == [10, 10, 60, 60, 300, 300, 900]
    assert bucket(-1) is None and bucket('x') is None


def test_the_words_go_after_90_days_and_the_counts_stay(log):
    old = SearchLog.objects.create(query='النفقة', folded='النفقه', results=4, shown=['/ma/loi/70-03/art_187'])
    SearchLog.objects.filter(pk=old.pk).update(at=timezone.now() - timedelta(days=91))
    SearchEvent.objects.create(log=old, kind='opened', path='/ma/loi/70-03/art_187', rank=1)
    assert prune() == 1
    old.refresh_from_db()
    log.refresh_from_db()
    assert (old.query, old.folded, old.results, old.shown) == ('', '', 4, ['/ma/loi/70-03/art_187'])
    assert old.events.count() == 1 and log.query == 'عقد الكراء'
