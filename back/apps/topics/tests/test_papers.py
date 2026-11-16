"""The papers topic (the papers review, 27 Oct 2026): its folder, its page drawn on the card, its one question, its
band, and the articles its tools on the phone rest on."""
import re
from pathlib import Path

import pytest

from apps.topics.services import kit

# A topic is its folder's files and the checks a person recorded, which live in the database.
pytestmark = pytest.mark.django_db

JOURNEYS = ['card-first', 'card-renew', 'card-lost', 'correct', 'name', 'abroad-marriage', 'spouse', 'appeal', 'record']
ANSWERS = ['morocco', 'abroad', 'foreigner']
RULES = Path(__file__).resolve().parents[4] / 'web' / 'src' / 'topics' / 'papers' / 'rules'


def test_the_folder_loads_its_journeys_lists_pages_and_changes():
    kit.load.cache_clear()
    c = kit.load('papers')
    assert list(c['journeys']) == JOURNEYS
    assert set(c['checklists']) == {'card-first', 'card-renew', 'card-marital', 'card-abroad'}
    assert set(c['pages']) == {'counter', 'copies', 'passport', 'nationality', 'card', 'legalize', 'data', 'foreigners',
                               'beliefs'}
    assert set(c['reform']) == {'passport-2026', 'naturalisation-2023', 'high-commission-2026'}


def test_every_door_stands_in_a_stage_led_by_the_card(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('papers')
    assert h['marks'] == 'card'
    placed = [k for s in h['stages'] for k in s['doors']]
    assert sorted(placed) == sorted(d['key'] for d in h['events'])
    # The figure the law sets is printed where the card's photo sits: the card at 16, valid ten years, seven cases to
    # renew it, fifteen days for a material error, sixty for the administration, thirty to appeal.
    marks = {d['key']: d['mark']['value'] for d in h['events'] if d.get('mark')}
    assert (marks['card-first'], marks['card-valid'], marks['card-renew']) == ('16', '10', '7')
    assert (marks['error'], marks['counter-wait'], marks['counter-refused'], marks['passport']) == ('15', '60', '30', '5')
    own = [d for d in h['events'] if ':' not in d['to']]
    assert all(d.get('mark') or d.get('icon') for d in own)


def test_one_question_three_answers_three_facts_each(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('papers')
    assert h['profile']['question']['ar'] == 'فين كتقضي الوراق ديالك؟'
    options = h['profile']['options']
    assert [o['key'] for o in options] == ANSWERS
    for o in options:
        assert len(o['facts']) == 3 and all(f['cites'] for f in o['facts']), o['key']
        assert o['first'] in {d['key'] for d in h['events']}


def test_the_band_says_the_lost_cards_first_acts_and_shows_no_number(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    band = kit.hub('papers')['urgent']
    assert band['to'] == 'journeys/card-lost' and band['tone'] == 'deep' and len(band['acts']) == 3
    assert not band.get('numbers')


def test_the_tools_on_the_phone_cite_only_articles_the_folder_cites():
    # The card, the clocks, the counter, the names and the rehabilitation are worked out on the phone from rules that
    # name their articles; each one the folder cites too, so a reviewer's check of the folder covers them.
    kit.load.cache_clear()
    cited = kit.cited(kit.load('papers'))
    found = {p for f in RULES.glob('*.ts') for p in re.findall(r"'(/ma/[a-z]+/[0-9a-z-]+/art_[0-9a-z-]+)'", f.read_text())}
    assert found, 'the rules name their articles'
    assert found <= cited, sorted(found - cited)
