"""The business topic (the business review, 27 Oct 2026): its folder, its page drawn on the company's stamp, its
one question, its band, and the articles its tools on the phone rest on."""
import re
from pathlib import Path

import pytest

from apps.topics.services import kit

# A topic is its folder's files and the checks a person recorded, which live in the database.
pytestmark = pytest.mark.django_db

JOURNEYS = ['auto-start', 'sarl-start', 'register', 'cooperative', 'cheque-bounced', 'cheque-written', 'late-payment',
            'difficulty', 'shop-sale']
ANSWERS = ['auto', 'trader', 'company', 'cooperative', 'supplier']
RULES = Path(__file__).resolve().parents[4] / 'web' / 'src' / 'topics' / 'business' / 'rules'


def test_the_folder_loads_its_journeys_lists_pages_and_changes():
    kit.load.cache_clear()
    c = kit.load('business')
    assert list(c['journeys']) == JOURNEYS
    assert set(c['checklists']) == {'auto-file', 'sarl-statutes', 'invoice', 'stop-file'}
    assert set(c['pages']) == {'forms', 'excluded', 'invoice', 'terms', 'cheque', 'markets', 'investment', 'beliefs'}
    assert set(c['reform']) == {'cheque-2026', 'terms-2023', 'companies-2024'}


def test_every_door_stands_in_a_stage_led_by_the_stamp(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('business')
    assert h['marks'] == 'cachet'
    placed = [k for s in h['stages'] for k in s['doors']]
    assert sorted(placed) == sorted(d['key'] for d in h['events'])
    # The figure the law sets is pressed in the stamp's middle: three months for the register, sixty days to pay, twenty
    # to present a cheque, thirty after a cessation of payments, 41 trades the auto-entrepreneur may not be.
    marks = {d['key']: d['mark']['value'] for d in h['events'] if d.get('mark')}
    assert (marks['register'], marks['terms'], marks['cheque-present'], marks['stop-paying']) == ('3', '60', '20', '30')
    assert (marks['auto-excluded'], marks['cooperative'], marks['markets']) == ('41', '5', '30%')
    own = [d for d in h['events'] if ':' not in d['to']]
    assert all(d.get('mark') or d.get('icon') for d in own)


def test_one_question_five_answers_three_facts_each(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('business')
    assert h['profile']['question']['ar'] == 'شنو كتدير؟'
    options = h['profile']['options']
    assert [o['key'] for o in options] == ANSWERS
    for o in options:
        assert len(o['facts']) == 3 and all(f['cites'] for f in o['facts']), o['key']
        assert o['first'] in {d['key'] for d in h['events']}


def test_the_band_says_the_bounced_cheques_first_acts_and_shows_no_number(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    band = kit.hub('business')['urgent']
    assert band['to'] == 'journeys/cheque-bounced' and band['tone'] == 'umber' and len(band['acts']) == 3
    assert not band.get('numbers')


def test_the_excluded_trades_are_the_decrees_forty_one():
    # The form tool checks a trade against decree 2.15.263's list; its rule holds the list as the decree prints it.
    listed = re.findall(r"^\s+'([^']+)',", (RULES / 'excluded.ts').read_text(), re.M)
    assert len(listed) == 41 == len(set(listed))


def test_the_tools_on_the_phone_cite_only_articles_the_folder_cites():
    # The form, the cheque, the late invoice and the company's year are worked out on the phone from rules that name
    # their articles; each one the folder cites too, so a reviewer's check of the folder covers them.
    kit.load.cache_clear()
    cited = kit.cited(kit.load('business'))
    found = {p for f in RULES.glob('*.ts') for p in re.findall(r"'(/ma/[a-z]+/[0-9a-z-]+/art_[0-9a-z-]+)'", f.read_text())}
    assert found, 'the rules name their articles'
    assert found <= cited, sorted(found - cited)
