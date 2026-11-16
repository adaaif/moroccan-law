"""«ابحث في هذا النص» (P10 of the polish review): the articles of one text that hold the words, in its order."""
from datetime import date

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version

pytestmark = pytest.mark.django_db


@pytest.fixture
def code():
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/70-03', type='law', number='70-03', title_ar='القانون رقم 70.03 بمثابة مدونة الأسرة')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2004, 2, 5), consolidation=Consolidation.AS_PUBLISHED)
    for order, (number, body) in enumerate([('187', 'نفقة كل إنسان في ماله، إلا ما استثني بمقتضى القانون.'),
                                            ('188', 'لا تجب على الإنسان نفقة غيره إلا بعد أن يكون له مقدار نفقة نفسه.'),
                                            ('190', 'يعتمد في تقدير كل ما يقضى به من نفقة على تصريحات الطرفين.'),
                                            ('191', 'تحدد المحكمة وسائل تنفيذ الحكم.')], start=1):
        Article.objects.create(version=v, order=order, label=f'المادة {number}', number=number, eid=f'art_{number}', body=body)
    return text


def test_a_text_is_searched_inside_in_its_own_order(api, code):
    r = api.get('/api/search/in/', {'path': '/ma/loi/70-03', 'q': 'النفقة'}).json()
    assert r['count'] == 3 and [a['label'] for a in r['articles']] == ['المادة 187', 'المادة 188', 'المادة 190']
    assert r['articles'][0]['path'] == '/ma/loi/70-03/art_187' and any(s['hit'] for s in r['articles'][0]['snippet'])
    # Every word must be there; the question's own words are set aside.
    assert api.get('/api/search/in/', {'path': '/ma/loi/70-03', 'q': 'نفقة الطرفين'}).json()['count'] == 1
    assert api.get('/api/search/in/', {'path': '/ma/loi/70-03', 'q': ''}).json()['count'] == 0


def test_the_articles_that_hold_the_words_side_by_side_come_first(api, code):
    # HM33 of the hard-moment review: «السكن الاجتماعي» in the tax code listed art. 6 first, which holds «السكنية»
    # and «الاجتماعية» apart, and the reader landed on it.
    v = code.versions.get()
    Article.objects.create(version=v, order=5, label='المادة 192', number='192', eid='art_192',
                           body='تقدر نفقة الأولاد مع مراعاة نفقة الطرفين.')
    Article.objects.create(version=v, order=6, label='المادة 193', number='193', eid='art_193',
                           body='تشمل نفقة الأولاد السكنى والتعليم، وتقدر نفقة الطرفين معا.')
    r = api.get('/api/search/in/', {'path': '/ma/loi/70-03', 'q': 'نفقة الأولاد'}).json()
    assert r['count'] == 2 and r['together'] == 2
    r = api.get('/api/search/in/', {'path': '/ma/loi/70-03', 'q': 'الطرفين نفقة'}).json()
    assert [(a['label'], a['together']) for a in r['articles']] == [('المادة 190', False), ('المادة 192', False),
                                                                    ('المادة 193', False)]
    r = api.get('/api/search/in/', {'path': '/ma/loi/70-03', 'q': 'نفقة الطرفين'}).json()
    assert [(a['label'], a['together']) for a in r['articles']] == [('المادة 192', True), ('المادة 193', True),
                                                                    ('المادة 190', False)]
    assert r['together'] == 2 and [s['t'] for s in r['articles'][0]['snippet'] if s['hit']][-2:] == ['نفقة', 'الطرفين.']


def test_an_unknown_text_is_said_in_the_one_error_shape(api, code):
    r = api.get('/api/search/in/', {'path': '/ma/loi/1-01', 'q': 'نفقة'})
    assert r.status_code == 404 and r.json() == {'errors': [{'field': 'path', 'code': 'not_found'}]}


def test_a_long_article_shows_the_stretch_around_its_first_word(monkeypatch):
    # B27 of the search plan: an annex of 157,000 characters is read a stretch at a time for its two lines, and they
    # are the lines it gave when read whole.
    import ma_law
    from apps.search.services.search import snippets
    body = ' '.join(['رسم'] * 3000) + ' تجب النفقة على الأب ' + ' '.join(['رسم'] * 3000)
    assert len(body) > 4 * snippets.LONG
    terms = ma_law.search_terms('النفقة')
    shown = snippets.snippet(body, terms, *snippets.SNIPPET)
    assert shown[0]['t'].startswith('… ') and shown[-1]['t'].endswith(' …') and [s['t'] for s in shown if s['hit']] == ['النفقة']
    monkeypatch.setattr(snippets, 'LONG', 10 ** 9)
    assert snippets.snippet(body, terms, *snippets.SNIPPET) == shown


def test_the_marks_a_search_leaves_are_the_forms_the_text_writes_its_words_in(api, code):
    """H2 of the search's marks (29 Oct 2026): «النفقة» lights «نفقة» as the text writes it, without the comma after it;
    with any=1 an article holding one of the words counts."""
    r = api.get('/api/search/in/', {'path': '/ma/loi/70-03', 'q': 'النفقة'}).json()
    assert r['words'] == ['نفقة']
    assert api.get('/api/search/in/', {'path': '/ma/loi/70-03', 'q': 'نفقة الطرفين'}).json()['count'] == 1
    some = api.get('/api/search/in/', {'path': '/ma/loi/70-03', 'q': 'نفقة الطرفين', 'any': '1'}).json()
    assert some['count'] == 3 and set(some['words']) == {'نفقة', 'الطرفين'}
