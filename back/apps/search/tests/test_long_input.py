"""OP3 and OP4 of the open-source audit: a search view reads at most a stated length of what it is sent, a word longer
than any word of Darija is not spelled, and a suggestion asks three letters, reads a bounded number of titles and is
worked out once a generation."""
import time

import ma_law
import pytest
from django.core.cache import caches
from django.test import override_settings

from apps.corpus.services import generation
from apps.search.api import views
from apps.search.models import SearchEntry
from apps.search.services import search, spelling
from apps.search.services.search import titles

pytestmark = pytest.mark.django_db

LONG = 'كراء المحلات ' * 400                     # 5,200 characters, far past any question
LATIN = '3' + 'a' * 3999                         # a request line's worth of one word


def test_every_search_view_cuts_the_question_before_reading_it(api, monkeypatch):
    read = []

    def keep(name, answer):
        return lambda q, *a, **k: read.append((name, len(q))) or answer

    monkeypatch.setattr(views, 'search', keep('search', {'query': ''}))
    monkeypatch.setattr(views.topics, 'matching', keep('topics', []))
    monkeypatch.setattr(views.kit, 'matching', keep('doors', []))
    monkeypatch.setattr(views.finder, 'door', keep('place', None))
    monkeypatch.setattr(spelling, 'arabizi', keep('arabizi', None))
    monkeypatch.setattr(views, 'suggest', keep('suggest', {}))
    monkeypatch.setattr(views, 'find_in', lambda path, q, **k: read.append(('find_in', len(path), len(q))) or {})
    for q in (LONG, LATIN):
        assert api.get('/api/search/', {'q': q, 'page': '9' * 3000, 'from': '20255', 'type': 'law,' * 1000}).status_code == 200
        assert api.get('/api/search/people/', {'q': q}).status_code == 200
        assert api.get('/api/search/suggest/', {'q': q}).status_code == 200
        assert api.get('/api/search/in/', {'path': '/ma/' + 'a' * 3000, 'q': q}).status_code == 200
    names = {r[0] for r in read}
    assert names == {'search', 'topics', 'doors', 'place', 'arabizi', 'suggest', 'find_in'}
    assert all(n <= search.QUERY_MOST for r in read for n in r[1:])
    assert max(n for name, n, *_ in read if name == 'suggest') == search.TYPED_MOST
    assert max(r[1:] for r in read if r[0] == 'find_in') == (views.ADDRESS_MOST, search.TYPED_MOST)


def test_a_page_a_year_and_a_type_filter_are_read_in_their_own_length():
    assert views._page('9' * 3000) == 1 and views._page('3') == 3 and views._page('0') == 1 and views._page(None) == 1
    assert views._year('20255') is None and views._year('2025') == 2025 and views._year('1899') is None


def test_a_citations_words_are_cut_before_they_are_resolved(api, monkeypatch):
    seen = []
    monkeypatch.setattr(views, 'resolve_many', lambda cs, **asked: seen.extend(cs) or [])
    citations = [{'kind': 'article', 'raw': 'ف ' * 5000, 'article': '5' * 5000, 'start': 0, 'end': 3}]
    assert api.post('/api/search/resolve/', {'citations': citations}, format='json').status_code == 200
    assert len(seen[0]['raw']) == len(seen[0]['article']) == views.WORD_MOST and seen[0]['start'] == 0


def test_a_word_longer_than_any_of_darija_stays_as_typed(monkeypatch):
    spelled = []
    monkeypatch.setattr(spelling.ma_law, 'arabizi_spellings', lambda w, n: spelled.append(w) or ['قانون'])
    word = '9anoun' * 6                                  # 36 letters
    assert spelling.word(word) == word and spelled == []


def test_a_word_longer_than_any_of_the_law_is_no_slip(monkeypatch):
    """Nor is a word of 60 Arabic letters one letter away from a word of the index: its edits cost the square of its
    length."""
    word = 'بتب' * 20
    slip = word[:-1] + 'ت'
    monkeypatch.setattr(spelling, 'term_counts', lambda: {ma_law.stem(slip): 1000})
    assert spelling.correct(word) is None
    monkeypatch.setattr(spelling, 'term_counts', lambda: {ma_law.stem(word[:14] + 'ت'): 1000})
    assert spelling.correct(word[:15]) == word[:14] + 'ت'


def test_a_long_question_in_latin_letters_is_read_at_once(api):
    assert api.get('/api/search/people/', {'q': 'wach 3la'}).status_code == 200     # the topics' words read once
    started = time.perf_counter()
    assert api.get('/api/search/people/', {'q': f'wach {LATIN}'}).status_code == 200
    assert time.perf_counter() - started < 5


def _titles(monkeypatch, *folded: str):
    """The titles the walk reads, in this order, as the kept table gives them."""
    rows = [(i, f'/ma/loi/{i}', title, 1.0, 2000) for i, title in enumerate(folded)]
    blob = '\n'.join(r[2] for r in rows)
    starts, at = [], 0
    for r in rows:
        starts.append(at)
        at += len(r[2]) + 1
    monkeypatch.setattr(titles, '_title_rows', lambda: (rows, blob, starts))
    monkeypatch.setattr(titles, '_shelf_paths', list)


def test_a_suggestion_asks_three_letters(api, monkeypatch):
    """Two letters walked every «ال» of 192,000 titles, seconds of a worker. A number of two digits still opens the
    famous articles it starts («49»)."""
    monkeypatch.setattr(titles, '_title_rows', lambda: (_ for _ in ()).throw(AssertionError('the titles were read')))
    for q in ('ال', 'رق', 'ق م'):
        r = api.get('/api/search/suggest/', {'q': q}).json()
        assert r['texts'] == r['topics'] == r['guides'] == r['words'] == []
    from apps.search.services import famous
    monkeypatch.setattr(famous, 'suggestions', lambda q: [{'article': {'path': f'/ma/code/family/art_{q}'}}])
    assert api.get('/api/search/suggest/', {'q': '49'}).json()['citations'] == [{'article': {'path': '/ma/code/family/art_49'}}]


def test_a_suggestion_reads_a_bounded_number_of_titles(monkeypatch):
    _titles(monkeypatch, *[f'قرار لوزير الفلاحه رقم {n}' for n in range(10)], 'قرار لوزير الفلاحه رقم 10 بالصيد البحري')
    assert len(titles._titles(['قرار'], 20)) == 11
    monkeypatch.setattr(titles, 'TITLES_READ', 4)
    assert titles._titles(['قرار'], 20) == [(f'/ma/loi/{n}',) for n in (3, 2, 1, 0)]
    # A rarer word typed beside it is read instead, whole: the title that holds both is found past the first four.
    assert titles._titles(['الفلاحه', 'صيد'], 20) == [('/ma/loi/10',)]


def test_the_walk_meets_the_laws_before_the_orders_and_the_newest_first():
    rows = [('order', 0.5, 2020), ('law', 2.0, 1999), ('law', 2.0, 2021), ('decree', 1.0, None), ('decree', 1.0, 2010)]
    for n, (kind, weight, year) in enumerate(rows):
        SearchEntry.objects.create(kind=SearchEntry.Kind.TEXT, text_path=f'/ma/{kind}/{n}', path=f'/ma/{kind}/{n}',
                                   title=kind, title_folded=kind, weight=weight, year=year)
    assert [r[1] for r in titles._titles_table()] == ['/ma/law/2', '/ma/law/1', '/ma/decree/4', '/ma/decree/3', '/ma/order/0']


KEPT = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'suggest-default'},
        'answers': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'suggest-answers'}}


def test_a_suggestion_is_worked_out_once_a_generation(api, monkeypatch):
    made = []
    monkeypatch.setattr(views, 'suggest', lambda q: made.append(q) or {'query': q, 'texts': [len(made)]})
    with override_settings(CACHES=KEPT):
        caches['answers'].clear()
        first = api.get('/api/search/suggest/', {'q': ' كراء '}).json()
        assert api.get('/api/search/suggest/', {'q': 'كراء'}).json() == first and made == ['كراء']
        assert api.get('/api/search/suggest/', {'q': 'كراء المحل'}).json()['texts'] == [2]
        generation.bump('corpus')
        assert api.get('/api/search/suggest/', {'q': 'كراء'}).json()['texts'] == [3]
        caches['answers'].clear()
