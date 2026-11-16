"""What `check_topic` reports of a topic's folder, what the hub shows of its doors, and a topic with no folder of its
own (F16, F17 of the family plan): two small folders written here, one topic's doors leading into the other's."""
import logging

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.topics.models import ItemCheck
from apps.topics.services import kit
from apps.topics.services.kit import folders

pytestmark = pytest.mark.django_db

HUB = """
events:
  - {key: one, title: {ar: الأولى, fr: La première}, to: journeys/one, words: [غادي نتزوج, عرس]}
  - {key: lost, title: {ar: ضاعت, fr: Perdue}, to: journeys/lost}
  - {key: calc, title: {ar: الحساب, fr: Le calcul}, to: tools/calc}
  - {key: held, title: {ar: عندهم, fr: Chez eux}, to: 'work:tools/held'}
  - {key: gone, title: {ar: مشات, fr: Partie}, to: 'work:tools/gone'}
  - {key: trip, title: {ar: الطريق, fr: Le trajet}, to: 'work:journeys/trip'}
  - {key: elsewhere, title: {ar: بعيد, fr: Ailleurs}, to: 'nowhere:journeys/trip'}
  - {key: bare, title: {ar: بلا صفحة, fr: Sans page}, to: 'work:tools'}
  # A door that is a tool of the web's own: no item of the folder to look for.
  - {key: web, title: {ar: أداة, fr: Outil}, to: tools/web, tool: true}
tools:
  - {key: calc, title: {ar: حاسبة, fr: Calculette}}
"""
JOURNEYS = """
- key: one
  title: {ar: الأولى, fr: La première}
  series: [deaths]          # only a page shows series
  steps:
    - {title: {ar: الملف, fr: Le dossier}, cites: [/ma/loi/70-03/art_9], next: journeys/lost-step}
    - {title: {ar: الحساب, fr: Le calcul}, more: [tools/calc, 'work:journeys/trip', 'work:journeys/gone']}
- key: two
  title: {ar: الثانية, fr: La seconde}
  steps: []
"""
PAGES = """
- key: numbers
  title: {ar: الأرقام, fr: Les chiffres}
  series: [births, deaths]
"""
SERIES = """
files:
  hcp-2024: {url: https://example.org/births.pdf, sha256: abc}
series:
  - key: births
    title: {ar: الولادات, fr: Les naissances}
    years:
      - {year: 2024, n: 10, from: hcp-2024}
"""
WORK_HUB = """
events: []
tools:
  - {key: held, title: {ar: أداة, fr: Un outil}}
"""
WORK_JOURNEYS = """
- key: trip
  title: {ar: الطريق, fr: Le trajet}
  steps: []
"""


@pytest.fixture
def world(tmp_path, monkeypatch, settings):
    """The family's folder and the work's, written here; every other topic has none."""
    settings.SHOW_DRAFTS = True
    monkeypatch.setattr(folders, 'BASE', tmp_path)
    for slug, files in {'family': {'hub': HUB, 'journeys': JOURNEYS, 'pages': PAGES, 'series': SERIES},
                        'work': {'hub': WORK_HUB, 'journeys': WORK_JOURNEYS}}.items():
        (tmp_path / slug).mkdir()
        for name, body in files.items():
            (tmp_path / slug / f'{name}.yaml').write_text(body, encoding='utf-8')
    kit.load.cache_clear()
    return tmp_path


@pytest.fixture
def reviewer():
    user = get_user_model().objects.create_user(username='reviewer', email='reviewer@example.org',
                                                password='a long pass 12', is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename='review_topic'))
    client = APIClient()
    client.force_authenticate(get_user_model().objects.get(pk=user.pk))
    return client


def test_check_topic_names_each_missing_page_tool_and_series_and_what_another_topic_holds_passes(world, capsys):
    call_command('check_topic', 'family')
    assert capsys.readouterr().out.splitlines() == [
        "family: {'journeys': 2, 'checklists': 0, 'pages': 1, 'reform': 0, 'series': 1, 'rates': 0, 'cards': 0}, "
        '1 articles cited',
        '  cites a missing article: /ma/loi/70-03/art_9',
        '  door «lost» leads to a missing journeys/lost',
        '  door «gone» leads to a missing work:tools/gone',
        '  door «elsewhere» leads to a missing nowhere:journeys/trip',
        '  door «bare» leads to a missing work:tools',
        '  journeys/one leads to a missing journeys/lost-step',
        '  journeys/one leads to a missing work:journeys/gone',
        '  pages/numbers shows a missing series deaths',
    ]


def test_check_topic_says_when_there_is_nothing_to_fix(world, capsys):
    call_command('check_topic', 'work')
    assert capsys.readouterr().out.splitlines() == [
        "work: {'journeys': 1, 'checklists': 0, 'pages': 0, 'reform': 0, 'series': 0, 'rates': 0, 'cards': 0}, "
        '0 articles cited',
        '  nothing to fix',
    ]


def test_the_hub_shows_only_the_doors_whose_page_or_tool_may_be_shown_here_or_in_another_topic(world):
    assert [e['key'] for e in kit.hub('family')['events']] == ['one', 'calc', 'held', 'trip']


def test_a_doors_words_are_those_its_hub_gives_it_and_an_unknown_door_has_none(world):
    assert kit.door_words('family-one') == ['غادي نتزوج', 'عرس']
    assert kit.door_words('family-lost') == [] and kit.door_words('family-nosuch') == []


def test_a_numbers_page_carries_the_series_its_topic_has(world, api):
    page = api.get('/api/topics/family/pages/numbers/').json()
    assert [(s['key'], s['kind'], s['years'][0]['n']) for s in page['series']] == [('births', 'series', 10)]


def test_two_checks_of_one_kind_both_show(world):
    call_command('approve_topic', 'family', 'journeys/one', 'journeys/two', '--by', 'a reviewer')
    journeys = kit.load('family')['journeys']
    assert (journeys['one']['checked']['by'], journeys['two']['checked']['by']) == ('a reviewer', 'a reviewer')


def test_a_check_shows_in_its_own_process_while_the_shared_cache_is_down(world, settings, caplog):
    # Nothing listens on port 1: every read and write of the default cache fails, as with Redis down.
    settings.CACHES = {**settings.CACHES, 'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                                                      'LOCATION': 'redis://127.0.0.1:1/0'}}
    with caplog.at_level(logging.WARNING, logger=folders.log.name):
        assert kit.checks_version() == '-'
        call_command('approve_topic', 'family', 'journeys/one', '--by', 'a reviewer')
    assert ItemCheck.objects.get(topic='family', ref='journeys/one').by == 'a reviewer'
    assert kit.load('family')['journeys']['one']['checked']['by'] == 'a reviewer'
    assert [r.getMessage() for r in caplog.records] == ["topics: the checks' version could not be read",
                                                        "topics: the checks' version could not be changed",
                                                        "topics: the checks' version could not be read"]


def test_a_topic_without_a_folder_has_no_module_and_nothing_to_review(world, api, reviewer, capsys):
    # The health topic is in topics.json; here it has no folder of its own.
    assert api.get('/api/topics/health/').json()['module'] is None
    assert reviewer.get('/api/topics/health/review/').status_code == 404
    assert reviewer.post('/api/topics/health/review/', {'refs': ['journeys/one']}, format='json').status_code == 404
    # A folder is not a topic: only one topics.json lists is reviewed.
    (world / 'stray').mkdir()
    (world / 'stray' / 'hub.yaml').write_text(WORK_HUB, encoding='utf-8')
    assert reviewer.get('/api/topics/stray/review/').status_code == 404
    assert reviewer.post('/api/topics/stray/review/', {'refs': ['tools/held']}, format='json').status_code == 404
    assert reviewer.get('/api/topics/work/review/').json()['items'][0]['ref'] == 'journeys/trip'
    call_command('check_topic', 'health')
    assert capsys.readouterr().out.splitlines() == [
        "health: {'journeys': 0, 'checklists': 0, 'pages': 0, 'reform': 0, 'series': 0, 'rates': 0, 'cards': 0}, "
        '0 articles cited',
        '  health: no folder',
    ]
    assert not ItemCheck.objects.exists()
