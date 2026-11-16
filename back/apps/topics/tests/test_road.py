"""The road topic (the road plan, 20 Oct 2026)."""
import pytest

from apps.topics.management.commands.build_compensation_table import off_steps

# A topic is its folder's files and the checks a person recorded, which live in the database.
pytestmark = pytest.mark.django_db


def test_a_misprint_in_the_capital_table_is_named_with_what_the_steps_give():
    # Capitals fall by 1,000 a year of age and rise by 3,000 a step of earnings; one cell printed 10,000 too high.
    grid = {e: {a: 100_000 + 3 * e - 1_000 * a for a in range(30, 36)} for e in range(10_000, 16_000, 1_000)}
    grid[12_000][33] += 10_000
    assert off_steps(grid) == [{'earnings': 12_000, 'age': 33, 'printed': 113_000, 'steps': 103_000}]
    # A kink every row shares is the law's own, not a misprint.
    for e in grid:
        grid[e][31] += 2_000
    assert [m['age'] for m in off_steps(grid)] == [33]


def test_the_fines_the_tools_ship_are_the_newest_row_of_rates_yaml():
    # The fine tool carries its figures so it works offline at the roadside (F8 of the road tools review); this copy in
    # web/src/topics/road/rules/rates.ts must say what rates.yaml says, or a reader offline sees old prices.
    import re
    from pathlib import Path

    import yaml
    from django.conf import settings

    rates = yaml.safe_load((Path(__file__).resolve().parents[1] / 'road' / 'rates.yaml').read_text(encoding='utf-8'))
    newest = max(next(r for r in rates if r['key'] == 'fines')['rows'], key=lambda row: row['from'])
    shipped = (Path(settings.BASE_DIR).parent / 'web' / 'src' / 'topics' / 'road' / 'rules' / 'rates.ts').read_text(encoding='utf-8')
    assert re.search(r"FINES_FROM = '([\d-]+)'", shipped).group(1) == newest['from']
    body = re.search(r'FINES: Record<string, number> = \{(.*?)\};', shipped, re.S).group(1)
    copy = {k: int(v) for k, v in re.findall(r'(\w+): (\d+)', body)}
    assert copy == newest['values']


def test_the_road_page_has_its_emergency_its_path_and_its_question(settings):
    # T1, T4, T6 of the road tools review: the hub carries the red band's door, the learning path and the question.
    from apps.topics.services import kit
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('road')
    assert h['urgent']['to'] == 'tools/now'
    # Practice stays in the path with no written card: its sign deck is built from the signs' checked words (K2).
    assert [x['to'] for x in h['learn']] == ['tools/scenes', 'tools/signs', 'tools/practice', 'pages/rules']
    assert h['doors_title']['ar'] == 'شنو وقع ليك؟'
    assert all(d.get('icon') and d.get('sign') in {'tri', 'ring', 'disc', 'square'} for d in h['events'])


def test_the_red_band_says_its_first_acts_and_only_numbers_an_official_page_gives(settings):
    # A7 and C1 of the road-signposted review: the acts are the accident journey's own answers, in its order; a number
    # comes with the official page and the hash of the file kept.
    from apps.topics.services import kit
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    band = kit.hub('road')['urgent']
    steps = kit.load('road')['journeys']['accident']['steps']
    assert band['acts'] == [steps[i]['answer'] for i in (0, 2, 5)]
    assert all(n['source']['url'].startswith('https://') and len(n['source']['sha256']) == 64 for n in band['numbers'])


def test_what_changes_next_is_the_soonest_dated_entry_after_today_never_a_reform(settings):
    # A11: the card says the next date and what it brings; dates already past and a reform's record never count.
    from apps.topics.services import kit
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    content = kit.load('road')
    nxt = kit.upcoming(content, today='2026-10-26')
    assert [e['date'] for e in nxt] == ['2026-12-31', '2027-01-01']
    assert kit.upcoming(content, today='2027-02-24') == []
    assert [e['date'] for e in kit.upcoming(content, today='2027-01-01')] == ['2027-01-29', '2027-02-24']
    assert all(e['change'] != 'reform' for e in kit.upcoming(kit.load('family'), today='2000-01-01'))


def test_each_answer_of_the_question_says_its_figures_with_their_articles(settings):
    # A4: the answer's facts, each figure with the articles that set it, instead of a line of article numbers.
    from apps.topics.services import kit
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    for option in kit.hub('road')['profile']['options']:
        assert 2 <= len(option['facts']) <= 3, option['key']
        assert all(f['cites'] and all(c.startswith('/ma/') for c in f['cites']) for f in option['facts'])


def test_the_urgent_door_hides_when_what_it_leads_to_may_not_be_shown(settings):
    from apps.topics.services import kit
    settings.SHOW_DRAFTS = False
    kit.load.cache_clear()
    assert kit.hub('road')['urgent'] is None          # tools/now waits for a person's check


def test_a_question_in_peoples_words_opens_its_door_and_the_door_counts_for_the_goldset(settings):
    # X1, X3: «شدني الرادار» names the radar door; the radar journey cites the articles a goldset question expects.
    from apps.topics.services import kit
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    found = kit.matching('شدني الرادار')
    assert found and found[0]['path'] == '/topics/road/journeys/radar'
    assert found[0]['icon'] == 'radar' and found[0]['lead']
    assert '/ma/loi/52-05/art_222' in kit.door_cites('road', 'journeys/radar')


@pytest.mark.django_db
def test_the_reviewers_desk_is_for_staff_and_records_a_check_as_the_command_does(tmp_path, monkeypatch, settings):
    # R1, R2 of the road tools review: the desk reads every item with its articles' words; an approval records who,
    # when and the digests, in the database under the reviewer's account (a copy of the folder here, never written).
    import shutil
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.topics.services import kit
    from apps.topics.services.kit import folders
    copy = tmp_path / 'road'
    shutil.copytree(kit.folder('road'), copy)
    monkeypatch.setattr(folders, 'folder', lambda slug: copy if slug == 'road' else kit.BASE / slug)
    kit.load.cache_clear()
    client = APIClient()
    assert client.get('/api/topics/road/review/').status_code == 401
    user = get_user_model().objects.create_user(username='reader', email='r@example.org', password='a long pass 12')
    client.force_authenticate(user)
    assert client.get('/api/topics/road/review/').status_code == 403
    user.is_staff = True
    user.save()
    assert client.get('/api/topics/road/review/').status_code == 403         # staff alone is no reviewer
    from django.contrib.auth.models import Permission
    user.user_permissions.add(Permission.objects.get(codename='review_topic'))
    client.force_authenticate(get_user_model().objects.get(pk=user.pk))     # its rights read afresh
    desk = client.get('/api/topics/road/review/').json()
    radar = next(i for i in desk['items'] if i['ref'] == 'journeys/radar')
    assert radar['wave'] == 1 and radar['state'] == 'draft'
    assert any(p in desk['bodies'] for p in ['/ma/loi/52-05/art_219', '/ma/loi/52-05/art_222']) or not desk['bodies']
    r = client.post('/api/topics/road/review/', {'refs': ['journeys/radar', 'tools/fine']}, format='json')
    assert r.status_code == 200 and r.json()['checked']['tools/fine']['by'] == 'reader'
    from apps.topics.models import ItemCheck
    written = ItemCheck.objects.get(topic='road', ref='journeys/radar')
    assert (written.by, written.user_id) == ('reader', user.pk) and not (copy / 'checked.yaml').exists()
    kit.load.cache_clear()


@pytest.mark.django_db
def test_a_tool_use_is_counted_by_day_page_and_event_and_never_carries_an_input():
    # M1 of the road tools review.
    from rest_framework.test import APIClient
    from apps.topics.models import ToolUse
    api = APIClient()
    for _ in range(3):
        assert api.post('/api/topics/use/', {'path': '/topics/road/tools/fine', 'event': 'open'}, format='json').status_code == 204
    assert ToolUse.objects.get(path='/topics/road/tools/fine', event='open').count == 3
    assert api.post('/api/topics/use/', {'path': '/topics/road/tools/fine?o=phone&d=2026-10-20', 'event': 'open'}, format='json').status_code == 400
    assert api.post('/api/topics/use/', {'path': '/topics/road/tools/fine', 'event': 'speed=84'}, format='json').status_code == 400
