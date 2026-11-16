"""The doubtful words of «ساهم» (/open-source): the figures, one word at a time, an answer, the printed line. Public, no
sign-in, nothing about the person kept."""
from datetime import timedelta

import pytest
from django.utils import timezone
from PIL import Image

from apps.opendata.throttles import ScopedRate
from apps.quality.models import Answer, Suspect
from apps.quality.services import words
from apps.quality.tests.words_helpers import page_with, placed, suspect

pytestmark = pytest.mark.django_db
WORDS = '/api/quality/words/'
NEXT = '/api/quality/words/next/'


@pytest.fixture
def page():
    return page_with()


def answer(api, pk, says='suggestion', **kw):
    return api.post(f'{WORDS}{pk}/', {'says': says}, format='json', **kw)


def test_the_figures_count_what_there_is_to_settle(api, page, settings, django_assert_num_queries):
    settings.WORD_ANSWERS = 3
    ready = placed(page)
    placed(page, 'جدار', 'حدار', asked=3)                              # answered enough: settled, not ready
    suspect(page, 'بمكتس', 'بمكنس', 'معه بمكتس ببطحة', place={})       # looked for, not found: a word, not ready
    suspect(page, 'الحيزة', 'الخبزة', 'الحيزة', signal='rare')        # not looked for yet
    suspect(page, 'شعباeffective', '', 'شعباeffective', signal='glued')   # not askable
    suspect(page, 'سواء', 'سواء', 'سواء', signal='rare')               # its suggestion is its word
    placed(page, 'مرة', 'مره', status='rejected', asked=4)              # decided: no longer counted
    Answer.objects.create(suspect=ready, says='word')
    old = Answer.objects.create(suspect=ready, says='word')
    Answer.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=2))
    with django_assert_num_queries(2):
        r = api.get(WORDS)
    assert r.status_code == 200 and r['Cache-Control'] == 'public, max-age=60'
    assert r.json() == {'words': 4, 'ready': 1, 'settled': 1, 'answers': 2, 'today': 1}


def test_a_word_comes_with_its_two_readings_its_line_and_its_page(api, page, django_assert_num_queries):
    s = placed(page)
    with django_assert_num_queries(1):
        r = api.get(NEXT)
    assert r.status_code == 200 and r['Cache-Control'] == 'no-store'
    first, second = ({'key': 'word', 'text': 'خيط'}, {'key': 'suggestion', 'text': 'حيط'})
    assert r.json() == {'word': {
        'id': s.pk,
        'readings': [first, second] if s.pk % 2 == 0 else [second, first],
        'before': 'ارا حدودها شمالا وشرقا', 'after': 'ابن التنيجي وقبلة وغربا',
        'strip': {'url': f'/api/quality/words/{s.pk}/strip/', 'width': 400, 'height': 120,
                  'mark': {'x': 0.4, 'w': 0.1975}, 'line': {'y': 0.3333, 'h': 0.3333}},
        'source': {'issue': {'number': 1432, 'suffix': '', 'date': '1940-04-05'}, 'page': 512,
                   'document_id': page.document_id, 'page_index': 3, 'language': 'ar'}}}


def test_the_order_of_the_readings_is_fixed_by_the_id(page):
    one, two = placed(page), placed(page, 'جدار', 'حدار')
    for s in (one, two):
        keys = [r['key'] for r in words.one([x.pk for x in (one, two) if x != s])['readings']]
        assert keys == (['word', 'suggestion'] if s.pk % 2 == 0 else ['suggestion', 'word'])


def test_a_word_on_a_page_of_no_issue_and_a_line_without_its_word(page):
    page.document.issue.delete()
    s = placed(page, place={'box': [0.1, 0.1, 0.4, 0.15], 'mark': None, 'size': [1596, 2000]})
    w = words.one([])
    assert w['id'] == s.pk and w['strip']['mark'] is None and w['source']['issue'] is None
    assert w['strip']['line'] is None            # placed before a word's own line was kept


def test_the_least_asked_word_comes_first_and_none_named_in_not(api, page, settings):
    settings.WORD_ANSWERS = 3
    twice = placed(page, asked=2)
    never = placed(page, 'جدار', 'حدار')
    once = placed(page, 'سور', 'سود', asked=1)
    assert api.get(NEXT).json()['word']['id'] == never.pk
    assert api.get(NEXT, {'not': f'{never.pk}'}).json()['word']['id'] == once.pk
    assert api.get(NEXT, {'not': f'{never.pk},x,{once.pk},²,-3'}).json()['word']['id'] == twice.pk
    assert api.get(NEXT, {'not': f'{never.pk},{once.pk},{twice.pk}'}).json() == {'word': None}
    assert words.skipped(','.join(str(i) for i in range(500))) == list(range(100))       # a hundred at most


def test_equals_are_given_at_random(page):
    pks = {placed(page, f'كلمة{i}', f'كلمه{i}').pk for i in range(6)}
    assert len({words.one([])['id'] for _ in range(60)}) > 1 and {words.one([])['id'] for _ in range(5)} <= pks


def test_a_word_answered_enough_or_decided_or_not_placed_is_not_asked(api, page, settings):
    settings.WORD_ANSWERS = 3
    placed(page, asked=3)
    placed(page, 'جدار', 'حدار', status='confirmed')
    suspect(page, 'سور', 'سود', 'سور', place={})
    suspect(page, 'باب', 'ناب', 'باب')
    assert api.get(NEXT).json() == {'word': None}


def test_an_answer_is_kept_with_nothing_about_the_person(api, page):
    s = placed(page)
    r = answer(api, s.pk, 'neither', HTTP_X_FORWARDED_FOR='196.200.1.1')
    assert r.status_code == 201 and r.json() == {'ok': True}
    s.refresh_from_db()
    assert s.asked == 1
    kept = Answer.objects.values().get()
    assert set(kept) == {'id', 'suspect_id', 'says', 'created_at'} and kept['says'] == 'neither'
    # Past WORD_ANSWERS a late answer still counts: the word had been given before its third answer came.
    Suspect.objects.filter(pk=s.pk).update(asked=3)
    assert answer(api, s.pk, 'unclear').status_code == 201 and Suspect.objects.get().asked == 4


def test_a_word_that_left_the_open_state_keeps_its_answers_and_is_refused(api, page):
    s = placed(page)
    answer(api, s.pk, 'suggestion')
    Suspect.objects.filter(pk=s.pk).update(status='confirmed')
    assert api.get(NEXT).json() == {'word': None}
    r = answer(api, s.pk)
    assert r.status_code == 404 and r.json() == {'errors': [{'field': 'word', 'code': 'not_found'}]}
    assert Answer.objects.count() == 1


def test_answers_that_are_refused(api, page):
    s = placed(page)
    unplaced = suspect(page, 'جدار', 'حدار', 'جدار', place={})
    for says in ('maybe', '', None, 3, ['word']):
        r = api.post(f'{WORDS}{s.pk}/', {'says': says}, format='json')
        assert r.status_code == 400 and r.json() == {'errors': [{'field': 'says', 'code': 'invalid'}]}
    assert api.post(f'{WORDS}{s.pk}/', ['word'], format='json').status_code == 400
    assert answer(api, unplaced.pk).status_code == 404
    assert answer(api, 10**6).status_code == 404 and answer(api, 10**30).status_code == 404
    # JSON only: a form on another site cannot answer in its visitors' names.
    r = api.post(f'{WORDS}{s.pk}/', {'says': 'word'})
    assert r.status_code == 415 and r.json()['errors'][0] == {'field': 'body', 'code': 'unsupported_media_type'}
    assert Answer.objects.count() == 0 and Suspect.objects.get(pk=s.pk).asked == 0


def test_an_answer_is_two_queries_in_one_transaction(api, page, django_assert_num_queries):
    s = placed(page)
    with django_assert_num_queries(4):              # the transaction's savepoint and release, the update, the insert
        assert answer(api, s.pk).status_code == 201


def test_the_doors_have_their_limits(api, page, monkeypatch):
    s = placed(page)
    monkeypatch.setitem(ScopedRate.THROTTLE_RATES, 'words', '2/min')
    monkeypatch.setitem(ScopedRate.THROTTLE_RATES, 'words_read', '2/min')
    assert [answer(api, s.pk).status_code for _ in range(3)] == [201, 201, 429]
    assert [api.get(NEXT).status_code for _ in range(3)] == [200, 200, 429]
    assert api.get(NEXT).json() == {'errors': [{'field': 'request', 'code': 'throttled'}]}
    assert Suspect.objects.get().asked == 2


def test_the_strip_is_cut_from_the_render_once_and_kept(api, page, settings, tmp_path, django_assert_max_num_queries):
    settings.CORPUS_DIR = tmp_path
    s = placed(page)
    render = tmp_path / 'renders' / page.document.sha256[:16] / '0003-1596.png'
    render.parent.mkdir(parents=True)
    Image.new('L', (1596, 2000), 255).save(render)
    with django_assert_max_num_queries(1):
        r = api.get(f'{WORDS}{s.pk}/strip/')
    assert r.status_code == 200 and r['Content-Type'] == 'image/webp' and r['Cache-Control'] == 'public, max-age=86400'
    kept = list((tmp_path / 'drawn' / 'strips').iterdir())
    assert len(kept) == 1
    with Image.open(kept[0]) as im:
        assert (im.format, im.size) == ('WEBP', (400, 120))         # the size the word's answer gives
    render.unlink()
    assert api.get(f'{WORDS}{s.pk}/strip/').status_code == 200      # kept: the render is no longer needed


def test_no_strip_without_a_place_or_a_render(api, page, settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    s = placed(page)
    unplaced = suspect(page, 'جدار', 'حدار', 'جدار', place={})
    for pk in (s.pk, unplaced.pk, 10**6, 10**30):
        r = api.get(f'{WORDS}{pk}/strip/')
        assert r.status_code == 404 and r.json() == {'errors': [{'field': 'request', 'code': 'not_found'}]}


def test_the_strip_is_not_a_page_of_the_days_reading(api, page, settings, tmp_path, monkeypatch):
    from apps.corpus.services import reading
    settings.CORPUS_DIR = tmp_path
    s = placed(page)
    render = tmp_path / 'renders' / page.document.sha256[:16] / '0003-1596.png'
    render.parent.mkdir(parents=True)
    Image.new('L', (1596, 2000), 255).save(render)
    monkeypatch.setattr(reading, 'spend', lambda *a, **k: pytest.fail('a strip counted as reading'))
    assert api.get(f'{WORDS}{s.pk}/strip/').status_code == 200
