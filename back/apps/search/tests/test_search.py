"""Search over a small corpus: citations jump, words find articles grouped by text, a query typed with the
keyboard in French is repaired, empty searches are logged. Needs Postgres with ParadeDB (TEST_DATABASE_URL)."""
from datetime import date

import pytest
from django.db import connection

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.search.models import SearchLog
from apps.search.services.index import rebuild
from apps.sources.models import Edition, Issue

pytestmark = [pytest.mark.django_db,
              pytest.mark.skipif(connection.vendor != 'postgresql', reason='BM25 needs ParadeDB (TEST_DATABASE_URL)')]


@pytest.fixture
def corpus():
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7533, date=date(2026, 8, 10))
    law = Text.objects.create(akn_uri='/akn/ma/act/loi/12-26', type='law', number='12-26',
                              number_as_printed='12.26', title_ar='قانون رقم 12.26 يتعلق بكراء المحلات التجارية',
                              signed_on=date(2026, 7, 1), first_published_in=issue)
    v = Version.objects.create(text=law, language='ar', valid_from=date(2026, 8, 10),
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='المادة الأولى', number='1', body='يطبق هذا القانون على عقود الكراء.', eid='art_1',
                           printed_page=5141)
    Article.objects.create(version=v, order=2, label='المادة 2', number='2', body='يلتزم المكتري بأداء الوجيبة الكرائية.', eid='art_2')
    decree = Text.objects.create(akn_uri='/akn/ma/act/decret/2-26-453', type='decree', number='2-26-453',
                                 number_as_printed='2.26.453', title_ar='مرسوم رقم 2.26.453 بتحديد رسوم التسجيل',
                                 first_published_in=issue)
    v2 = Version.objects.create(text=decree, language='ar', valid_from=date(2026, 8, 10),
                                consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v2, order=1, label='المادة الأولى', number='1', body='تحدد رسوم التسجيل كما يلي.', eid='art_1')
    rebuild(log=lambda m: None)
    return {'law': law, 'decree': decree, 'issue': issue}


def test_the_index_holds_what_an_answer_shows_by_address(corpus):
    # B24 of the search plan: no row points at a corpus row; each holds what the answer shows.
    from apps.search.models import SearchEntry
    art = SearchEntry.objects.get(kind='article', path='/ma/loi/12-26/art_1')
    assert (art.text_path, art.label, art.eid, art.page, art.consolidation) == ('/ma/loi/12-26', 'المادة الأولى', 'art_1', 5141, 'as_published')
    assert art.body == 'يطبق هذا القانون على عقود الكراء.'
    law = SearchEntry.objects.get(kind='text', text_path='/ma/loi/12-26')
    assert (law.issue, law.in_corpus, law.signed_year, law.title) == ('7533', True, 2026, 'قانون رقم 12.26 يتعلق بكراء المحلات التجارية')


def test_an_answer_reads_no_corpus_table(api, corpus):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx:
        api.get('/api/search/', {'q': 'عقود الكراء'})
    assert not [q['sql'] for q in ctx.captured_queries if 'corpus_article' in q['sql'] or 'corpus_version' in q['sql']]


def test_words_find_articles_grouped_by_text(api, corpus):
    r = api.get('/api/search/', {'q': 'عقود الكراء'}).json()
    assert r['understood_as'] == 'words'
    assert r['results'][0]['text']['path'] == '/ma/loi/12-26'
    assert r['results'][0]['articles'][0]['path'] == '/ma/loi/12-26/art_1'
    assert any(s['hit'] for s in r['results'][0]['articles'][0]['snippet'])
    # Its stamp: the BO issue and the page it was printed on.
    assert (r['results'][0]['text']['issue'], r['results'][0]['text']['consolidation']) == ('7533', 'as_published')
    assert r['results'][0]['articles'][0]['page'] == 5141
    # B3: the search's row keeps what its first page showed, in order.
    assert SearchLog.objects.get(pk=r['log']).shown[0] == '/ma/loi/12-26/art_1'


def test_a_citation_jumps(api, corpus):
    r = api.get('/api/search/', {'q': 'المادة 2 من القانون رقم 12.26'}).json()
    assert r['jump']['state'] == 'found'
    assert r['jump']['article']['path'] == '/ma/loi/12-26/art_2'
    r = api.get('/api/search/', {'q': '2.26.453'}).json()
    assert r['jump']['text']['path'] == '/ma/decret/2-26-453'
    r = api.get('/api/search/', {'q': 'ج.ر 7533'}).json()
    assert r['jump']['state'] == 'issue' and r['jump']['issue']['path'] == '/bo/general_ar/7533'


def test_a_citation_is_read_as_the_librarys_box_reads_it(api, corpus):
    """W3 of the library-search review: «ق 12.26» is the law, «المادة 2 المكررة» its article «bis», on the search page and in
    the header's suggestions as in the library's box."""
    from apps.corpus.models import Article, Version
    v = Version.objects.filter(text__number='12-26').first()
    Article.objects.create(version=v, order=99, label='المادة 2 المكررة', number='2-bis', eid='art_2-bis', body='نص المادة المكررة.')
    r = api.get('/api/search/', {'q': 'المادة 2 المكررة من القانون رقم 12.26'}).json()
    assert r['jump']['state'] == 'found' and r['jump']['article']['path'] == '/ma/loi/12-26/art_2-bis'
    r = api.get('/api/search/', {'q': 'ق 12.26'}).json()
    assert r['jump']['text']['path'] == '/ma/loi/12-26'
    r = api.get('/api/search/suggest/', {'q': 'المادة 2 المكررة من القانون رقم 12.26'}).json()
    assert [c['article']['path'] for c in r['citations'] if c.get('article')] == ['/ma/loi/12-26/art_2-bis']
    r = api.get('/api/search/', {'q': 'المادة 2 من القانون رقم 12.26'}).json()
    assert r['jump']['article']['path'] == '/ma/loi/12-26/art_2'                     # its neighbour stays itself


def test_a_found_article_stands_alone_and_the_words_beside_it_are_searched(api, corpus):
    # B8 of the search plan: a citation keeps its exact path; its own words («المادة», «القانون», «12.26») are not
    # searched under it (an annex holding «ف», «ق» and «418» came under «ف 418 ق.ل.ع»), the words said beside it are.
    r = api.get('/api/search/', {'q': 'المادة 2 من القانون رقم 12.26'}).json()
    assert r['jump']['article']['path'] == '/ma/loi/12-26/art_2' and r['results'] == []
    r = api.get('/api/search/', {'q': 'المادة 2 من القانون رقم 12.26 رسوم التسجيل'}).json()
    assert r['jump']['article']['path'] == '/ma/loi/12-26/art_2'
    assert [x['text']['path'] for x in r['results']] == ['/ma/decret/2-26-453']


def test_an_amending_article_says_which_article_it_changes(api, corpus):
    # B16 of the search plan: its card leads to the article it changes, from the sound changes only.
    from apps.consolidation.models import Change
    common = {'by_uri': '/akn/ma/act/decret/2-26-453', 'by_article': 'المادة الأولى', 'by_kind': 'decree', 'by_number': '2-26-453',
              'source': 'reading', 'text_uri': '/akn/ma/act/loi/12-26'}
    Change.objects.create(number='2', verb='modified', state='read', **common)
    Change.objects.create(number='1', verb='modified', state='unclear', **common)      # not read: not said
    Change.objects.create(number='9', verb='modified', state='read', **common)         # no such article on the site
    rebuild(log=lambda m: None)
    r = api.get('/api/search/', {'q': 'رسوم التسجيل'}).json()
    found = r['results'][0]['articles'][0]
    assert found['path'] == '/ma/decret/2-26-453/art_1'
    assert [(c['path'], c['label'], c['verb'], c['name']['ar']) for c in found['changes']] == [
        ('/ma/loi/12-26/art_2', 'المادة 2', 'modified', 'قانون رقم 12.26 يتعلق بكراء المحلات التجارية')]
    assert api.get('/api/search/', {'q': 'عقود الكراء'}).json()['results'][0]['articles'][0]['changes'] == []


def test_an_answer_says_how_long_each_stage_took(api, corpus):
    # B27: the Server-Timing header names each stage, for a browser's network panel and perf_report.
    stages = [p.split(';dur=')[0] for p in api.get('/api/search/', {'q': 'عقود الكراء'})['Server-Timing'].split(', ')]
    assert stages == ['cite', 'words', 'page', 'snippets', 'log', 'topics']
    stages = [p.split(';dur=')[0] for p in api.get('/api/search/suggest/', {'q': 'قانون'})['Server-Timing'].split(', ')]
    assert stages == ['finds', 'topics', 'cite', 'titles', 'texts']


def test_a_code_not_loaded_is_named(api, corpus):
    r = api.get('/api/search/', {'q': 'مدونة الأسرة 53'}).json()
    assert r['jump']['state'] == 'not_in_corpus'
    assert r['jump']['name']['ar'] == 'مدونة الأسرة'


def test_a_query_typed_in_french_layout_is_repaired(api, corpus):
    r = api.get('/api/search/', {'q': 'hgmvhx'}).json()          # «الكراء» typed on AZERTY (ك is the m key)
    assert r['understood_as'] == 'repaired' and r['repaired'] == 'الكراء'
    assert r['results'][0]['text']['path'] == '/ma/loi/12-26'


def test_some_words_when_not_all_match(api, corpus):
    r = api.get('/api/search/', {'q': 'الكراء الطائرات'}).json()
    assert r['understood_as'] == 'some_words' and r['partial'] and r['texts'] == 1


def test_filters_and_logging(api, corpus):
    r = api.get('/api/search/', {'q': 'رسوم', 'type': 'law'}).json()
    assert r['texts'] == 0
    assert SearchLog.objects.filter(query='رسوم', results=0).exists()


def test_suggest_titles_as_you_type(api, corpus):
    r = api.get('/api/search/suggest/', {'q': 'كراء المحل'}).json()
    assert r['texts'][0]['path'] == '/ma/loi/12-26'
    r = api.get('/api/search/suggest/', {'q': '12.26'}).json()
    assert r['citations'][0]['text']['path'] == '/ma/loi/12-26'


def test_a_short_form_of_single_letters_suggests_no_title(api, corpus, monkeypatch):
    """«ق.م.م» is three words of one letter: the titles were walked at every «ق», a slow suggestion (W6 of
    the library-search review). One letter names no title, and the titles are not read at all."""
    from apps.search.services.search import titles
    monkeypatch.setattr(titles, '_title_rows', lambda: (_ for _ in ()).throw(AssertionError('the titles were read')))
    assert titles._titles(['ق', 'م', 'م'], 6) == []
    assert api.get('/api/search/suggest/', {'q': 'ق.م.م'}).status_code == 200


def test_suggestions_carry_what_the_librarys_reader_finds(api, corpus):
    """W3 of the library-search review: one reader for both boxes. A dahir by its day and a finance law by its year are
    offered by the header's box too, before its own titles, and never twice."""
    from datetime import date

    from apps.corpus.models import Text
    day = {'signed_on': date(1984, 10, 2), 'signed_on_hijri': '6 محرم 1405'}
    Text.objects.create(akn_uri='/akn/ma/act/dahir/1-84-177', type='dahir', number='1-84-177', number_as_printed='1.84.177',
                        title_ar='ظهير شريف رقم 1.84.177 يتعلق بتعويض المصابين في حوادث تسببت فيها مركبات برية ذات محرك', **day)
    Text.objects.create(akn_uri='/akn/ma/act/dahir/1-83-351', type='dahir', number='1-83-351', number_as_printed='1.83.351',
                        title_ar='ظهير شريف رقم 1.83.351 بتفويض السلطة فيما يتعلق بإدارة الدفاع الوطني', **day)
    Text.objects.create(akn_uri='/akn/ma/act/dahir/1-58-250', type='dahir', number='1-58-250', number_as_printed='1.58.250',
                        title_ar='ظهير شريف رقم 1.58.250 بسن قانون الجنسية المغربية', signed_on=date(1958, 9, 6))
    Text.objects.create(akn_uri='/akn/ma/act/loi/60-24', type='law', number='60-24', number_as_printed='60.24',
                        title_ar='قانون المالية رقم 60.24 للسنة المالية 2025', signed_on=date(2024, 12, 13))
    # Two dahirs signed the same day: a citation cannot choose, the reader names both, in either calendar.
    both = {'/ma/dahir/1-84-177', '/ma/dahir/1-83-351'}
    for asked in ('ظهير 2 أكتوبر 1984', 'ظهير 6 محرم 1405'):
        r = api.get('/api/search/suggest/', {'q': asked}).json()
        assert {f['path'] for f in r['finds']} == both and {f['why'] for f in r['finds']} == {'day'}, asked
        assert not any(c.get('text') for c in r['citations']) and not both & {x['path'] for x in r['texts']}, asked
    # One dahir on its day: the citation's line names it already, the reader's does not say it again.
    r = api.get('/api/search/suggest/', {'q': 'ظهير 6 شتنبر 1958'}).json()
    named = [c['text']['path'] for c in r['citations'] if c.get('text')] + [f['path'] for f in r['finds']]
    assert named == ['/ma/dahir/1-58-250']
    r = api.get('/api/search/suggest/', {'q': 'قانون المالية 2025'}).json()
    assert [f['path'] for f in r['finds']] == ['/ma/loi/60-24'] and all(x['path'] != '/ma/loi/60-24' for x in r['texts'])
    assert api.get('/api/search/suggest/', {'q': 'كراء المحل'}).json()['finds'] == []


def test_resolve_says_where_each_citation_stands(api, corpus):
    citations = [
        {'kind': 'article', 'raw': 'المادة 2 من القانون رقم 12.26', 'article': '2', 'text_kind': 'law', 'text_number': '12-26'},
        {'kind': 'article', 'raw': 'المادة 9 من القانون رقم 12.26', 'article': '9', 'text_kind': 'law', 'text_number': '12-26'},
        {'kind': 'article', 'raw': 'الفصل 230 من ق.ل.ع', 'article': '230', 'code': 'doc'},
        {'kind': 'issue', 'raw': 'ج.ر 7533', 'issue': 7533},
    ]
    r = api.post('/api/search/resolve/', {'citations': citations, 'since': '2026-01-01'}, format='json').json()
    states = [x['state'] for x in r['results']]
    assert states == ['found', 'text_only', 'not_in_corpus', 'issue']
    assert api.post('/api/search/resolve/', {'citations': 'x'}, format='json').status_code == 400


def test_a_code_not_in_the_corpus_is_always_said(api, corpus):
    # «مدونة الأسرة» is a code the corpus does not hold: said with where to read it (row 1 of the reader-experience review)…
    r = api.get('/api/search/', {'q': 'مدونة الأسرة'}).json()
    assert r['jump']['state'] == 'not_in_corpus' and r['jump']['official'].startswith('https://adala.justice.gov.ma')
    # …also when other words come with it, which are searched on their own and come under it…
    r = api.get('/api/search/', {'q': 'عقود الكراء في قانون الالتزامات والعقود'}).json()
    assert r['jump']['state'] == 'not_in_corpus' and r['results'][0]['text']['path'] == '/ma/loi/12-26'
    # …but texts sharing only a word of its name («قانون») are not answers.
    assert api.get('/api/search/', {'q': 'قانون الالتزامات والعقود'}).json()['texts'] == 0
    # …and an article of it too.
    r = api.get('/api/search/', {'q': 'الفصل 230 من ق.ل.ع'}).json()
    assert r['jump']['state'] == 'not_in_corpus'


def test_a_code_by_its_everyday_name(api, corpus):
    road = Text.objects.create(akn_uri='/akn/ma/act/loi/52-05', type='law', number='52-05', number_as_printed='52.05',
                               title_ar='القانون رقم 52.05 المتعلق بمدونة السير على الطرق')
    v = Version.objects.create(text=road, language='ar', valid_from=date(2010, 3, 11),
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='المادة 85', number='85', body='لا يجوز السياقة بدون رخصة.', eid='art_85')
    rebuild(log=lambda m: None)
    for q in ('قانون السير', 'code de la route'):
        r = api.get('/api/search/', {'q': q}).json()
        assert r['jump']['state'] == 'found' and r['jump']['text']['path'] == '/ma/loi/52-05'
        assert r['results'][0]['text']['path'] == '/ma/loi/52-05'
    r = api.get('/api/search/', {'q': 'المادة 85 من مدونة السير'}).json()
    assert r['jump']['article']['path'] == '/ma/loi/52-05/art_85'
    # B17: typed up to its number, a code offers its articles that start with it, in its order.
    for order, n in enumerate(('8', '80', '81', '82', '83', '84', '18'), start=2):
        Article.objects.create(version=v, order=order, label=f'المادة {n}', number=n, body='نص.', eid=f'art_{n}')
    Article.objects.filter(version=v, eid='art_85').update(order=9)        # after 84, as in the code
    rebuild(log=lambda m: None)
    r = api.get('/api/search/suggest/', {'q': 'مدونة السير 8'}).json()
    assert [c['article']['path'].rsplit('/', 1)[-1] for c in r['citations']] == ['art_8', 'art_80', 'art_81', 'art_82', 'art_83']
    assert [c['article']['path'] for c in api.get('/api/search/suggest/', {'q': 'المادة 85 من مدونة السير'}).json()['citations']] == [
        '/ma/loi/52-05/art_85']
    # «constitution» is the Constitution only alone.
    assert api.get('/api/search/', {'q': 'constitution'}).json()['jump']['citation']['code'] == 'constitution'
    assert api.get('/api/search/', {'q': "constitution d'une société"}).json()['jump'] is None


def test_asking_words_are_set_aside(api, corpus):
    r = api.get('/api/search/', {'q': 'واش عقود الكراء'}).json()
    assert r['asked'] == 'عقود الكراء' and r['understood_as'] == 'words'
    assert r['results'][0]['text']['path'] == '/ma/loi/12-26'
    assert api.get('/api/search/', {'q': 'عقود الكراء'}).json()['asked'] is None


def test_the_everyday_words_list(api, corpus, monkeypatch):
    from apps.search.services import vocab
    monkeypatch.setattr(vocab, 'entries', lambda: [('loyer', ['الكراء']), ('الكونطرا', ['عقود'])])
    r = api.get('/api/search/', {'q': 'الكونطرا'}).json()
    assert r['understood_as'] == 'everyday' and r['repaired'] == 'عقود'
    assert r['results'][0]['text']['path'] == '/ma/loi/12-26'
    assert api.get('/api/search/', {'q': 'loyer'}).json()['results'][0]['text']['path'] == '/ma/loi/12-26'
    # A form the corpus also writes as typed is still searched as the law says it when it is the whole query.
    monkeypatch.setattr(vocab, 'entries', lambda: [('الكراء', ['عقود'])])
    assert api.get('/api/search/', {'q': 'الكراء'}).json()['understood_as'] == 'everyday'


def test_apply_vocab_keeps_only_what_was_approved(tmp_path, monkeypatch):
    import json

    from django.core.management import call_command

    from apps.search.services import vocab
    target = tmp_path / 'everyday.json'
    target.write_text(json.dumps({'about': 'x', 'entries': []}))
    monkeypatch.setattr(vocab, 'FILE', target)
    review = tmp_path / 'review.json'
    review.write_text(json.dumps({
        'entries': [{'id': 'v001', 'order': 1, 'typed': 'AMO', 'kind': 'acronyms', 'means': ['التأمين الإجباري', 'خطأ']},
                    {'id': 'v002', 'order': 2, 'typed': 'patente', 'kind': 'french', 'means': ['الباتانتا']},
                    {'id': 'v003', 'order': 3, 'typed': 'كرا', 'kind': 'darija', 'means': ['الكراء']}],
        'decisions': {'v001': {'verdict': 'approve', 'keep': [True, False], 'extra': 'التغطية الصحية'},
                      'v002': {'verdict': 'reject', 'keep': [True], 'extra': ''}},
    }, ensure_ascii=False))
    call_command('apply_vocab', str(review))
    data = json.loads(target.read_text())
    assert data['about'] == 'x'
    assert data['entries'] == [{'typed': ['AMO'], 'kind': 'acronyms', 'means': ['التأمين الإجباري', 'التغطية الصحية']}]


def test_suggestions_name_topics_guides_laws_and_words_six_at_most(api, corpus, settings):
    # P8 of the polish review: «كراء» offers the housing topic and its law before formal titles, one line each.
    settings.SHOW_DRAFTS = True    # the guides are drafts while developing
    r = api.get('/api/search/suggest/', {'q': 'كراء'}).json()
    assert [t['slug'] for t in r['topics']] == ['housing'] and r['topics'][0]['path'] == '/topics/housing'
    assert [g['slug'] for g in r['guides']][:1] == ['renting']
    assert r['texts'][0]['path'] == '/ma/loi/12-26'
    assert len(r['topics']) + len(r['guides']) + len(r['texts']) + len(r['words']) <= 6
    r = api.get('/api/search/suggest/', {'q': 'سانديك'}).json()
    assert [w['slug'] for w in r['words']] == ['syndic']


def test_a_result_shows_two_articles_and_counts_the_rest(api, corpus):
    for order in range(3, 7):
        Article.objects.create(version=corpus['law'].versions.first(), order=order, label=f'المادة {order}', number=str(order),
                               body='تطبق أحكام الكراء على المحلات.', eid=f'art_{order}')
    rebuild(log=lambda m: None)
    r = api.get('/api/search/', {'q': 'الكراء'}).json()
    law = r['results'][0]
    assert law['text']['path'] == '/ma/loi/12-26' and len(law['articles']) == 2 and law['more'] == 3


def test_the_articles_a_heading_names_the_words_over_come_first(api, corpus):
    # T4 of the work plan: «التعويض عن الفصل» opens its section at its first article, not at the article that says
    # the words most often.
    issue = corpus['issue']
    code = Text.objects.create(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99', number_as_printed='65.99',
                               title_ar='القانون رقم 65.99 المتعلق بمدونة الشغل', first_published_in=issue)
    v = Version.objects.create(text=code, language='ar', valid_from=date(2004, 6, 8), consolidation=Consolidation.AS_PUBLISHED)
    end = ['الباب الخامس: توقف عقد الشغل وإنهاؤه', 'الفرع الرابع: التعويض عن الفصل']
    Article.objects.create(version=v, order=1, label='المادة 41', number='41', eid='art_41',
                           body='الفصل التعسفي يعطي الحق في التعويض. التعويض عن الفصل والتعويض عن الضرر وفصل الأجير.',
                           heading_path=['الباب الخامس: توقف عقد الشغل وإنهاؤه', 'الفرع الثالث: إنهاء العقد'])
    Article.objects.create(version=v, order=2, label='المادة 52', number='52', eid='art_52', heading_path=end,
                           body='يستحق الأجير المرتبط بعقد شغل غير محدد المدة التعويض عن الفصل بعد ستة أشهر من الشغل داخل '
                                'نفس المقاولة بصرف النظر عن طريقة الأداء.')
    Article.objects.create(version=v, order=3, label='المادة 53', number='53', eid='art_53', heading_path=end,
                           body='يعادل مبلغ التعويض عن الفصل عن كل سنة من الشغل ما يلي.')
    rebuild(log=lambda m: None)
    r = api.get('/api/search/', {'q': 'التعويض عن الفصل'}).json()
    assert [a['eid'] for a in r['results'][0]['articles']] == ['art_52', 'art_53']


def test_search_endpoints_keep_a_fixed_number_of_queries(api, corpus, django_assert_max_num_queries):
    # B27 of the search plan: ceilings that do not grow with the data (the N+1 rule).
    with django_assert_max_num_queries(12):
        api.get('/api/search/', {'q': 'عقود الكراء'})
    with django_assert_max_num_queries(16):
        api.get('/api/search/', {'q': 'المادة 2 من القانون رقم 12.26'})
    with django_assert_max_num_queries(8):
        api.get('/api/search/suggest/', {'q': 'قانون'})


def test_a_question_inside_a_named_code_is_searched_there_first(api, corpus, settings):
    # C12 of the constitution review: «اللغات الرسمية في الدستور» opens art. 5, not another text that says the words.
    settings.SEARCH_INSIDE = True
    cons = Text.objects.create(akn_uri='/akn/ma/act/dahir/1-11-91', type='constitution', number='1-11-91',
                               number_as_printed='1.11.91', title_ar='ظهير شريف رقم 1.11.91 بتنفيذ نص الدستور', status='in_force')
    v = Version.objects.create(text=cons, language='ar', valid_from=date(2011, 7, 29), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='الفصل 1', number='1', body='نظام الحكم بالمغرب نظام ملكية دستورية.', eid='art_1')
    Article.objects.create(version=v, order=5, label='الفصل 5', number='5', body='تظل العربية اللغة الرسمية للدولة.', eid='art_5')
    other = Text.objects.create(akn_uri='/akn/ma/act/loi-organique/26-16', type='organic_law', number='26-16',
                                number_as_printed='26.16', title_ar='قانون تنظيمي رقم 26.16 بتفعيل الطابع الرسمي للأمازيغية')
    v2 = Version.objects.create(text=other, language='ar', valid_from=date(2019, 9, 26), consolidation=Consolidation.AS_PUBLISHED)
    for n in range(1, 4):       # the words said more often here than in the constitution
        Article.objects.create(version=v2, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}',
                               body='اللغة الرسمية الأمازيغية لغة رسمية للدولة اللغة الرسمية في الدستور.')
    rebuild(log=lambda m: None)
    r = api.get('/api/search/', {'q': 'ما هي اللغة الرسمية في الدستور'}).json()
    assert r['jump']['text']['path'] == '/ma/dahir/1-11-91'
    assert r['results'][0]['text']['path'] == '/ma/dahir/1-11-91'
    assert r['results'][0]['articles'][0]['path'] == '/ma/dahir/1-11-91/art_5'
    assert '/ma/loi-organique/26-16' in [x['text']['path'] for x in r['results']]

