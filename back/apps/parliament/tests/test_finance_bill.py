"""A finance bill as filed (the finance-bill review, P1, P2): its articles cut from the government's file, the
dates its tax changes would apply, and its proposals kept apart from the law — never an article's history, never a
standing."""
from datetime import date

import pytest

from apps.consolidation.models import Change
from apps.consolidation.services import engine, history
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.parliament.services import finance_bill

CGI = '/akn/ma/act/code/cgi'
BILL = '/akn/ma/act/projet-loi/60-26'


def test_the_cut_follows_the_bills_numbering_and_joins_a_quoted_passages_lines():
    pages = [[
        'مشروع قانون المالية رقم 60.26', '- 2 -',
        'الجزء الأول',
        'المادة الأولى',
        'تستمر الجهات المختصة في القيام خلال السنة المالية 2027 بما يلي :',
        'المادة 2',
        'تغير أحكام المادة 7 من القانون المشار إليه أعلاه',
        'المادة 7',                       # a reference alone on its line, not the next number: never a heading
        'كما يلي :',
        '«المادة 6.- الإعفاءات',
        '«37° - صندوق الإرث المشار إليه في المادة 247 المكررة أربع مرات',
        '«أدناه، برسم مجموع أنشطته.',
        'المادة 3',
        'تحدث مناصب مالية.',
    ]]
    arts = finance_bill.cut(pages, finance_bill.AR_HEAD, finance_bill.AR_DIVISION)
    assert [a.number for a in arts] == ['1', '2', '3']
    assert arts[0].heading_path == ['الجزء الأول']
    assert '«37° - صندوق الإرث المشار إليه في المادة 247 المكررة أربع مرات أدناه، برسم مجموع أنشطته.' in arts[1].lines
    assert '«المادة 6.- الإعفاءات' in arts[1].lines


def test_the_dates_of_effect_give_each_code_article_its_day():
    body = ('IV.- Dates d’effet\n'
            '1 – Les dispositions de l’article 82-I du code général des impôts, relatives à l’avance, sont applicables '
            'aux opérations d’importation réalisées à compter du 1er juillet 2027.\n'
            '5 – Les dispositions de l’article 59-I du code général des impôts, telles que modifiées, sont applicables '
            'aux revenus acquis à compter du 1er janvier 2027.\n'
            '9 – Les dispositions des articles 57-1° et 73-I du code général des impôts sont applicables aux revenus '
            'acquis à compter du 1er janvier 2031.')
    got = finance_bill.dates_of_effect(body)
    assert got['82'][0] == '2027-07-01' and got['59'][0] == '2027-01-01'
    assert got['82'][2] and not got['59'][2]    # only the advance is dated so: the article's other changes are not
    assert got['57'][0] == got['73'][0] == '2031-01-01'


def test_the_lead_names_the_code_articles_changed_and_added():
    body = ('I.- Les dispositions des articles 6, 9-II, 73 et 161 bis du code général des impôts … sont modifiées. '
            'II.- Le code est complété par les articles 125 sexies, 247 quater et 247 quinquies comme suit')
    assert finance_bill.code_articles(body) == {'6', '9', '73', '161-bis', '125-sexies', '247-quater', '247-quinquies'}


@pytest.fixture
def proposal(db):
    code = Text.objects.create(akn_uri=CGI, type='law', title_ar='المدونة العامة للضرائب')
    v = Version.objects.create(text=code, language='ar', valid_from=date(2026, 1, 1), consolidation=Consolidation.DGI)
    Article.objects.create(version=v, order=1, label='المادة 73', number='73', eid='art_73',
                           body='I.- جدول حساب الضريبة\n- شريحة الدخل إلى غاية 40 000 درهم معفاة من الضريبة؛')
    bill = Text.objects.create(akn_uri=BILL, type='bill', title_ar='مشروع قانون المالية رقم 60.26 للسنة المالية 2027',
                               title_fr='Projet de loi de finances n° 60-26 pour l’année budgétaire 2027')
    Version.objects.create(text=bill, language='ar', valid_from=date(2026, 10, 20), consolidation=Consolidation.BILL)
    Change.objects.create(text_uri=CGI, number='73', verb='modified', source=Change.Source.BILL, by_kind='bill',
                          by_number='60-26', by_uri=BILL, by_article='المادة 7', state=Change.State.PROPOSED,
                          published_on=date(2026, 10, 20), effective_on=date(2031, 1, 1),
                          wording=['المادة 73.- سعر الضريبة', '- شريحة الدخل إلى غاية 60.000 درهم معفاة من الضريبة ؛'])
    return code, bill


def test_a_bill_stands_nowhere_and_its_proposals_are_no_articles_history(proposal):
    code, bill = proposal
    assert engine.standing(bill)['status'] == 'unknown'
    assert history.article_changes(code).get('73', []) == []
    assert history.proposals_of(code)['73']['name'] == {'ar': 'مشروع قانون المالية 2027', 'fr': 'projet de loi de finances 2027'}


def test_an_article_says_a_bill_proposes_to_change_it_and_the_bill_lists_what_it_proposes(api, proposal):
    d = api.get('/api/corpus/at/ma/code/cgi/').json()
    art = d['articles'][0]
    assert art['proposed']['bill'] == '/ma/projet-loi/60-26' and art['proposed']['effective_on'] == '2031-01-01'
    assert art['changes'] == [] and d['standing']['changes'] == 0
    b = api.get('/api/corpus/at/ma/projet-loi/60-26/').json()
    assert b['standing']['status'] == 'unknown'
    assert [(c['number'], c['state']) for c in b['amends'][0]['changes']] == [('73', 'proposed')]


def test_the_proposal_gives_the_bills_words_when_it_cannot_be_placed(api, proposal, django_assert_max_num_queries):
    with django_assert_max_num_queries(8):
        d = api.get('/api/corpus/proposed/', {'path': '/ma/code/cgi/art_73'}).json()
    p = d['proposals'][0]
    assert p['bill']['article'] == 'المادة 7' and p['effective_on'] == '2031-01-01'
    assert p['wording'][1].startswith('- شريحة الدخل إلى غاية 60.000')
    assert p['after'] is not None or p['unplaced']


def test_a_year_with_no_law_yet_answers_with_its_bill_said_as_one(api, proposal):
    from apps.budget.models import FinanceLaw, Kind
    _, bill = proposal
    FinanceLaw.objects.create(year=2027, kind=Kind.BILL, number='60.26', title=bill.title_ar, text=bill)
    d = api.get('/api/budget/laws/2027/').json()
    assert d['kind'] == 'bill' and d['filed']['on'] == '2026-10-20' and d['filed']['path'] == '/ma/projet-loi/60-26'
    assert api.get('/api/budget/laws/2027/', {'kind': 'law'}).status_code == 404
    law = FinanceLaw.objects.get(year=2027)
    from apps.budget.services.checks import run_checks
    assert not [c for c in run_checks(law, {}) if c['id'] == 'table_article']    # its annexes are other files


def test_a_bills_debate_is_never_the_topics_next_change(settings):
    from apps.topics.services import kit
    settings.SHOW_DRAFTS = True
    content = {'reform': {
        'lf-2027': {'stage': 'bill', 'timeline': [{'date': '2026-11-19', 'text': {'ar': 'آخر أجل'}}]},
        'lf-2026': {'stage': 'in_force', 'timeline': [{'date': '2026-12-01', 'text': {'ar': 'يطبق'}}]}}}
    assert [e['change'] for e in kit.upcoming(content, today='2026-10-26')] == ['lf-2026']


def test_a_negative_amount_printed_with_its_sign_last_is_put_back():
    assert finance_bill.signed('رصيد الميزانية العامة ......... 690 921 000 -88').endswith('-88 690 921 000')
    assert finance_bill.signed('فاتح يناير 2027 -1') == 'فاتح يناير 2027 -1'


def test_the_watcher_reads_the_dossiers_files_and_agenda():
    from apps.budget.management.commands.watch_finance_bill import dossier
    page = ('<div>الأربعاء 28 أكتوبر 2026</div><p>الشروع في المناقشة العامة</p>'
            '<a href="/sites/default/files/01-%20Projet%20loi%20de%20Finances%202027_Ar.pdf">مشروع قانون المالية رقم 60.26</a>')
    d = dossier(page)
    assert d['agenda'] == ['الأربعاء 28 أكتوبر 2026']
    assert d['files'] == [{'url': 'https://www.chambredesrepresentants.ma/sites/default/files/01-%20Projet%20loi%20de%20Finances%202027_Ar.pdf',
                           'name': 'مشروع قانون المالية رقم 60.26'}]


def test_following_the_bill_tells_its_stages_and_an_article_that_it_is_proposed_for_change(api, proposal,
                                                                                             django_assert_max_num_queries):
    with django_assert_max_num_queries(12):
        d = api.get('/api/follows/news/', {'path': ['/ma/projet-loi/60-26', '/ma/code/cgi/art_73']}).json()
    bill, art = d['news']
    assert [i['key'] for i in bill['items']] == ['bill:2026-10-20']
    assert bill['items'][0]['text']['ar'] == 'أودعته الحكومة في البرلمان'
    assert art['items'][0]['key'] == 'proposed:/ma/projet-loi/60-26'
    assert 'مشروع، ماشي قانون' in art['items'][0]['text']['ar']


def test_the_press_watch_lists_only_new_articles_about_the_bill():
    from apps.budget.management.commands.watch_finance_bill import press_candidates
    feed = ('<item><title><![CDATA[مشروع قانون المالية 2027 أمام البرلمان]]></title><link>https://a.ma/1</link><pubDate>Mon</pubDate></item>'
            '<item><title>PLF 2027 : ce qui change</title><link>https://a.ma/2</link></item>'
            '<item><title>Match de football</title><link>https://a.ma/3</link></item>')
    found = press_candidates({'f': feed}, 2027, known={'https://a.ma/2'})
    assert [c['url'] for c in found] == ['https://a.ma/1']


def test_a_dead_link_in_the_dossier_is_said_and_the_watcher_goes_on(tmp_path, settings, monkeypatch):
    # 28 Oct 2026: the Chamber's link to the bill's own file answered 404 and the watcher stopped there.
    import urllib.error
    from io import StringIO
    from django.core.management import call_command
    from apps.budget.management.commands import watch_finance_bill as watch
    settings.CORPUS_DIR = tmp_path
    page = ('<a href="/sites/default/files/01-dead.pdf">مشروع قانون المالية</a>'
            '<a href="/sites/default/files/02-note.pdf">مذكرة تقديم</a>').encode()

    def get(url):
        if url.endswith('01-dead.pdf'):
            raise urllib.error.HTTPError(url, 404, 'Not Found', {}, None)
        return page if 'Dossier' in url else b'<rss></rss>' if url.endswith('rss') else b'%PDF-1.7 note'
    monkeypatch.setattr(watch, 'get', get)
    monkeypatch.setattr(watch.time, 'sleep', lambda s: None)
    out = StringIO()
    call_command('watch_finance_bill', '--year', '2027', '--fetch', stdout=out)
    assert 'did not answer (HTTP Error 404: Not Found)' in out.getvalue()
    assert (tmp_path / 'sources' / 'parliament' / 'plf2027' / '02-note.pdf').read_bytes() == b'%PDF-1.7 note'
