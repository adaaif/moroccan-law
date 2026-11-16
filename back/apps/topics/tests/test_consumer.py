"""The consumer topic (the consumer plan, 24 Oct 2026): its folder, its shipped figures, its page, its words."""
import re
from pathlib import Path

import yaml
from django.conf import settings
import pytest

from apps.topics.services import kit

# A topic is its folder's files and the checks a person recorded, which live in the database.
pytestmark = pytest.mark.django_db

FOLDER = Path(__file__).resolve().parents[1] / 'consumer'


def test_the_folder_loads_with_its_journeys_pages_papers_changes_and_rates():
    kit.load.cache_clear()
    c = kit.load('consumer')
    assert set(c['journeys']) == {'online', 'defect', 'late', 'door', 'credit', 'home-loan', 'subscription', 'clause', 'prices'}
    assert set(c['pages']) == {'beliefs', 'where', 'bills', 'bank', 'safety', 'numbers'}
    assert set(c['series']) == {'bank-complaints', 'mediation'}
    assert set(c['checklists']) == {'invoice', 'offer'}
    assert 'sugar' in c['rates'] and len(c['reform']) == 6    # with the 2027 bill's line


def test_every_period_a_journey_counts_is_a_full_one_from_the_next_day():
    # Art. 203: the periods of law 31.08 are full ones; a step's limit says it starts the day after its event.
    c = kit.load('consumer')
    for j in c['journeys'].values():
        for step in j['steps']:
            if step.get('delay') and step['delay'].get('on_day'):
                assert 'الموالي' in step['delay']['from']['ar'], j['key']


def test_the_sugar_prices_the_tool_ships_are_rates_yaml_s():
    # T7 works offline from a copy (web/src/topics/consumer/rules/sugar.ts); it must say what rates.yaml says.
    rates = yaml.safe_load((FOLDER / 'rates.yaml').read_text(encoding='utf-8'))
    rows = next(r for r in rates if r['key'] == 'sugar')['rows']
    shipped = (Path(settings.BASE_DIR).parent / 'web' / 'src' / 'topics' / 'consumer' / 'rules' / 'sugar.ts').read_text(encoding='utf-8')
    body = re.search(r'export const SUGAR: RateRow\[\] = \[(.*?)\n\];', shipped, re.S).group(1)
    copied = re.findall(r"\{ from: '([\d-]+)'(?:, to: '[\d-]+')?, values: \{(.*?)\} \}", body, re.S)
    assert [f for f, _ in copied] == [r['from'] for r in rows]
    for (_, values), row in zip(copied, rows):
        copy = {k: float(v) for k, v in re.findall(r'(\w+): ([\d.]+)', values)}
        assert copy == {k: float(v) for k, v in row['values'].items()}


def test_the_page_asks_how_one_bought_and_shows_the_beliefs(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('consumer')
    assert h['profile']['question']['ar'] == 'كيفاش شريتي؟'
    assert [o['key'] for o in h['profile']['options'] if o.get('main')] == ['shop', 'online', 'door', 'credit']
    assert len(h['beliefs']) == 5 and all(b['to'] == 'pages/beliefs' for b in h['beliefs'])
    assert all(d.get('icon') for d in h['events'] + h['tools'])
    # Only the two tools opened before review (K5) are open; the rest wait for a person's check.
    assert {t['key'] for t in h['tools'] if t.get('open')} == {'return', 'guarantee'}


def test_a_question_in_peoples_words_opens_the_consumer_door(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    found = [f for f in kit.matching('كتبو ليا لا ترد ولا تستبدل') if f['topic'] == 'consumer']
    assert found and found[0]['path'] == '/topics/consumer/pages/beliefs'
    found = [f for f in kit.matching('بغيت نرجع السلعة اللي طلبت أونلاين') if f['topic'] == 'consumer']
    assert found and found[0]['path'] == '/topics/consumer/journeys/online'


def test_every_door_has_one_stage_in_the_life_of_a_purchase(settings):
    # The consumer-receipt review: the doors laid out before, paying, after, when it goes wrong and elsewhere, each
    # once, none folded; the other topics' doors only in the stage of links.
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('consumer')
    assert h['marks'] == 'tag'
    placed = [k for s in h['stages'] for k in s['doors']]
    assert sorted(placed) == sorted(d['key'] for d in h['events'])
    assert [s['key'] for s in h['stages'] if s.get('links')] == ['elsewhere']
    online = next(d for d in h['events'] if d['key'] == 'online')
    assert online['mark']['value'] == '7' and online['mark']['unit']['ar'] == 'أيام'


def test_an_answer_says_three_figures_each_with_its_articles(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    options = [o for o in kit.hub('consumer')['profile']['options'] if o.get('facts')]
    assert {o['key'] for o in options} >= {'shop', 'online', 'door', 'credit'}
    for o in options:
        assert len(o['facts']) == 3, o['key']
        # A figure the same in both languages («4%») is one string.
        assert all(f['value'] and f['label']['ar'] and f['label']['fr'] and f['cites'] for f in o['facts']), o['key']


def test_the_receipt_waits_for_review_and_every_journey_ends_on_its_paper(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    tools = kit.hub('consumer')['tools']
    assert tools[0]['key'] == 'receipt' and not tools[0].get('open')
    for key, j in kit.load('consumer')['journeys'].items():
        assert j['ends']['paper']['ar'] and j['ends']['paper']['fr'] and j['ends']['cites'], key
