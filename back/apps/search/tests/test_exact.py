"""Words between quotes (31 Oct 2026): searched as typed, each word whole and unstemmed, side by side and in
order, the first word with or without the letters Arabic writes on its front («بالقوة القاهرة», «والعقد»), with no repair
and no topic above them; «ابحث في هذا النص» and the law page's marks read them the same way.
The search needs Postgres with ParadeDB (TEST_DATABASE_URL); the reading of the quotes does not."""
from datetime import date

import pytest
from django.db import connection

from apps.search.services.search.quotes import quoted

needs_bm25 = pytest.mark.skipif(connection.vendor != 'postgresql', reason='BM25 needs ParadeDB (TEST_DATABASE_URL)')


def test_any_quote_a_keyboard_types_opens_and_closes():
    assert quoted('عقد "القوة القاهرة"') == (['القوه القاهره'], ['القوة القاهرة'], 'عقد')
    assert quoted('«العقد» و“force majeure”') == (['العقد', 'force majeure'], ['العقد', 'force majeure'], 'و')
    # One left open runs to the end; an empty pair is no phrase.
    assert quoted('الكراء "الوجيبة   الشهرية') == (['الوجيبه الشهريه'], ['الوجيبة الشهرية'], 'الكراء')
    assert quoted('"" الكراء') == ([], [], 'الكراء')
    assert quoted('الكراء') == ([], [], 'الكراء')


@pytest.fixture
def corpus():
    from apps.corpus.models import Article, Consolidation, Text, Version
    from apps.search.services.index import rebuild
    from apps.sources.models import Edition, Issue
    from apps.translations.models import FrenchArticle

    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7533, date=date(2026, 8, 10))
    law = Text.objects.create(akn_uri='/akn/ma/act/loi/12-26', type='law', number='12-26', number_as_printed='12.26',
                              title_ar='قانون رقم 12.26 يتعلق بالعقود', signed_on=date(2026, 7, 1), first_published_in=issue)
    v = Version.objects.create(text=law, language='ar', valid_from=date(2026, 8, 10), consolidation=Consolidation.AS_PUBLISHED)
    for n, body in enumerate([
        'يبرم العقد كتابة.',
        'يكون كل عقد مكتوبا، وإلا كان باطلا.',
        'لا يسأل المدين إذا حالت القوةُ القاهرة دون التنفيذ.',
        'لا تعد القوة وحدها سببا، ولو كان في القاهرة.',
        'ينقضي الالتزام بقوة قاهرة، ويعفى المدين للقوة القاهرة.',
        'تسري هذه العقدة على والعقد الجديد.',
        'يعتبر الأمر معقدا إذا ثبت بالقوة القاهرة.',
    ], start=1):
        Article.objects.create(version=v, order=n, label=f'المادة {n}', number=str(n), body=body, eid=f'art_{n}')
    FrenchArticle.objects.create(text_uri=law.akn_uri, order=3, label='Article 3', number='3',
                                 body="Le débiteur ne répond pas en cas de force majeure.")
    rebuild(log=lambda m: None)
    return law


@pytest.fixture(autouse=True)
def every_article(monkeypatch):
    """Every article found shown under its text, not the first two: the tests read which are found."""
    from apps.search.services.search import query
    monkeypatch.setattr(query, 'PER_TEXT', 20)


def _found(r):
    return {a['path'].rsplit('/', 1)[1] for x in r['results'] for a in x['articles']}


@needs_bm25
@pytest.mark.django_db
def test_a_quoted_word_is_that_word_and_not_its_stem(api, corpus):
    assert _found(api.get('/api/search/', {'q': 'العقد'}).json()) >= {'art_1', 'art_2'}
    # «العقد» itself, and with «و» on its front; never «عقد», «العقدة» or «معقدا».
    r = api.get('/api/search/', {'q': '"العقد"'}).json()
    assert (r['understood_as'], r['exact'], _found(r)) == ('exact', ['العقد'], {'art_1', 'art_6'})
    # Nothing stands above words asked as typed: no topic, door or gloss.
    assert (r['topics'], r['doors'], r['said'], r['answer']) == ([], [], [], None)


@needs_bm25
@pytest.mark.django_db
def test_quoted_words_are_found_side_by_side_and_in_order(api, corpus):
    assert 'art_4' in _found(api.get('/api/search/', {'q': 'القوة القاهرة'}).json())
    # «القوةُ القاهرة» (a haraka does not count), «للقوة القاهرة», «بالقوة القاهرة»; never the two words apart.
    r = api.get('/api/search/', {'q': '«القوة القاهرة»'}).json()
    assert _found(r) == {'art_3', 'art_5', 'art_7'}
    # The snippet marks the phrase as the article writes it, and only it.
    snippets = {a['path'].rsplit('/', 1)[1]: [s['t'] for s in a['snippet'] if s['hit']] for x in r['results'] for a in x['articles']}
    assert snippets['art_3'] == ['القوةُ', 'القاهرة'] and snippets['art_7'] == ['بالقوة', 'القاهرة.']
    # A front the index keeps apart («بقوة» is not «قوة» there) is found too, and a front on a later word is not.
    assert _found(api.get('/api/search/', {'q': '"قوة قاهرة"'}).json()) == {'art_5'}
    assert _found(api.get('/api/search/', {'q': '"المدين القوة القاهرة"'}).json()) == set()
    # Its official French holds a phrase in Latin letters.
    assert _found(api.get('/api/search/', {'q': '"force majeure"'}).json()) == {'art_3'}
    assert _found(api.get('/api/search/', {'q': '"majeure force"'}).json()) == set()


@needs_bm25
@pytest.mark.django_db
def test_quoted_words_found_nowhere_are_not_repaired(api, corpus):
    # Unquoted, a letter off is searched as the law spells it; quoted, it is found as typed or not at all.
    r = api.get('/api/search/', {'q': '"القوة القاهرية"'}).json()
    assert (r['understood_as'], r['texts'], r['repaired'], r['partial']) == ('exact', 0, None, False)


@needs_bm25
@pytest.mark.django_db
def test_find_in_a_text_reads_quotes_as_the_search_does(api, corpus):
    # The phrase comes back as each article writes it, for the law page to light whole.
    r = api.get('/api/search/in/', {'path': '/ma/loi/12-26', 'q': '"القوة القاهرة"'}).json()
    assert (r['count'], [a['eid'] for a in r['articles']]) == (3, ['art_3', 'art_5', 'art_7'])
    assert r['words'] == ['القوةُ القاهرة', 'للقوة القاهرة', 'بالقوة القاهرة']
    r = api.get('/api/search/in/', {'path': '/ma/loi/12-26', 'q': '"العقد"'}).json()
    assert [a['eid'] for a in r['articles']] == ['art_1', 'art_6']
    # The law page's marks: any of the words, the quoted ones as typed.
    r = api.get('/api/search/in/', {'path': '/ma/loi/12-26', 'q': '"العقد" التنفيذ', 'any': '1'}).json()
    assert [a['eid'] for a in r['articles']] == ['art_1', 'art_3', 'art_6']


@needs_bm25
@pytest.mark.django_db
def test_a_phrase_whose_stem_fills_every_entry_read_is_read_again_by_its_letters(api, corpus, monkeypatch):
    # «"النفقة"» shares its stem with «نفقات»: 9,250 articles here, past the LIMIT read. Read again among the entries
    # whose words hold its letters, the exact ones are all there.
    from apps.search.services.search import bm25, query
    monkeypatch.setattr(bm25, 'LIMIT', 2)
    monkeypatch.setattr(query, 'LIMIT', 2)
    r = api.get('/api/search/', {'q': '"العقد"'}).json()
    assert _found(r) == {'art_1', 'art_6'}
