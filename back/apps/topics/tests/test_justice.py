"""The justice topic (the justice review, 27 Oct 2026): its folder, its page drawn on the court file, its one
question, its band, and the articles its tools on the phone rest on."""
import re
from pathlib import Path

import yaml
import pytest

from apps.consolidation.services import sgg
from apps.topics.services import kit

# A topic is its folder's files and the checks a person recorded, which live in the database.
pytestmark = pytest.mark.django_db

JOURNEYS = ['custody', 'complaint', 'trial', 'lawsuit', 'small-claim', 'payment-order', 'appeal', 'enforce', 'aid', 'lawyer']
ANSWERS = ['family', 'victim', 'accused', 'claimant', 'defendant', 'judgment']
RULES = Path(__file__).resolve().parents[4] / 'web' / 'src' / 'topics' / 'justice' / 'rules'


def test_the_folder_loads_its_journeys_lists_pages_and_changes():
    kit.load.cache_clear()
    c = kit.load('justice')
    assert list(c['journeys']) == JOURNEYS
    assert set(c['checklists']) == {'custody-rights', 'claim', 'appeal', 'aid-file'}
    assert set(c['pages']) == {'courts', 'deadlines', 'lawyer', 'aid', 'alternatives', 'prison', 'coercion', 'beliefs'}
    assert set(c['reform']) == {'civil-2026', 'criminal-2025', 'alternatives-2025', 'lawyers-2026', 'bailiffs-2025'}


def test_every_door_stands_in_a_stage_led_by_the_court_file(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('justice')
    assert h['marks'] == 'file'
    placed = [k for s in h['stages'] for k in s['doors']]
    assert sorted(placed) == sorted(d['key'] for d in h['events'])
    # The figure the law sets is on the file's cover: 48 hours of custody, 5,000 DH for the proximity judge, 30 days to
    # appeal a civil judgment and 10 a correctional one, 5 years for an alternative sentence.
    marks = {d['key']: d['mark']['value'] for d in h['events'] if d.get('mark')}
    assert (marks['custody'], marks['small'], marks['appeal-civil'], marks['appeal-criminal']) == ('48', '5.000', '30', '10')
    assert (marks['alternative'], marks['coercion'], marks['final']) == ('5', '8.000', '10.000')
    own = [d for d in h['events'] if ':' not in d['to']]
    assert all(d.get('mark') or d.get('icon') for d in own)


def test_one_question_six_answers_three_facts_each(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('justice')
    assert h['profile']['question']['ar'] == 'فين واقف فالقضية؟'
    options = h['profile']['options']
    assert [o['key'] for o in options] == ANSWERS
    for o in options:
        assert len(o['facts']) == 3 and all(f['cites'] for f in o['facts']), o['key']
        assert o['first'] in {d['key'] for d in h['events']}


def test_the_band_says_the_custodys_first_acts_opens_its_clock_and_shows_no_number(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    band = kit.hub('justice')['urgent']
    assert band['to'] == 'journeys/custody' and band['tone'] == 'indigo' and len(band['acts']) == 3
    assert band['tool'] == 'tools/custody' and band['tool_label']['ar']
    assert not band.get('numbers')


def test_a_courts_limits_are_complete_in_the_journeys():
    # Every limit counted in days from a notification or a judgment is a court's: complete (58.25 art. 602, 22.01 art. 750).
    kit.load.cache_clear()
    c = kit.load('justice')
    for key in ['trial', 'appeal', 'payment-order']:
        delays = [s['delay'] for s in c['journeys'][key]['steps'] if s.get('delay', {}).get('on_day')]
        assert delays and all(d.get('complete') for d in delays), key


def test_the_penal_codes_alternative_sentences_are_cut_out_of_art_35():
    # Adala's copy runs arts 35-1 to 35-15 into art. 35; page_tables.yaml cuts them out at every load, last first.
    entries = [e for e in sgg.page_entries('adala_89') if str(e['article']).startswith('35-')]
    assert [e['article'] for e in entries] == [f'35-{n}' for n in range(15, 0, -1)]
    assert all(e['after'] == '35' and e['headings'][2].startswith('الباب الأول المكرر') for e in entries)
    six = next(e for e in entries if e['article'] == '35-6')
    assert 'بين 40 و3600 ساعة' in six['table'] and 'لثلاث ساعات من العمل' in six['table']


def test_the_tools_on_the_phone_cite_only_articles_the_folder_cites():
    # The deadlines, the custody clock, the courts and the alternatives are worked out on the phone from rules that name
    # their articles; each one the folder cites too, so a reviewer's check of the folder covers them.
    kit.load.cache_clear()
    cited = kit.cited(kit.load('justice'))
    found = {p for f in RULES.glob('*.ts') for p in re.findall(r"'(/ma/[a-z-]+/[0-9a-z-]+/art_[0-9a-z-]+)'", f.read_text())}
    assert found, 'the rules name their articles'
    assert found <= cited, sorted(found - cited)


def test_the_legal_aid_reading_names_its_text():
    page = yaml.safe_load((Path(__file__).resolve().parents[2] / 'quality' / 'data' / 'justice_legal_aid_514_65.yaml').read_text())
    assert page['text'] == '/ma/decret-loi/514-65' and len(page['fixes']) == 7
