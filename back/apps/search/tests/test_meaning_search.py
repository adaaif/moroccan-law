"""Search by meaning (B7, B8 of the search plan; N11 of the read-and-trusted review) on ParadeDB and pgvector: the question's vector comes from the model
server while the words are searched (the model's third-party pieces stood in, model.py), the nearest passages are fused
with BM25's hits, each article says how it was found, a question the words do not find is answered by meaning alone,
and what meaning alone found comes after the words' texts, as the settings say."""
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection

from apps.corpus.models import Article, Consolidation, Status, Text, Version
from apps.search.models import SearchEntry, SearchLog, SearchPassage
from apps.search.services import meaning
from apps.search.services.index import rebuild
from apps.search.services.search.query import search
from apps.search.tests.model import vector

pytestmark = [pytest.mark.django_db,
              pytest.mark.skipif(connection.vendor != 'postgresql', reason='BM25 and pgvector need ParadeDB (TEST_DATABASE_URL)')]


def text(uri, kind, title, year, bodies, **more):
    number = uri.rsplit('/', 1)[1]
    t = Text.objects.create(akn_uri=uri, type=kind, number=number, number_as_printed=number.replace('-', '.'), title_ar=title,
                            signed_on=date(year, 1, 1), **more)
    v = Version.objects.create(text=t, language='ar', valid_from=date(year, 2, 1), consolidation=Consolidation.AS_PUBLISHED)
    for i, body in enumerate(bodies, 1):
        Article.objects.create(version=v, order=i, label=f'المادة {i}', number=str(i), eid=f'art_{i}', body=body)
    return t


@pytest.fixture
def corpus(served, settings):
    """A lease law whose words say «الإفراغ»; a decree and an older, repealed law that say it as «إخلاء», which only
    meaning reads as the same thing. Every article embedded; meaning on."""
    text('/akn/ma/act/loi/91-97', 'law', 'القانون رقم 91.97 المتعلق بعقود الكراء', 2013,
         ['يؤدي المكتري الكراء في أجله.', 'يمكن الإفراغ بحكم.', 'يتم الإفراغ داخل مدة ثلاثة أشهر من تاريخ الإنذار.'])
    text('/akn/ma/act/decret/2-91-1', 'decree', 'مرسوم رقم 2.91.1', 2014, ['إخلاء إخلاء.'])
    text('/akn/ma/act/loi/92-97', 'law', 'القانون رقم 92.97', 2002, ['إخلاء العقار المشترك.'], status=Status.REPEALED)
    rebuild(log=lambda m: None)
    call_command('embed_passages', '--scope', 'all', stdout=StringIO())
    settings.SEARCH_MEANING = True
    settings.SEARCH_MEANING_AFTER = ''
    settings.SEARCH_MEANING_FLOOR = 0.0


def found(r: dict) -> list[tuple]:
    return [(x['text']['path'], [(a['path'].rsplit('/', 1)[1], a['found_by']) for a in x['articles']]) for x in r['results']]


def test_a_question_the_words_do_not_find_is_answered_by_meaning_alone_and_says_so(api, corpus):
    # Another model's passage, as near the question as can be, is no answer for this model's question.
    SearchPassage.objects.create(path='/ma/loi/92-97/art_1', text_path='/ma/loi/92-97', model='bge-m3-padded', part=0,
                                 lang='ar', text_type='law', year=2002, in_force=False, vector=vector('السكنى'))
    r = api.get('/api/search/', {'q': 'السكنى', 'repealed': '1'}).json()
    assert r['understood_as'] == 'meaning' and r['partial'] is False and r['texts'] == 3 and r['articles'] == 5
    assert found(r)[0] == ('/ma/loi/91-97', [('art_1', 'meaning'), ('art_2', 'meaning')])
    assert SearchLog.objects.get(pk=r['log']).understood_as == 'meaning'
    # Without the repealed law's passages unless asked; the years and the types as the words' filters.
    assert [x[0] for x in found(api.get('/api/search/', {'q': 'السكنى'}).json())] == ['/ma/loi/91-97', '/ma/decret/2-91-1']
    assert [x[0] for x in found(api.get('/api/search/', {'q': 'السكنى', 'to': '2013', 'repealed': '1'}).json())] == [
        '/ma/loi/91-97', '/ma/loi/92-97']
    assert [x[0] for x in found(api.get('/api/search/', {'q': 'السكنى', 'from': '2014'}).json())] == ['/ma/decret/2-91-1']
    assert [x[0] for x in found(api.get('/api/search/', {'q': 'السكنى', 'type': 'decree'}).json())] == ['/ma/decret/2-91-1']


def test_the_floor_holds_only_beside_what_the_words_found(api, corpus, settings):
    # N11: nothing near enough to «السكنى» to pass a floor of 0.99, yet with no word found, meaning answers as it is.
    settings.SEARCH_MEANING_FLOOR = 0.99
    r = api.get('/api/search/', {'q': 'السكنى'}).json()
    assert r['understood_as'] == 'meaning' and found(r)[0] == ('/ma/loi/91-97', [('art_1', 'meaning'), ('art_2', 'meaning')])
    # Beside what the words found, the same floor leaves meaning's own articles out.
    assert found(api.get('/api/search/', {'q': 'الإفراغ'}).json()) == [('/ma/loi/91-97', [('art_2', 'both'), ('art_3', 'both')])]


def test_words_and_meaning_are_fused_and_meaning_alone_comes_after_as_the_settings_say(api, corpus, settings):
    settings.SEARCH_FUSION_WEIGHT = 0.0     # meaning's scores alone: the texts that say «إخلاء» lead
    r = api.get('/api/search/', {'q': 'الإفراغ', 'repealed': '1'}).json()
    assert r['understood_as'] == 'words'
    assert found(r) == [('/ma/decret/2-91-1', [('art_1', 'meaning')]),
                        ('/ma/loi/92-97', [('art_1', 'meaning')]),
                        ('/ma/loi/91-97', [('art_2', 'both'), ('art_3', 'both')])]
    # N11: a decree found by meaning alone comes after the texts the words found ('rules'); every such text ('all').
    settings.SEARCH_MEANING_AFTER = 'rules'
    order = lambda: [x[0] for x in found(api.get('/api/search/', {'q': 'الإفراغ', 'repealed': '1'}).json())]
    assert order() == ['/ma/loi/92-97', '/ma/loi/91-97', '/ma/decret/2-91-1']
    settings.SEARCH_MEANING_AFTER = 'all'
    assert order() == ['/ma/loi/91-97', '/ma/decret/2-91-1', '/ma/loi/92-97']
    # A meaning-only article less alike than the floor is left out beside what the words found (0.63 and 0.33 here).
    settings.SEARCH_MEANING_FLOOR = 0.5
    assert order() == ['/ma/loi/91-97', '/ma/decret/2-91-1']
    # By the default weight, BM25's share: the words' law first.
    settings.SEARCH_MEANING_AFTER, settings.SEARCH_MEANING_FLOOR, settings.SEARCH_FUSION_WEIGHT = '', 0.0, 0.5
    assert order()[0] == '/ma/loi/91-97'


def test_a_passage_whose_article_left_the_index_is_not_an_answer(api, corpus):
    SearchEntry.objects.filter(path='/ma/decret/2-91-1/art_1').delete()
    assert '/ma/decret/2-91-1' not in [x[0] for x in found(api.get('/api/search/', {'q': 'السكنى'}).json())]


def test_with_the_model_server_down_the_words_answer_alone(api, corpus, settings):
    settings.SEARCH_MODEL_URL = 'http://127.0.0.1:9'          # nothing listens there
    r = api.get('/api/search/', {'q': 'الإفراغ'}).json()
    assert found(r) == [('/ma/loi/91-97', [('art_2', 'words'), ('art_3', 'words')])]
    assert api.get('/api/search/', {'q': 'السكنى'}).json()['texts'] == 0


def test_a_text_opened_by_its_number_or_an_article_by_its_citation_stands_alone(api, corpus):
    # HM44 and B8: no decree found by meaning under a law opened by its number, nor under a cited article.
    r = api.get('/api/search/', {'q': 'القانون رقم 91.97'}).json()
    assert r['jump']['text']['path'] == '/ma/loi/91-97' and all(f == 'words' for _, arts in found(r) for _, f in arts)
    r = api.get('/api/search/', {'q': 'المادة 2 من القانون رقم 91.97'}).json()
    assert r['jump']['article']['path'] == '/ma/loi/91-97/art_2' and r['results'] == []


def test_the_answer_box_takes_the_first_article_words_and_meaning_agree_on(corpus, settings):
    # B15: the sentence that answers, the number in bold; only when both found the article. (The page gives the box
    # way to a topic's doors, which «الإفراغ» names: the service's own answer is read here.)
    settings.SEARCH_ANSWER = True
    box = search('ما هي مدة الإفراغ', log=False)['answer']
    assert (box['path'], box['label'], box['page'], box['found_by'], box['amount']) == (
        '/ma/loi/91-97/art_3', 'المادة 3', None, 'both', True)
    assert box['text']['path'] == '/ma/loi/91-97'
    assert [s['t'] for s in box['sentence'] if s['num']] == ['ثلاثة أشهر'] and 'الإفراغ' in [s['t'] for s in box['sentence'] if s['hit']]
    # A question that asks no amount: the sentence, nothing in bold.
    box = search('واش يمكن الإفراغ', log=False)['answer']
    assert box['path'] == '/ma/loi/91-97/art_2' and box['amount'] is False
    assert ''.join(s['t'] for s in box['sentence']) == 'يمكن الإفراغ بحكم.' and not any(s['num'] for s in box['sentence'])
    # A question about an amount whose sentence states none: the sentence, no amount said.
    box = search('شحال يمكن الإفراغ', log=False)['answer']
    assert box['path'] == '/ma/loi/91-97/art_2' and box['amount'] is False
    # Some of the words only: no box, where the same article found by every word has one.
    r = search('واش يمكن الإفراغ بالقوة', log=False)
    assert r['partial'] and r['results'][0]['articles'][0]['path'] == '/ma/loi/91-97/art_2' and r['answer'] is None
    # A text found by its title alone first (none of its articles), and an article with no sentence of its own: no box.
    text('/akn/ma/act/loi/96-97', 'law', 'القانون رقم 96.97 المتعلق بالزرابي', 2015, [])
    text('/akn/ma/act/loi/97-97', 'law', 'القانون رقم 97.97', 2015, ['---'])
    Article.objects.filter(version__text__number='97-97').update(label='تمهيد')
    rebuild(log=lambda m: None)
    call_command('embed_passages', '--scope', 'all', stdout=StringIO())
    r = search('ما هي الزرابي', log=False)
    assert r['results'][0]['text']['path'] == '/ma/loi/96-97' and r['results'][0]['articles'] == [] and r['answer'] is None
    r = search('ما هو التمهيد', log=False)
    assert r['results'][0]['articles'][0]['path'] == '/ma/loi/97-97/art_1' and r['results'][0]['articles'][0]['found_by'] == 'both'
    assert r['answer'] is None
    # Found by the words alone (its passages gone), no box; a few words are not a question; nor a later page.
    assert search('واش يمكن الإفراغ', page=2, log=False)['answer'] is None
    SearchPassage.objects.filter(path='/ma/loi/91-97/art_3').delete()
    assert search('ما هي مدة الإفراغ', log=False)['answer'] is None
    assert search('الإفراغ', log=False)['answer'] is None
    settings.SEARCH_ANSWER = False
    assert search('واش يمكن الإفراغ', log=False)['answer'] is None
    # Nothing found (the model server down, no word in the law): no box.
    settings.SEARCH_ANSWER, settings.SEARCH_MODEL_URL = True, 'http://127.0.0.1:9'
    r = search('ما هي ثثثثث', log=False)
    assert r['results'] == [] and r['answer'] is None


def test_a_question_inside_a_named_code_is_searched_there_by_its_words_and_its_meaning(api, served, settings):
    # C12 of the constitution review, with meaning: the code's articles near the question come with those its words found.
    cons = text('/akn/ma/act/dahir/1-11-91', 'constitution', 'ظهير شريف رقم 1.11.91 بتنفيذ نص الدستور', 2011,
                ['نظام الحكم بالمغرب نظام ملكية دستورية.', 'تظل العربية اللغة الرسمية للدولة.'], status='in_force')
    text('/akn/ma/act/loi/93-97', 'law', 'القانون رقم 93.97', 2016, ['اللغة الرسمية الأمازيغية.'])
    rebuild(log=lambda m: None)
    call_command('embed_passages', '--scope', 'all', stdout=StringIO())
    settings.SEARCH_MEANING, settings.SEARCH_INSIDE = True, True
    r = search('ما هي اللغة الرسمية في الدستور', log=False)
    assert r['jump']['text']['path'] == '/ma/dahir/1-11-91' == cons.akn_uri.replace('/akn/ma/act', '/ma')
    assert found(r) == [('/ma/dahir/1-11-91', [('art_2', 'both'), ('art_1', 'meaning')]),
                        ('/ma/loi/93-97', [('art_1', 'words')])]
    # A question, its first article found both ways, yet the code is said above: no box.
    settings.SEARCH_ANSWER = True
    assert search('ما هي اللغة الرسمية في الدستور', log=False)['answer'] is None
    settings.SEARCH_ANSWER = False
    # The model server gone (a question not asked before, no vector kept): the code's articles its words found, first.
    settings.SEARCH_MODEL_URL = 'http://127.0.0.1:9'
    assert found(search('اللغة الرسمية في الدستور', log=False)) == [
        ('/ma/dahir/1-11-91', [('art_2', 'words')]), ('/ma/loi/93-97', [('art_1', 'words')])]
    # Its own passages alone, measured exactly.
    near = meaning.nearest(vector('اللغة'), types=[], years=(None, None), repealed=True, within='/ma/dahir/1-11-91')
    assert [p for p, _, _ in near] == ['/ma/dahir/1-11-91/art_2', '/ma/dahir/1-11-91/art_1']
