"""Answers kept by what they depend on (S14 of the performance audit) and what a public answer says about being kept
(S17): a kept answer costs no query, anything that writes what it shows makes it worked out again, and an answer to a
signed-in reader is never marked as public."""
from datetime import date

import pytest
from django.core.cache import caches
from django.test import override_settings

from apps.corpus.models import Consolidation, Version
from apps.corpus.services import generation
from apps.corpus.tests.test_perf import law
from apps.discussion.models import Contribution, Discussion
from apps.discussion.tests.conftest import lease, make_user, uploads  # noqa: F401  (fixtures)

pytestmark = pytest.mark.django_db

KEPT = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'kept-default'},
        'answers': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'kept-answers'}}


@pytest.fixture
def kept():
    with override_settings(CACHES=KEPT):
        caches['answers'].clear()
        yield caches['answers']
        caches['answers'].clear()


def test_a_kept_answer_costs_no_query_until_the_corpus_changes(api, kept, django_assert_num_queries):
    law('31-08', articles=4)
    first = api.get('/api/corpus/shelf/')
    assert first.status_code == 200 and first['ETag']
    with django_assert_num_queries(0):
        again = api.get('/api/corpus/shelf/')
    assert again.content == first.content and again['ETag'] == first['ETag']
    assert api.get('/api/corpus/shelf/', HTTP_IF_NONE_MATCH=first['ETag']).status_code == 304
    # A command wrote the corpus (manage.py bumps after it): the shelf is worked out again and says so.
    law('18-00', articles=2)
    generation.bump('corpus')
    fresh = api.get('/api/corpus/shelf/')
    assert fresh['ETag'] != first['ETag']
    assert {b['key'] for b in fresh.json() if b['state'] == 'in_corpus'} == {'consumer', 'co_ownership'}


def test_a_text_window_is_kept_per_window_and_day(api, kept, django_assert_max_num_queries):
    law('31-08', articles=50, versions=(Consolidation.AS_PUBLISHED,))
    a = api.get('/api/corpus/at/ma/loi/31-08/', {'window': 30}).json()
    with django_assert_max_num_queries(1):          # the address is followed each time (an alias redirects)
        assert api.get('/api/corpus/at/ma/loi/31-08/', {'window': 30}).json() == a
    assert api.get('/api/corpus/at/ma/loi/31-08/art_40/', {'window': 30}).json()['range'] == [37, 50]


def test_a_discussion_is_worked_out_again_after_any_contribution(api, kept, lease):
    path = '/talk/housing'
    d = Discussion.objects.create(path=path, text_path=path)
    asker = make_user('asker')
    Contribution.objects.create(discussion=d, author=asker, kind='question', title='سؤال', body='سؤال أول؟')
    first = api.get('/api/discussion/feed/', {'place': path}).json()
    assert len(first['posts']) == 1
    Contribution.objects.create(discussion=d, author=asker, kind='question', title='سؤال', body='سؤال ثان؟')  # a signal bumps
    assert len(api.get('/api/discussion/feed/', {'place': path}).json()['posts']) == 2


def test_a_signed_in_reader_is_answered_fresh_and_never_marked_public(api, kept, lease):
    path = '/talk/housing'
    Discussion.objects.create(path=path, text_path=path)
    anonymous = api.get('/api/discussion/feed/', {'place': path})
    assert anonymous['Cache-Control'] == 'public, max-age=10, stale-while-revalidate=60'
    api.force_authenticate(make_user('reader'))
    signed = api.get('/api/discussion/feed/', {'place': path}, HTTP_AUTHORIZATION='Bearer x')
    assert signed.status_code == 200 and 'Cache-Control' not in signed


def test_public_reads_say_how_long_they_may_be_kept(api):
    law('31-08')
    assert api.get('/api/corpus/shelf/')['Cache-Control'] == 'public, max-age=60, stale-while-revalidate=600'
    assert 'Authorization' in api.get('/api/corpus/shelf/')['Vary']
    assert 'Cache-Control' not in api.get('/api/corpus/shelf/', HTTP_AUTHORIZATION='Bearer x')


def test_a_long_texts_outline_has_its_own_address_kept_for_good(api, kept):
    # S15 of the performance audit: the outline was 242 KB of the DOC's 313 KB window, sent with every window.
    law('31-08', articles=50)
    d = api.get('/api/corpus/at/ma/loi/31-08/', {'window': 30}).json()
    assert d['outline'] is None and d['outline_url'].startswith('/api/corpus/outline/')
    r = api.get(d['outline_url'])
    assert r['Cache-Control'] == 'public, max-age=31536000, immutable'
    outline = r.json()['outline']
    assert [o['eid'] for o in outline] == [f'art_{i}' for i in range(1, 51)] and outline[0]['w'].startswith('نص المادة')
    # Another generation, another address: the one kept by a browser is never the new corpus's.
    generation.bump('corpus')
    assert api.get('/api/corpus/at/ma/loi/31-08/', {'window': 30}).json()['outline_url'] != d['outline_url']
    assert 'immutable' not in api.get(d['outline_url'])['Cache-Control']


def test_a_short_text_comes_whole_without_an_outline(api):
    law('31-08', articles=5)
    d = api.get('/api/corpus/at/ma/loi/31-08/', {'window': 30}).json()
    assert d['outline'] is None and d['outline_url'] is None and len(d['articles']) == 5


def test_a_topics_folder_is_kept_not_read_again_by_each_worker(api, kept, monkeypatch):
    # Each worker read a folder's YAML on its first request to it, about a second each time (26 Oct 2026).
    from apps.topics.services import kit
    first = api.get('/api/topics/family/')
    assert first.status_code == 200 and first.json()['module']
    monkeypatch.setattr(kit, 'hub', lambda slug: pytest.fail('the hub was worked out again'))
    assert api.get('/api/topics/family/').json()['module'] == first.json()['module']


def test_a_topic_is_kept_by_the_browser_longer_than_the_law(api):
    assert api.get('/api/topics/family/')['Cache-Control'] == 'public, max-age=300, stale-while-revalidate=86400'
    assert api.get('/api/topics/')['Cache-Control'] == 'public, max-age=300, stale-while-revalidate=86400'


def _keys(kept) -> set:
    return set(kept._cache)


def test_a_texts_answer_is_kept_under_what_it_is_made_of_not_what_was_asked(api, kept):
    """OP18: every `on` date, every window size and any anchor were a new key, so a caller filled the cache at will."""
    text = law('31-08', articles=50, day=date(2020, 1, 1))
    Version.objects.create(text=text, language='ar', valid_from=date(2024, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    a = api.get('/api/corpus/at/ma/loi/31-08/', {'window': 30, 'on': '2021-03-01'}).content
    first = _keys(kept)
    # Another day of the same version's life, a window as long, an anchor the text does not hold: the same answer.
    assert api.get('/api/corpus/at/ma/loi/31-08/', {'window': 30, 'on': '2022-07-15'}).content == a
    assert api.get('/api/corpus/at/ma/loi/31-08/', {'window': 30, 'on': '2023-12-31'}).content == a
    assert api.get('/api/corpus/at/ma/loi/31-08/art_999/', {'window': 30, 'on': '2021-03-01'}).json()['range'] == [0, 30]
    assert api.get('/api/corpus/at/ma/loi/31-08/', {'from': 45, 'count': 40, 'on': '2021-01-02'}).json()['range'] == [45, 50]
    assert api.get('/api/corpus/at/ma/loi/31-08/', {'from': 45, 'count': 80, 'on': '2021-01-02'}).json()['range'] == [45, 50]
    assert api.get('/api/corpus/at/ma/loi/31-08/', {'from': 9000, 'on': '2021-01-02'}).json()['range'] == [50, 50]
    assert api.get('/api/corpus/at/ma/loi/31-08/', {'from': 9001, 'on': '2021-01-02'}).json()['range'] == [50, 50]
    assert len(_keys(kept) - first) == 2               # the two spans; the window and the version are those kept already
    # The version in force on another day is another answer.
    assert api.get('/api/corpus/at/ma/loi/31-08/', {'window': 30, 'on': '2025-01-01'}).content != a


def _answers_kept(kept) -> list:
    return [v for v in (kept.get(k.split(':', 2)[-1]) for k in _keys(kept)) if isinstance(v, (bytes, tuple))]


def test_an_answer_too_large_is_never_kept(api, kept, settings):
    law('31-08', articles=50)
    settings.ANSWERS_KEPT_MOST = 1000
    big = api.get('/api/corpus/at/ma/loi/31-08/', {'window': 30})
    assert len(big.content) > 1000 and _answers_kept(kept) == []
    assert api.get('/api/corpus/at/ma/loi/31-08/', {'window': 30}).content == big.content       # worked out again
    settings.ANSWERS_KEPT_MOST = 2_000_000
    api.get('/api/corpus/at/ma/loi/31-08/', {'window': 30})
    assert [len(body) for body, _ in _answers_kept(kept)] == [len(big.content)]


def test_a_lookup_that_found_nothing_is_never_kept(api, kept, tmp_path, settings):
    """A law's page for an anchor that leads nowhere, an article no bill names: answered, nothing kept."""
    (tmp_path / 'index.html').write_text('<html><head><title>قانون</title></head><body><div id="root"></div></body></html>')
    settings.WEB_DIST = str(tmp_path)
    law('31-08', articles=5)
    api.get('/ma/loi/31-08')
    before = _keys(kept)
    for n in range(5):
        assert api.get(f'/ma/loi/31-08/art_{100 + n}').status_code == 404
        assert api.get('/api/corpus/proposed/', {'path': f'/ma/loi/31-08/art_{100 + n}'}).json()['proposals'] == []
    assert len(_keys(kept) - before) <= 1             # the bill's numbers for the text, once
