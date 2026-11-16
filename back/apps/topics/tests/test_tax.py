"""The tax topic (the tax review, 26 Oct 2026): its folder, its page, its band and the figures the tools read."""
import pytest

from apps.topics.services import kit

# A topic is its folder's files and the checks a person recorded, which live in the database.
pytestmark = pytest.mark.django_db

DOORS = ['bill2027', 'salary', 'children', 'pension', 'rent', 'declare', 'savings', 'housing', 'land', 'car', 'sell', 'buy', 'gift', 'own',
         'late', 'notice', 'abroad', 'company']


def test_the_folder_loads():
    kit.load.cache_clear()
    c = kit.load('tax')
    assert set(c['journeys']) == {'declare', 'sell', 'rent-out', 'notice', 'own'}
    assert set(c['pages']) == {'map', 'beliefs', 'calendar', 'savings', 'gift', 'abroad', 'business',
                               'bill-2027', 'bill-amendments', 'bill-claims', 'allowances-2031', 'fifa-2030', 'bill-press'}
    assert set(c['reform']) == {'lf-2027', 'lf-2026', 'lf-2025', 'announced-pensions', 'announced-electricity',
                                'announced-support'}
    assert set(c['rates']) == {'scale', 'family', 'expenses', 'pension', 'rent', 'property', 'registration', 'car', 'own',
                               'late', 'local', 'bill-scale', 'bill-expenses'}


def test_every_door_on_a_fiscal_stamp_in_one_stage_and_doors_may_open_a_tool(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    h = kit.hub('tax')
    assert h['marks'] == 'stamp'
    assert [d['key'] for d in h['events']] == DOORS
    placed = [k for s in h['stages'] for k in s['doors']]
    assert sorted(placed) == sorted(DOORS)
    # A door straight to a tool is kept once the tool is shown (the salary's).
    assert next(d for d in h['events'] if d['key'] == 'salary')['to'] == 'tools/salary'
    assert {t['key'] for t in h['tools']} == {'bill', 'salary', 'local', 'car', 'pension', 'rent', 'sell', 'buy', 'own', 'late'}


def test_one_question_seven_answers_three_facts_each_on_their_articles(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    p = kit.hub('tax')['profile']
    assert [o['key'] for o in p['options']] == ['salary', 'pension', 'rent', 'property', 'self', 'abroad', 'company']
    for o in p['options']:
        assert len(o['facts']) == 3
        assert all(c.startswith(('/ma/code/cgi/', '/ma/loi/47-06/')) for f in o['facts'] for c in f['cites'])


def test_the_band_holds_the_years_dates_in_ochre(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    u = kit.hub('tax')['urgent']
    assert u['tone'] == 'ochre'
    assert {d['key'] for d in u['dates']} == {'car', 'income', 'land', 'professional', 'quarter'}
    assert next(d for d in u['dates'] if d['key'] == 'income')['before'] == '03-01'


def test_the_scale_and_the_family_deduction_by_year():
    kit.load.cache_clear()
    rates = kit.load('tax')['rates']
    scale = rates['scale']['rows']
    assert scale[0]['from'] == '2025-01-01' and scale[0]['values']['s1'] == 40000 and scale[0]['values']['r5'] == 37
    family = {r['from']: r['values'] for r in rates['family']['rows']}
    assert family['2025-01-01'] == {'per': 500, 'max': 3000}
    assert family['2026-01-01'] == {'per': 600, 'max': 3600}
    pension = {r['from']: r['values'] for r in rates['pension']['rows']}
    assert pension['2025-01-01']['basic_reduction'] == 50 and pension['2026-01-01']['basic_exempt'] == 1


def test_the_bills_figures_are_never_read_as_law():
    # The finance-bill review, P6: the bill's scales stand in their own tables, every row `proposed`; the scale the tools
    # read as law keeps no row from the bill.
    kit.load.cache_clear()
    rates = kit.load('tax')['rates']
    assert all(r.get('proposed') == '/ma/projet-loi/60-26' for k in ('bill-scale', 'bill-expenses') for r in rates[k]['rows'])
    assert not any(r.get('proposed') for r in rates['scale']['rows'] + rates['expenses']['rows'])
    assert [r['from'][:4] for r in rates['bill-scale']['rows']] == ['2027', '2028', '2029', '2030', '2031']


def test_the_bill_page_is_data_the_page_can_draw():
    # The bill-page review (V3): each change a row with the bill's figure, today's or the reason there is none, and
    # its date or the words for it; a calendar naming the sections; each claim a neutral marker and the text's figure.
    kit.load.cache_clear()
    pages = kit.load('tax')['pages']
    bill = pages['bill-2027']
    assert bill['layout'] == 'changes' and bill['reform'] == 'lf-2027'
    keys = [s['key'] for s in bill['sections']]
    assert keys[0] == 'salary'    # C1: the salaried section first
    for s in bill['sections']:
        assert s['chip'] and s['line'] and s['rows']
        for r in s['rows']:
            assert r['headline'] and r['then']
            assert 'now' in r or r.get('announced') or r.get('new'), r['headline']
            assert r.get('from') or r.get('when') or r.get('announced') or r.get('same'), r['headline']
    assert all(set(c['for']) <= set(keys) for c in bill['calendar'])
    claims = pages['bill-claims']
    assert claims['layout'] == 'claims'
    assert all(c['mark'] in {'as', 'if', 'later', 'not', 'other'} and c['figure'] for c in claims['sections'])


def test_the_chambers_votes_add_up_and_each_is_on_the_record():
    # The Chamber-vote update (15 Nov 2026): a vote is the record's count, with the kept page that gives it; the
    # hemicycle is drawn from the Chamber's own number of seats (organic law 27.11, art. 1), so a count never exceeds it.
    import re
    kit.load.cache_clear()
    bill = kit.load('tax')['reform']['lf-2027']
    assert bill['stage'] == 'bill' and bill['at'] in {s['key'] for s in bill['stages']}
    votes = {v['key']: v for v in bill['votes']}
    assert set(votes) == {'plenary', 'committee'}
    for v in votes.values():
        assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', v['date']) and v['body']['ar'] and v['body']['fr']
        assert all(isinstance(v[k], int) and v[k] >= 0 for k in ('for', 'against', 'abstain'))
        assert v['source']['file'] and re.fullmatch(r'[0-9a-f]{64}', v['source']['sha256'])
    plenary = votes['plenary']
    assert plenary['seats'] == 395 and plenary['cites'] == ['/ma/loi-organique/27-11/art_1']
    assert plenary['for'] + plenary['against'] + plenary['abstain'] <= plenary['seats']
    assert plenary['for'] > plenary['against'] and plenary['headline']['ar'] and plenary['note']['ar']
    # The votes are in the dated record too, and the stop the bill has reached comes after them.
    assert {votes['committee']['date'], plenary['date']} <= {e['date'] for e in bill['timeline']}
    assert [s['key'] for s in bill['stages']].index(bill['at']) >= 3


def test_the_committees_amendments_are_its_own_table():
    # The committee's count, group by group (its report, second part, p. 6): what a group filed is what was taken,
    # rejected and withdrawn; the groups add up to the totals the page says.
    kit.load.cache_clear()
    am = kit.load('tax')['reform']['lf-2027']['amendments']
    for g in am['groups']:
        assert g['side'] in {'government', 'majority', 'opposition'} and g['label']['ar'] and g['label']['fr']
        assert g['accepted'] + g['rejected'] + g['withdrawn'] == g['filed'], g['key']
    assert sum(g['filed'] for g in am['groups']) == am['filed'] == 287
    assert sum(g['accepted'] for g in am['groups']) == am['accepted'] == 59
    assert am['source']['file'] and am['page'] == 'pages/bill-amendments' and am['link']['ar']
    assert 'bill-amendments' in kit.load('tax')['pages']


AMENDED_BY = {'government', 'majority', 'committee', 'rni', 'pjd', 'mp', 'left', 'groups'}


def _amendment(row: dict) -> dict | None:
    """A row's amendment, checked: who filed it, its vote as three counts or unanimous, its page in the report."""
    assert not (row.get('amended') and row.get('refused')), row['headline']
    a = row.get('amended') or row.get('refused')
    if a:
        assert a['by'] in AMENDED_BY and isinstance(a['page'], int) and 1 <= a['page'] <= 860, row['headline']
        vote = a.get('vote')
        if a.get('withdrawn'):
            assert vote is None and row.get('refused'), row['headline']
        elif row.get('refused') and a['by'] == 'groups':
            assert vote is None and row.get('detail'), row['headline']    # several proposals: each vote in the detail
        else:
            assert vote == 'unanimous' or (isinstance(vote, list) and len(vote) == 3
                                           and all(isinstance(n, int) and n >= 0 for n in vote) and sum(vote) <= 44), row['headline']
    # The figure as filed is shown only beside an amendment: struck through where the deputies changed it, standing
    # («فالمشروع») where they refused to.
    assert not row.get('filed') or a, row['headline']
    return a


def test_what_the_deputies_changed_says_who_how_and_where():
    # A line Parliament amended names the amendment behind it; the page cites the committee's report, kept with its hash.
    import re
    kit.load.cache_clear()
    pages = kit.load('tax')['pages']
    bill = pages['bill-2027']
    assert bill['chamber'] == 'vote' and bill['report']['url'].endswith('.pdf')
    assert re.fullmatch(r'[0-9a-f]{64}', bill['report']['sha256']) and bill['report']['file']
    amended = [r for s in bill['sections'] for r in s['rows'] if _amendment(r)]
    assert len(amended) >= 12 and not any(r.get('refused') for r in amended)
    # The deputies left the salary scale as filed: no figure of the salaried reader's first rows is struck through.
    salary = bill['sections'][0]
    assert salary['note']['ar'] and not any(r.get('filed') for r in salary['rows'])
    # The same change says the same thing in the other topics' own lines.
    stamp = next(r for s in bill['sections'] for r in s['rows'] if '/ma/code/cgi/art_252' in (r.get('cites') or []))
    assert (stamp['then'], stamp['filed'], stamp['now']) == ('25%', '24%', '20%')
    assert '25%' in kit.load('road')['reform']['lf-2027']['line']['ar']


def test_the_amendments_page_is_every_change_and_every_refusal():
    # pages/bill-amendments: the committee's amendments in plain words, by reader, then what it did not take. Every row
    # is an amendment (taken or refused); a refused one is a proposal, so it has no date of effect.
    kit.load.cache_clear()
    pages = kit.load('tax')['pages']
    page = pages['bill-amendments']
    assert page['layout'] == 'changes' and page['chamber'] == 'amendments' and page['reform'] == 'lf-2027'
    assert page['report'] == pages['bill-2027']['report'] and page['bill'] == '/ma/projet-loi/60-26'
    keys = [s['key'] for s in page['sections']]
    assert keys[-1] == 'refused' and len(keys) == len(set(keys))
    for s in page['sections']:
        assert s['chip']['ar'] and s['chip']['fr'] and s['title']['ar'] and s['line']['ar'] and s['rows']
        for r in s['rows']:
            assert r['headline']['ar'] and r['headline']['fr'] and r['then']
            assert 'now' in r or r.get('new') or r.get('filed'), r['headline']    # a budget line has no «today»
            a = _amendment(r)
            assert a, r['headline']
            if s['key'] == 'refused':
                assert r.get('refused') and not r.get('from'), r['headline']
            else:
                assert r.get('amended') and (r.get('from') or r.get('when')), r['headline']


def test_what_people_say_is_linked_dated_and_kept():
    # The bill-story review, Y8–Y11: each item typed, dated, its headline as printed, linked, one sentence of ours
    # (or attributed quotes), a proposal said as one; a kept copy names its hash; the claims point at items that exist.
    import re
    kit.load.cache_clear()
    pages = kit.load('tax')['pages']
    items = pages['bill-press']['items']
    assert pages['bill-press']['layout'] == 'press'
    for i in items:
        assert i['type'] in {'government', 'parliament', 'unions', 'employers', 'experts', 'press'}
        assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', i['date']) and i['url'].startswith('https://') and i['title']
        assert i.get('said') or i.get('quotes'), i['key']
        # Every item's private copy kept, with its hash (docs/rules.md, «What people say is linked, never the law»).
        assert i.get('file') and re.fullmatch(r'[0-9a-f]{64}', i.get('sha256') or ''), i['key']
    keys = {i['key'] for i in items}
    assert all(set(c.get('repeated') or []) <= keys for c in pages['bill-claims']['sections'])
    assert any(q.get('proposal') for i in items for q in i.get('quotes') or [])


# The verbs our reported speech opens with, as the page's Darija says them: «كيقول بلي», «كتتسائل واش», …
REPORTING = ('كيقول', 'كتقول', 'كيشوف', 'كيقترح', 'كيطالب', 'كيتسائل', 'كتتسائل', 'كيكتب', 'كيقدّر', 'كيدافع',
             'كيذكّر', 'كيبيّن', 'كيسمي', 'كتوصف')


def test_what_a_person_said_is_reported_never_put_in_their_mouth():
    # Our sentences about what someone said are in the page's own Darija, which none of them spoke or wrote: drawn as
    # «Name: sentence» they read as the person's words. Each is reported speech, «X، كيقول بلي …», «X, estime que …».
    kit.load.cache_clear()
    quotes = [q for i in kit.load('tax')['pages']['bill-press']['items'] for q in i.get('quotes') or []]
    assert len(quotes) == 28    # ten more on 15 Nov 2026, the week the Chamber voted
    for q in quotes:
        assert 'said' not in q and q['says']['ar'].startswith(REPORTING), q['says']['ar']
        assert q['says']['fr'][0].islower(), q['says']['fr']


def test_the_page_that_grades_what_was_said_stays_a_draft_until_a_person_reads_it(settings):
    # It weighs a named minister's figures against the text: a person reads each claim against its page first.
    kit.load.cache_clear()
    claims = kit.load('tax')['pages']['bill-claims']
    assert not claims.get('open') and not claims.get('checked')
    settings.SHOW_DRAFTS = True
    assert kit.page('tax', 'pages', 'bill-claims')['state'] == 'draft'
    settings.SHOW_DRAFTS = False
    assert kit.page('tax', 'pages', 'bill-claims') is None
