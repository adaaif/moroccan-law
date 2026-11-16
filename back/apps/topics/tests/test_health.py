"""The health topic (the health review, 27 Oct 2026): its folder, its page, its band, the rates its refund tool
reads and the long-illness list its finder reads."""
import re
from pathlib import Path

import pytest

from apps.topics.services import kit

# A topic is its folder's files and the checks a person recorded, which live in the database.
pytestmark = pytest.mark.django_db

JOURNEYS = ['emergency', 'refund', 'refused', 'clinic', 'long-illness', 'tadamon-lost', 'record', 'sick', 'error', 'death',
            'self']
ANSWERS = ['private', 'cnops', 'tadamon', 'self', 'achamil', 'student', 'unknown']


def test_the_folder_loads_its_journeys_pages_changes_and_rates():
    kit.load.cache_clear()
    c = kit.load('health')
    assert list(c['journeys']) == JOURNEYS
    assert set(c['pages']) == {'rights', 'regimes', 'tadamon', 'hospital', 'medicines', 'birth', 'beliefs', 'donation',
                               'disability', 'illnesses'}
    assert set(c['reform']) == {'cnops-2027', 'medicine-prices-2026', 'pharmacy-2026', 'lf-2027'}
    assert set(c['rates']) == {'refund-cnss', 'refund-cnops'}


def test_every_door_stands_in_a_stage_led_by_its_vignette(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('health')
    assert h['marks'] == 'vignette'
    placed = [k for s in h['stages'] for k in s['doors']]
    assert sorted(placed) == sorted(d['key'] for d in h['events'])
    # The figure the law sets is printed on the label: two months to file, no cheque, a year to contest.
    marks = {d['key']: d['mark']['value'] for d in h['events'] if d.get('mark')}
    assert marks['refund'] == '2' and marks['cheque'] == '0' and marks['refused'] == '1' and marks['sick'] == '48'
    own = [d for d in h['events'] if ':' not in d['to']]
    assert all(d.get('mark') or d.get('icon') for d in own)


def test_one_question_seven_answers_three_facts_each(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('health')
    assert h['profile']['question']['ar'] == 'شنو التغطية ديالك؟'
    options = h['profile']['options']
    assert [o['key'] for o in options] == ANSWERS
    for o in options:
        assert len(o['facts']) == 3 and all(f['cites'] for f in o['facts']), o['key']


def test_the_band_says_the_emergency_journeys_acts_and_only_a_sourced_number(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    band = kit.hub('health')['urgent']
    assert band['to'] == 'journeys/emergency' and len(band['acts']) == 3
    # C2 «sourced»: the SAMU's 141 with the ministry's page and its hash; nothing without one.
    assert [n['number'] for n in band['numbers']] == ['141']
    assert all(n['source']['url'].startswith('https://www.sante.gov.ma/') and len(n['source']['sha256']) == 64 for n in band['numbers'])


def test_the_refund_rates_are_the_decrees_and_the_tool_reads_the_same_keys(settings):
    kit.load.cache_clear()
    rates = kit.load('health')['rates']
    cnss = rates['refund-cnss']['rows'][0]['values']
    cnops = rates['refund-cnops']['rows'][0]['values']
    assert (cnss['care'], cnss['long_public']) == (70, 90)                    # decree 2.05.737, art. 2
    assert (cnops['care'], cnops['public_hospital'], cnops['share_cap']) == (80, 100, 10)   # decree 2.05.736, arts 1–2
    tool = (Path(settings.BASE_DIR).parent / 'web' / 'src' / 'topics' / 'health' / 'rules' / 'refund.ts').read_text(encoding='utf-8')
    keys = set(re.search(r'export type Rates = \{([^}]*)\}', tool).group(1).replace(':', ' ').replace(';', ' ').split()) - {'number'}
    assert keys == set(cnss) == set(cnops)


def test_the_long_illness_list_has_its_41_rows_in_both_languages():
    kit.load.cache_clear()
    page = kit.load('health')['pages']['illnesses']
    rows = next(s['table']['rows'] for s in page['sections'] if s.get('table'))
    assert [int(r[0]) for r in rows] == list(range(1, 42))
    assert all(r[1] and r[2] for r in rows)
