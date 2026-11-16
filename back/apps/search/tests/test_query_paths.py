"""The ways a query is read before and after its words (the search's docstring, steps 1 to 5) on ParadeDB: a constitution
by its year, a law's number typed the wrong way round, Darija in Latin letters, a code named beside quoted words, what an
everyday word means alone, a word one letter away, a question inside a named code with quotes, the lemmas (B4), the
everyday drafts grounded in the index, and the official French beside the answers on a French page."""
import json
from datetime import date

import pytest
from django.core.management import call_command
from django.db import connection

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.search.models import SearchEntry
from apps.search.services import index, lemmas, vocab
from apps.search.services.index import rebuild
from apps.search.services.search.beside import topic_words
from apps.search.services.search.query import search
from apps.translations.models import FrenchArticle

pytestmark = [pytest.mark.django_db,
              pytest.mark.skipif(connection.vendor != 'postgresql', reason='BM25 needs ParadeDB (TEST_DATABASE_URL)')]


def text(uri, kind, title, signed, bodies, labels=None):
    number = uri.rsplit('/', 1)[1]
    t = Text.objects.create(akn_uri=uri, type=kind, number=number, number_as_printed=number.replace('-', '.'), title_ar=title,
                            signed_on=signed)
    v = Version.objects.create(text=t, language='ar', valid_from=signed, consolidation=Consolidation.AS_PUBLISHED)
    for i, body in enumerate(bodies, 1):
        n = (labels or {}).get(i, str(i))
        Article.objects.create(version=v, order=i, label=f'المادة {n}', number=n, eid=f'art_{n}', body=body)
    return t


@pytest.fixture
def corpus():
    text('/akn/ma/act/loi/91-97', 'law', 'القانون رقم 91.97 المتعلق بعقود الكراء', date(2013, 1, 1),
         ['يؤدي المكتري الكراء في أجله.', 'يمكن الإفراغ بحكم.', 'يتم الإفراغ داخل مدة ثلاثة أشهر.', 'تجب النفقة على الأب.',
          'تبرم العقود كتابة.', 'ينتهي العقد بانتهاء مدته.'])
    text('/akn/ma/act/dahir/1-96-157', 'constitution', 'ظهير شريف رقم 1.96.157 بتنفيذ نص الدستور المراجع', date(1996, 10, 7),
         ['المغرب ملكية دستورية.'])
    text('/akn/ma/act/dahir/1-11-91', 'constitution', 'ظهير شريف رقم 1.11.91 بتنفيذ نص الدستور', date(2011, 7, 29),
         ['نظام الحكم بالمغرب نظام ملكية دستورية.', 'تظل العربية اللغة الرسمية للدولة.'])
    rebuild(log=lambda m: None)


def paths(r: dict) -> list[str]:
    return [a['path'] for x in r['results'] for a in x['articles']]


def test_a_constitution_named_with_a_year_is_the_one_in_force_that_year(corpus):
    r = search('دستور 1996', log=False)
    assert r['understood_as'] == 'citation' and r['jump']['state'] == 'found'
    assert r['jump']['text']['path'] == '/ma/dahir/1-96-157' and r['jump']['name'] == r['jump']['text']['name']
    assert search('الدستور', log=False)['jump']['text']['path'] == '/ma/dahir/1-11-91'


def test_a_laws_number_typed_the_wrong_way_round_is_opened_and_said(corpus):
    r = search('القانون رقم 97.91', log=False)
    assert (r['repaired'], r['jump']['state'], r['jump']['text']['path']) == ('91.97', 'found', '/ma/loi/91-97')
    assert search('القانون رقم 91.97', log=False)['repaired'] is None
    # Neither way round a law the site holds: said as not held here, nothing repaired.
    r = search('القانون رقم 98.89', log=False)
    assert r['repaired'] is None and r['jump']['state'] == 'not_in_corpus'


def test_darija_in_latin_letters_is_searched_in_arabic_and_said(corpus):
    r = search('kra', log=False)
    assert (r['understood_as'], r['arabizi'], r['repaired'], r['query']) == ('arabizi', 'الكراء', 'الكراء', 'kra')
    assert paths(r)[:1] == ['/ma/loi/91-97/art_1']


def test_quoted_words_beside_a_code_not_in_the_corpus_are_searched_without_its_name(corpus):
    r = search('مدونة الأسرة "النفقة"', log=False)
    assert r['jump']['state'] == 'not_in_corpus' and r['jump']['citation']['code'] == 'family'
    assert r['understood_as'] == 'citation' and paths(r) == ['/ma/loi/91-97/art_4']


def test_what_an_everyday_word_means_is_searched_alone_when_the_question_finds_nothing(corpus, tmp_path, monkeypatch):
    everyday = tmp_path / 'everyday.json'
    everyday.write_text(json.dumps({'entries': [{'typed': ['الكونطرادو'], 'kind': 'darija', 'means': ['الإفراغ']}]},
                                   ensure_ascii=False))
    monkeypatch.setattr(vocab, 'FILE', everyday)
    vocab.entries.cache_clear()
    try:
        r = search('واش الكونطرادو قانوني', log=False)
    finally:
        vocab.entries.cache_clear()
    assert (r['understood_as'], r['repaired']) == ('everyday', 'الإفراغ')
    assert paths(r) == ['/ma/loi/91-97/art_2', '/ma/loi/91-97/art_3']


def test_a_word_one_letter_from_the_laws_is_put_right_and_said(corpus, settings):
    # The index's counts as a whole corpus has them: «الإفراغ» common enough to be what «الإفراع» meant.
    (settings.CORPUS_DIR / index.TERMS).write_text(json.dumps({'افراغ': 50, 'كراء': 40}, ensure_ascii=False))
    index.term_counts.cache_clear()
    r = search('الإفراع', log=False)
    assert (r['understood_as'], r['repaired']) == ('spelling', 'الافراغ') and paths(r)[0] == '/ma/loi/91-97/art_2'


def test_quoted_words_inside_a_named_code_are_searched_there(corpus, settings):
    settings.SEARCH_INSIDE = True
    r = search('الدستور "اللغة الرسمية"', log=False)
    assert r['jump']['text']['path'] == '/ma/dahir/1-11-91' and r['understood_as'] == 'citation'
    assert paths(r) == ['/ma/dahir/1-11-91/art_2']
    # The code's name alone: nothing to search inside it, and its own articles found by its title are not set aside.
    r = search('الدستور', log=False)
    assert r['jump']['text']['path'] == '/ma/dahir/1-11-91' and '/ma/dahir/1-11-91/art_1' in paths(r)


def test_a_text_whose_title_row_left_the_index_is_not_shown(corpus):
    SearchEntry.objects.filter(kind='text', text_path='/ma/loi/91-97').delete()
    r = search('الإفراغ', log=False)
    assert r['texts'] == 1 and r['results'] == []


def test_a_broken_plural_meets_its_singular_through_the_lemmas(corpus, settings):
    # «العقود» (art. 5) and «العقد» (art. 6) are two stems: each finds its own article.
    assert paths(search('عقد', log=False)) == ['/ma/loi/91-97/art_6']
    (settings.CORPUS_DIR / lemmas.FILE).write_text(json.dumps({'lemmas': {'عقود': 'عقد'}}, ensure_ascii=False))
    lemmas.table.cache_clear()
    rebuild(log=lambda m: None)
    assert paths(search('العقود', log=False)) == ['/ma/loi/91-97/art_5']      # read only when SEARCH_LEMMAS is set
    settings.SEARCH_LEMMAS = True
    # The article's words and the question's as their lemmas: the plural finds the singular and the singular the plural.
    for q in ('عقد', 'العقود'):
        assert sorted(paths(search(q, log=False))) == ['/ma/loi/91-97/art_5', '/ma/loi/91-97/art_6'], q


def test_the_everyday_drafts_are_counted_against_the_index(corpus, settings):
    drafts = settings.CORPUS_DIR / 'reports' / 'vocab' / 'drafts.json'
    drafts.parent.mkdir(parents=True)
    drafts.write_text(json.dumps({'drafts': [
        {'typed': 'الإفراغ', 'kind': 'darija', 'means': ['الإفراغ', 'الإفراغ بحكم', 'شيء لا يوجد', '...'], 'sure': True},
        {'typed': 'كلمة', 'kind': 'darija', 'means': ['شيء لا يوجد', 'الطرد'], 'sure': False}]}, ensure_ascii=False))
    from io import StringIO
    out = StringIO()
    call_command('ground_vocab', stdout=out)
    data = json.loads(drafts.read_text())['drafts']
    assert [(d['found'], d['typed_found']) for d in data] == [([2, 1, 0, 0], 2), ([0, 0], 0)]     # «...» is no word
    assert out.getvalue().strip() == '1 of 2 drafts have a meaning the corpus uses'


def test_a_french_page_shows_the_official_french_of_the_articles_and_the_doors(api, corpus, settings):
    settings.SHOW_DRAFTS = True        # the doors are drafts while developing
    FrenchArticle.objects.create(text_uri='/akn/ma/act/loi/91-97', order=2, label='Article 2', number='2',
                                 body="L'expulsion est prononcée par jugement.")
    r = api.get('/api/search/', {'q': 'الإفراغ', 'lang': 'fr'}).json()
    shown = {a['path']: a.get('french') for x in r['results'] for a in x['articles']}
    assert shown['/ma/loi/91-97/art_3'] is None
    assert shown['/ma/loi/91-97/art_2']['label'] == 'Article 2'
    assert ''.join(s['t'] for s in shown['/ma/loi/91-97/art_2']['snippet']) == "L'expulsion est prononcée par jugement."
    assert 'french' not in api.get('/api/search/', {'q': 'الإفراغ'}).json()['results'][0]['articles'][0]
    # The radar's door: the road code's articles it rests on, with their French.
    road = text('/akn/ma/act/loi/52-05', 'law', 'القانون رقم 52.05 المتعلق بمدونة السير على الطرق', date(2010, 2, 11),
                ['تسجل المخالفات بالرادار.', 'تحرر المحاضر.'], labels={1: '197', 2: '200'})
    FrenchArticle.objects.create(text_uri=road.akn_uri, order=197, label='Article 197', number='197',
                                 body='Les infractions sont constatées par radar.')
    r = api.get('/api/search/', {'q': 'شدني الرادار', 'lang': 'fr'}).json()
    doors = {d['path']: d.get('french') for d in r['door_articles']}
    assert doors == {'/ma/loi/52-05/art_197': {'label': 'Article 197', 'body': 'Les infractions sont constatées par radar.'},
                     '/ma/loi/52-05/art_200': None}
    # Nothing found: nothing to look up.
    assert api.get('/api/search/', {'q': 'ثثثثث', 'lang': 'fr'}).json()['results'] == []


def test_a_topic_not_known_has_no_words():
    assert topic_words('no-such-topic') == []


def test_a_worker_reads_what_a_search_needs_before_its_first_reader(corpus):
    # N12 of the read-and-trusted review: the titles, the French words and the index's counts read once, nothing logged.
    from apps.search.models import SearchLog
    from apps.search.services import spelling
    from apps.search.services.search import suggestions
    spelling.french_words.cache_clear()
    index.term_counts.cache_clear()
    suggestions.warm()
    assert spelling.french_words.cache_info().currsize == 1 and index.term_counts.cache_info().currsize == 1
    assert not SearchLog.objects.exists()
