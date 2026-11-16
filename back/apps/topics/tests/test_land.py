"""The land topic (the land review, 26 Oct 2026): its folder, its page, its band and the clock it leads to."""
import re
from pathlib import Path

import pytest

from apps.topics.services import kit

# A topic is its folder's files and the checks a person recorded, which live in the database.
pytestmark = pytest.mark.django_db

DOORS = ['buy', 'held', 'register', 'oppose', 'fraud', 'inherit', 'preempt', 'divide', 'build', 'nopermit', 'plan',
         'expropriation', 'collective']


def test_the_folder_loads_with_a_journey_for_every_door():
    kit.load.cache_clear()
    c = kit.load('land')
    assert list(c['journeys']) == DOORS
    assert set(c['checklists']) == {'before-buying', 'papers'}
    assert set(c['pages']) == {'beliefs', 'offices'}
    assert set(c['reform']) == {'sale-2026', 'subdivisions-2026', 'lf-2027'}


def test_every_door_is_drawn_as_its_plot_in_one_stage_of_a_plots_life(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('land')
    assert h['marks'] == 'plot'
    placed = [k for s in h['stages'] for k in s['doors']]
    assert sorted(placed) == sorted(d['key'] for d in h['events'])
    own = [d for d in h['events'] if not d['to'].startswith('housing:')]
    assert [d['key'] for d in own] == DOORS and all(d.get('plot') for d in own)
    # The number the law sets is written on the plot: two months to oppose, thirty days to pre-empt.
    marks = {d['key']: d['mark']['value'] for d in own if d.get('mark')}
    assert marks == {'held': '10', 'oppose': '2', 'fraud': '4', 'preempt': '30', 'build': '2', 'nopermit': '10.000',
                     'plan': '10', 'expropriation': '2', 'collective': '30'}


def test_one_question_with_three_facts_an_answer_and_the_laws_reason_for_a_fade(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('land')
    assert h['profile']['question']['ar'] == 'أرضك شنو هي؟'
    options = h['profile']['options']
    assert [o['key'] for o in options] == ['titled', 'pending', 'untitled', 'collective', 'unknown']
    for o in options:
        assert len(o['facts']) == 3 and all(f['cites'] for f in o['facts']), o['key']
    held = next(d for d in h['events'] if d['key'] == 'held')
    assert 'titled' not in held['for'] and '261' in held['not']['ar']


def test_the_band_lists_the_papers_that_start_a_clock_and_leads_to_it(settings):
    # M5, C1 «band»: in the soil's ink, each paper with its limit and its articles; the clock counts them.
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    band = kit.hub('land')['urgent']
    assert band['tone'] == 'soil' and band['to'] == 'tools/clock'
    assert [p['key'] for p in band['papers']] == ['oppose', 'inquiry', 'preempt', 'share']
    # Every paper the band names is one the clock counts (web/src/topics/land/rules/clock.ts).
    clock = (Path(settings.BASE_DIR).parent / 'web' / 'src' / 'topics' / 'land' / 'rules' / 'clock.ts').read_text(encoding='utf-8')
    counted = set(re.findall(r"^  '?([\w-]+)'?: L\('", clock, re.M))
    assert {p['key'] for p in band['papers']} <= counted


def test_the_clock_and_the_new_tools_wait_for_review(settings):
    # C3 «wait»: nothing of the land opens before a person's check.
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    tools = kit.hub('land')['tools']
    assert [t['key'] for t in tools] == ['clock', 'permit', 'before', 'find']
    assert not any(t.get('open') for t in tools)


def test_every_journey_ends_at_its_office_with_its_paper():
    kit.load.cache_clear()
    for key, j in kit.load('land')['journeys'].items():
        assert j['ends']['office'] in {'registry', 'commune', 'court', 'act', 'council'}, key
        assert j['ends']['paper']['ar'] and j['ends']['paper']['fr'], key


def test_a_question_in_peoples_words_opens_the_land_door(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    for q, path in [('شريت أرض بعقد عرفي', '/topics/land/journeys/buy'), ('أجل الشفعة', '/topics/land/journeys/preempt'),
                    ('الدولة بغات تاخذ ليا الأرض', '/topics/land/journeys/expropriation'),
                    ('رخصة البناء ما جاوبونيش', '/topics/land/journeys/build')]:
        found = kit.matching(q)
        assert found and found[0]['path'] == path, (q, found[:2])
