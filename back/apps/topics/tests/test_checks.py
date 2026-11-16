"""A person's check of a topic's item is kept in the database under the account that made it (F17 of the family plan,
R2 of the road tools review): never in the code's folder, which a deploy replaces, and only for an item the topic has."""
import importlib
import shutil

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient

from apps.topics.models import ItemCheck
from apps.topics.services import kit
from apps.topics.services.kit import folders

pytestmark = pytest.mark.django_db


@pytest.fixture
def road(tmp_path, monkeypatch):
    """The road's folder copied here: whatever the desk did, it could not write into the code's own."""
    copy = tmp_path / 'road'
    shutil.copytree(kit.folder('road'), copy)
    real = kit.folder
    monkeypatch.setattr(folders, 'folder', lambda slug: copy if slug == 'road' else real(slug))
    kit.load.cache_clear()
    yield copy
    kit.load.cache_clear()


@pytest.fixture
def reviewer():
    user = get_user_model().objects.create_user(username='salma', email='salma@example.org', password='a long pass 12',
                                                is_staff=True, display_name='سلمى، محامية')
    user.user_permissions.add(Permission.objects.get(codename='review_topic'))
    client = APIClient()
    client.force_authenticate(get_user_model().objects.get(pk=user.pk))
    return client, user


def test_a_check_is_kept_under_the_account_that_made_it(road, reviewer):
    client, user = reviewer
    r = client.post('/api/topics/road/review/', {'refs': ['journeys/radar', 'tools/fine'], 'by': 'someone else'},
                    format='json')
    assert r.status_code == 200
    assert {ref: c['by'] for ref, c in r.json()['checked'].items()} == {'journeys/radar': 'سلمى، محامية',
                                                                        'tools/fine': 'سلمى، محامية'}
    rows = {c.ref: c for c in ItemCheck.objects.filter(topic='road')}
    assert set(rows) == {'journeys/radar', 'tools/fine'} and {c.user_id for c in rows.values()} == {user.pk}
    assert rows['journeys/radar'].digests is not None and rows['tools/fine'].digests == {}
    assert not (road / 'checked.yaml').exists()                   # nothing in the code's folder
    content = kit.load('road')
    assert content['journeys']['radar']['checked']['by'] == 'سلمى، محامية'
    assert next(t for t in content['hub']['tools'] if t['key'] == 'fine')['checked']['by'] == 'سلمى، محامية'


def test_a_check_outlives_the_code_folder_a_deploy_replaces(road, reviewer, tmp_path, monkeypatch):
    client, _ = reviewer
    assert client.post('/api/topics/road/review/', {'refs': ['journeys/radar']}, format='json').status_code == 200
    fresh = tmp_path / 'deployed' / 'road'
    shutil.copytree(kit.BASE / 'road', fresh)
    monkeypatch.setattr(folders, 'folder', lambda slug: fresh if slug == 'road' else kit.BASE / slug.replace('-', '_'))
    kit.load.cache_clear()
    assert kit.load('road')['journeys']['radar']['checked']['by'] == 'سلمى، محامية'


@pytest.mark.parametrize('refs, code', [
    (['hub/events'], 'not_found'),               # the hub's list of doors is no item: it made every search answer 500
    (['tools/nowhere'], 'not_found'),
    (['journeys/nowhere'], 'not_found'),
    (['journeys/radar', 'tools/nowhere'], 'not_found'),
    (['journeys/' + 'x' * 200], 'invalid'),
    ([f'journeys/{i}' for i in range(101)], 'invalid'),
    ('journeys/radar', 'invalid'),
    ([], 'invalid'),
])
def test_only_an_item_the_topic_has_can_be_checked(road, reviewer, refs, code, settings):
    settings.SHOW_DRAFTS = True
    client, _ = reviewer
    r = client.post('/api/topics/road/review/', {'refs': refs}, format='json')
    assert r.status_code == 400 and r.json() == {'errors': [{'field': 'refs', 'code': code}]}
    assert not ItemCheck.objects.exists()
    assert kit.matching('شدني الرادار')                          # the search still reads every folder


def test_the_command_records_a_check_under_the_name_it_is_given(road):
    from django.core.management import CommandError, call_command
    call_command('approve_topic', 'road', 'journeys/radar', '--by', 'a reviewer')
    check = ItemCheck.objects.get(topic='road', ref='journeys/radar')
    assert (check.by, check.user) == ('a reviewer', None)
    with pytest.raises(CommandError):
        call_command('approve_topic', 'road', 'hub/events', '--by', 'a reviewer')


def test_the_checks_files_of_before_become_rows_once(tmp_path):
    migration = importlib.import_module('apps.topics.migrations.0005_item_checks')
    (tmp_path / 'family').mkdir()
    (tmp_path / 'family' / 'checked.yaml').write_text(
        "journeys/marry: {by: a reviewer, 'on': '2026-10-20', digests: {/ma/loi/70-03/art_65: abc}}\n"
        "tools/inheritance: {by: an adoul, 'on': '2026-10-21'}\n", encoding='utf-8')
    migration.files_into_rows(ItemCheck, tmp_path)
    migration.files_into_rows(ItemCheck, tmp_path)
    rows = {c.ref: c for c in ItemCheck.objects.filter(topic='family')}
    assert rows['journeys/marry'].by == 'a reviewer' and rows['journeys/marry'].digests == {'/ma/loi/70-03/art_65': 'abc'}
    assert str(rows['tools/inheritance'].on) == '2026-10-21' and len(rows) == 2


def test_the_desk_lists_each_waves_items_most_read_first_for_one_query_more(road, reviewer, monkeypatch,
                                                                            django_assert_num_queries):
    """The analytics review (15 Nov 2026): within a wave, the items whose pages were shown most in the last 28 days come
    first (a tool's own pages under it count for it); ties keep their order, an item with no page of its own comes last
    in its wave, and each wave keeps the places it held. One query reads the whole topic's pages."""
    from datetime import date, timedelta

    from django.utils import timezone

    from apps.analytics.models import DayCount
    from apps.topics.services.kit import checks
    client, _ = reviewer
    monkeypatch.setattr(timezone, 'localdate', lambda *a: date(2026, 11, 15))
    before = client.get('/api/topics/road/review/').json()['items']
    yesterday = date(2026, 11, 14)
    for day, path, n in ((yesterday, '/topics/road/tools/scenes', 30), (yesterday, '/topics/road/tools/scenes/quiz', 5),
                         (yesterday, '/topics/road/pages/where', 20), (yesterday, '/topics/road/journeys/ticket', 20),
                         (yesterday, '/topics/road/tools/numbers', 3), (yesterday, '/topics/road', 100),
                         (yesterday, '/topics/road/series/deaths', 50), (yesterday, '/topics/roadside/journeys/radar', 70),
                         (yesterday - timedelta(28), '/topics/road/journeys/radar', 999)):
        DayCount.objects.create(day=day, metric='page.path', key=path, count=n)
    # The articles the items cite (one query on an empty corpus) and, since the analytics review, the pages' readings.
    with django_assert_num_queries(2):
        items = client.get('/api/topics/road/review/').json()['items']
    readers = {i['ref']: i['readers'] for i in items}
    assert (readers['tools/scenes'], readers['journeys/ticket'], readers['journeys/radar']) == (35, 20, 0)
    assert readers['series/deaths'] is None and readers['cards/batch-1'] is None
    wave = lambda rows, n: [i['ref'] for i in rows if i['wave'] == n]
    assert wave(items, 1)[:4] == ['tools/scenes', 'journeys/ticket', 'pages/where', 'journeys/radar']
    assert sorted(wave(items, 1)) == sorted(wave(before, 1))
    assert wave(items, None) == ['tools/numbers', 'reform/lf-2027', 'tools/where', 'cards/batch-1']
    assert [i['wave'] for i in items] == [i['wave'] for i in before]          # each wave where it was
    assert wave(items, 2) == wave(before, 2)                                     # nothing read: today's order
    for k in range(30):
        DayCount.objects.create(day=yesterday, metric='page.path', key=f'/topics/road/pages/other-{k}', count=k + 1)
    # A topic's reform has its own page at the topic's /reform: the item reform/reform.
    assert checks._item_of('/topics/family/reform', '/topics/family/') == 'reform/reform'
    assert checks._item_of('/topics/family/reform/stage-2', '/topics/family/') == 'reform/stage-2'
    assert checks._item_of('/topics/family/changes', '/topics/family/') is None
    with django_assert_num_queries(2):
        client.get('/api/topics/road/review/')
