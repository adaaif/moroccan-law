"""The articles people know by their number or a name (famous.py, 9 Nov 2026): «490» and «العلاقات الرضائية» open art.
490 of the penal code first, «الفصل 1234» asks which code, «الفساد» asks «did you mean», typing «222» offers art. 222,
and the article's page and head carry the public's name; never a query per card."""
from datetime import date

import ma_law
import pytest
from django.db import connection

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.search.services import famous

PENAL = '/ma/dahir/1-59-413'


def row_of(code: str, number: str) -> int:
    return next(i for i, r in enumerate(famous.table()['rows']) if (r['code'], r['number']) == (code, number))


# The list, read without the database.

def test_the_list_names_each_article_once_and_each_name_once():
    from apps.corpus.services.codes import CODES
    rows = famous.table()['rows']
    assert all(r['code'] in CODES and r['number'].isdigit() for r in rows)
    assert len({(r['code'], r['number']) for r in rows}) == len(rows)
    folded = [famous._norm(n) for r in rows for n in r['names']]
    assert len(folded) == len(set(folded)), 'a name written twice, or leading to two articles'
    # Never an opinion in the public's names: no «controversial», no verdict, and every row says what it is known as or
    # carries the law's own term (491, 53).
    assert not any(w in ' '.join(n for r in rows for n in r['known_as']['ar'] + r['known_as']['fr'])
                   for w in ('مثير', 'جدل', 'controvers', 'scandal'))


def test_a_bare_famous_number_asks_for_its_article_and_another_number_for_nothing():
    assert famous.read('490', [])['rows'] == [row_of('penal', '490')]
    assert famous.read(' 222 ', [])['rows'] == [row_of('penal', '222')]
    # A year, an issue, an amount: searched as typed.
    assert famous.read('2026', []) is None and famous.read('7556', []) is None


def test_an_article_without_its_code_asks_which_code():
    asked = famous.read('الفصل 490', ma_law.parse_query('الفصل 490'))
    assert asked['number'] == '490' and asked['word'] == 'fasl' and asked['rows'] == [row_of('penal', '490')]
    # No famous article of that number: still a choice of codes (F3).
    asked = famous.read('الفصل 1234', ma_law.parse_query('الفصل 1234'))
    assert asked == {'number': '1234', 'word': 'fasl', 'rows': [], 'maybe': []}
    assert famous.read('المادة 20', ma_law.parse_query('المادة 20'))['word'] == 'madda'


@pytest.mark.parametrize('q, code, number', [
    ('العلاقات الرضائية', 'penal', '490'),
    ('العلاقات الرضائيّة', 'penal', '490'),                  # a vowel mark is no other name
    ('واش العلاقات الرضائية ممنوعة', 'penal', '490'),         # a name of two words inside a question
    ('Relations hors-mariage au Maroc', 'penal', '490'),
    ('وكالين رمضان', 'penal', '222'),
    ('wkalin ramdan', 'penal', '222'),
    ('زواج القاصرات فالمغرب', 'family', '20'),
    ('Avortement', 'penal', '449'),
    ('المناصفة', 'constitution', '19'),
])
def test_the_publics_names_ask_for_the_article(q, code, number):
    assert famous.read(q, [])['rows'] == [row_of(code, number)]


def test_a_one_word_name_must_be_the_whole_question():
    # «المناصفة في الإرث» is not art. 19's question; «partage des biens apres deces» is an inheritance.
    assert famous.read('المناصفة في الإرث', []) is None
    assert famous.read('partage des biens apres deces', []) is None


def test_a_word_the_law_uses_otherwise_only_asks():
    assert famous.read('الفساد', []) == {'number': None, 'word': '', 'rows': [], 'maybe': [row_of('penal', '490')]}


def test_typing_offers_the_famous_articles():
    assert famous.suggested('49') == [row_of('family', '49'), row_of('penal', '490'), row_of('penal', '491')]
    assert famous.suggested('222') == [row_of('penal', '222')]
    assert famous.suggested('زواج القا') == [row_of('family', '20')]
    assert famous.suggested('4') == [] and famous.suggested('زوا') == []


# Over a small corpus (Postgres with ParadeDB, as the search's other tests).

pg = pytest.mark.skipif(connection.vendor != 'postgresql', reason='BM25 needs ParadeDB (TEST_DATABASE_URL)')


@pytest.fixture
def corpus(db):
    from apps.search.services.index import rebuild

    def code(uri, kind, number, printed, title, articles):
        text = Text.objects.create(akn_uri=uri, type=kind, number=number, number_as_printed=printed, title_ar=title,
                                   status='in_force')
        v = Version.objects.create(text=text, language='ar', valid_from=date(2004, 2, 5), consolidation=Consolidation.ADALA)
        for order, (label, n, body) in enumerate(articles, 1):
            Article.objects.create(version=v, order=order, label=label, number=n, body=body, eid=f'art_{n}')
        return text

    penal = code('/akn/ma/act/dahir/1-59-413', 'dahir', '1-59-413', '1.59.413', 'ظهير شريف بالمصادقة على مجموعة القانون الجنائي', [
        ('الفصل 222', '222', 'كل من عرف باعتناقه الدين الإسلامي، وتجاهر بالإفطار في نهار رمضان، في مكان عمومي، دون عذر شرعي، يعاقب بالحبس.'),
        ('الفصل 489', '489', 'يعاقب بالحبس من ارتكب فعلا من أفعال الشذوذ الجنسي مع شخص من جنسه.'),
        ('الفصل 490', '490', 'كل علاقة جنسية بين رجل وامرأة لا تربط بينهما علاقة الزوجية تكون جريمة الفساد ويعاقب عليها بالحبس من شهر واحد إلى سنة.'),
        ('الفصل 491', '491', 'يعاقب بالحبس من سنة إلى سنتين أحد الزوجين الذي يرتكب جريمة الخيانة الزوجية.'),
        ('الفصل 493', '493', 'الجرائم المعاقب عليها في الفصلين 490 و491 لا تثبت إلا بناء على محضر رسمي.'),
    ])
    code('/akn/ma/act/loi/65-99', 'law', '65-99', '65.99', 'القانون رقم 65.99 المتعلق بمدونة الشغل', [
        ('المادة 490', '490', 'تحدث لجنة إقليمية للبحث والمصالحة.'),
        ('المادة 1234', '1234', 'مادة للتجربة.'),
    ])
    code('/akn/ma/act/loi/70-03', 'law', '70-03', '70.03', 'القانون رقم 70.03 بمثابة مدونة الأسرة', [
        ('المادة 20', '20', 'لقاضي الأسرة المكلف بالزواج، أن يأذن بزواج الفتى والفتاة دون سن الأهلية.'),
    ])
    rebuild(log=lambda m: None)
    return penal


@pg
def test_a_famous_number_shows_its_article_first_then_the_other_codes(api, corpus):
    r = api.get('/api/search/', {'q': '490'}).json()
    card = r['famous'][0]
    assert card['path'] == f'{PENAL}/art_490' and card['known_as']['ar'] == ['العلاقات الرضائية']
    assert card['body'].startswith('كل علاقة جنسية') and card['text']['path'] == PENAL
    # Read from the law's words, not chosen: art. 493 names 490.
    assert [c['path'] for c in card['cited_by']] == [f'{PENAL}/art_493']
    assert [t['path'] for t in r['choices']['texts']] == ['/ma/loi/65-99/art_490']
    assert r['nearest'] == [] and r['answer'] is None


@pg
def test_an_article_number_without_a_famous_one_offers_the_codes_alone(api, corpus):
    r = api.get('/api/search/', {'q': 'المادة 1234'}).json()
    assert r['famous'] == [] and [t['path'] for t in r['choices']['texts']] == ['/ma/loi/65-99/art_1234']


@pg
def test_a_name_opens_the_article_and_a_word_the_law_uses_otherwise_asks(api, corpus):
    assert api.get('/api/search/', {'q': 'العلاقات الرضائية'}).json()['famous'][0]['path'] == f'{PENAL}/art_490'
    r = api.get('/api/search/', {'q': 'الفساد'}).json()
    assert r['famous'] == [] and [m['path'] for m in r['maybe']] == [f'{PENAL}/art_490']


@pg
def test_cards_cost_the_same_queries_for_one_article_or_several(corpus, django_assert_max_num_queries):
    from django.db import connection as conn
    from django.test.utils import CaptureQueriesContext

    rows = [row_of('penal', n) for n in ('490', '491', '489', '222')] + [row_of('family', '20')]
    famous.cards(rows[:1])                 # the shelf's addresses, kept for the process
    with CaptureQueriesContext(conn) as one:
        famous.cards(rows[:1])
    with CaptureQueriesContext(conn) as five:
        assert len(famous.cards(rows)) == 5
    assert len(five.captured_queries) == len(one.captured_queries) <= 8


@pg
def test_typing_a_number_offers_the_famous_article_with_its_name(api, corpus):
    found = api.get('/api/search/suggest/', {'q': '222'}).json()['citations']
    assert found[0]['article']['path'] == f'{PENAL}/art_222'
    assert found[0]['known_as']['ar'][1] == 'وكالين رمضان'


@pg
def test_the_articles_page_and_head_carry_the_publics_name(api, corpus):
    from apps.corpus.services import heads

    page = api.get(f'/api/corpus/at{PENAL}/art_490/').json()
    known = {a['eid']: a['known_as'] for a in page['articles']}
    assert known['art_490']['ar'] == ['العلاقات الرضائية'] and known.get('art_493') is None
    tags = heads.tags(f'{PENAL}/art_490')
    assert 'العلاقات الرضائية' in tags['title'] and tags['description'].startswith('يُعرف في النقاش العام')
    assert 'les relations sexuelles hors mariage' in tags['ld']['alternateName']
