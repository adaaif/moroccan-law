"""The digital topic (the digital review, 27 Oct 2026): its folder, its page drawn on a chat message, its one
question, its band, and the articles its tools on the phone rest on."""
import re
from pathlib import Path

import yaml
import pytest

from apps.topics.services import kit

# A topic is its folder's files and the checks a person recorded, which live in the database.
pytestmark = pytest.mark.django_db

JOURNEYS = ['extortion', 'hacked', 'scam', 'defamed', 'data-request', 'cndp', 'info-request', 'copyright', 'company']
ANSWERS = ['user', 'victim', 'business', 'creator', 'citizen', 'signer']
RULES = Path(__file__).resolve().parents[4] / 'web' / 'src' / 'topics' / 'digital' / 'rules'
READINGS = Path(__file__).resolve().parents[2] / 'quality' / 'data'


def test_the_folder_loads_its_journeys_lists_pages_and_changes():
    kit.load.cache_clear()
    c = kit.load('digital')
    assert list(c['journeys']) == JOURNEYS
    assert set(c['checklists']) == {'complaint', 'data-request', 'info-request', 'company-duties'}
    assert set(c['pages']) == {'data', 'offences', 'info', 'copyright', 'esign', 'company', 'beliefs'}
    assert set(c['reform']) == {'access-2019', 'cyber-2021', 'trust-2023', 'copyright-2026'}


def test_every_door_stands_in_a_stage_led_by_a_message(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('digital')
    assert h['marks'] == 'bubble'
    placed = [k for s in h['stages'] for k in s['doors']]
    assert sorted(placed) == sorted(d['key'] for d in h['events'])
    # The figure the law sets is in the message: access free, ten full days to correct, five years for extortion, six
    # months to complain of defamation, twenty working days for an answer, seventy years after the author.
    marks = {d['key']: d['mark']['value'] for d in h['events'] if d.get('mark')}
    assert (marks['access'], marks['rectify'], marks['extortion'], marks['defamed']) == ('0', '10', '5', '6')
    assert (marks['request'], marks['refused'], marks['protection']) == ('20', '60', '70')
    own = [d for d in h['events'] if ':' not in d['to']]
    assert all(d.get('mark') or d.get('icon') for d in own)


def test_one_question_six_answers_three_facts_each(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('digital')
    assert h['profile']['question']['ar'] == 'شنو كتدير فالأنترنت؟'
    options = h['profile']['options']
    assert [o['key'] for o in options] == ANSWERS
    for o in options:
        assert len(o['facts']) == 3 and all(f['cites'] for f in o['facts']), o['key']
        assert o['first'] in {d['key'] for d in h['events']}


def test_the_band_says_the_extortions_first_acts_opens_the_offences_and_shows_no_number(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    band = kit.hub('digital')['urgent']
    assert band['to'] == 'journeys/extortion' and band['tone'] == 'slate' and len(band['acts']) == 3
    assert band['tool'] == 'tools/offence' and band['tool_label']['ar']
    assert not band.get('numbers')


def test_the_journeys_count_only_the_limits_the_kit_can_count():
    # Defamation's six months from the publication (88.13 art. 101) and the ten full days to correct (09.08 art. 8) are
    # counted from the reader's day; 31.13's working days are the info tool's.
    kit.load.cache_clear()
    c = kit.load('digital')
    asked = {k for k, j in c['journeys'].items() if j.get('day')}
    assert asked == {'defamed', 'data-request'}
    for key in asked:
        assert any(s.get('delay', {}).get('on_day') for s in c['journeys'][key]['steps']), key
    rectify = next(s['delay'] for s in c['journeys']['data-request']['steps'] if s.get('delay'))
    assert rectify['days'] == 10 and rectify['complete']


def test_the_tools_on_the_phone_cite_only_articles_the_folder_cites():
    kit.load.cache_clear()
    cited = kit.cited(kit.load('digital'))
    found = {p for f in RULES.glob('*.ts') for p in re.findall(r"'(/ma/[a-z-]+/[0-9a-z-]+/art_[0-9a-z-]+)'", f.read_text())}
    assert found, 'the rules name their articles'
    assert found <= cited, sorted(found - cited)


def test_the_page_readings_name_their_texts():
    texts = {f.stem: yaml.safe_load(f.read_text())['text'] for f in READINGS.glob('digital_*.yaml')}
    assert texts == {
        'digital_copyright_2_00': '/ma/loi/2-00',
        'digital_doc_417_3': '/ma/code/doc',
        'digital_penal_1_59_413': '/ma/dahir/1-59-413',
        'digital_press_88_13': '/ma/loi/88-13',
    }
