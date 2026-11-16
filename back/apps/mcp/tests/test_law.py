"""What the tools answer (MC10–MC15), from the corpus, before the protocol around them."""
from unittest import mock

import pytest

from apps.mcp.services import law
from apps.mcp.tests.conftest import ART_51_NOW, ART_51_THEN

pytestmark = pytest.mark.django_db
SITE = 'http://localhost:5190'


def test_fetch_gives_an_article_whole_with_its_source_and_standing(labour):
    item, served = law.fetch('/ma/loi/65-99/art_51')
    assert served == 1
    assert item['id'] == '/ma/loi/65-99/art_51' and item['url'] == f'{SITE}/ma/loi/65-99/art_51'
    assert item['text'] == ART_51_NOW and item['title'].startswith('المادة 51 — ')
    meta = item['metadata']
    assert meta['status'] == 'in force' and meta['law']['number'] == '65.99'
    assert meta['published_in'] == {'bo': '5167', 'date': '2003-12-08', 'page': 3969, 'url': f'{SITE}/bo/general_ar/5167'}
    assert meta['version']['official'] is False and 'Bulletin officiel prevails' in meta['version']['note']
    assert meta['french']['text'].startswith('Toute rupture') and '5210' in meta['french']['source']
    assert meta['position'] == '3 of 6'


def test_any_spelling_of_an_address_reads_the_same_article(labour):
    for raw in ('ma/loi/65-99/art_51', 'https://old.example.org/ma/loi/65-99/art_51/', '/ma/loi/65-99/art_51#x'):
        assert law.fetch(raw)[0]['id'] == '/ma/loi/65-99/art_51'


def test_a_number_with_its_printed_zero_reads_the_same_article(labour):
    """Claude asked for /ma/loi/07-03 on 4 Nov 2026: the number as the BO prints it is the law's address too."""
    for raw in ('/ma/loi/065-99/art_51', '/ma/loi/65.99/art_51'):
        assert law.fetch(raw)[0]['id'] == '/ma/loi/65-99/art_51'


def test_fetch_on_a_text_gives_its_outline_with_ids(labour):
    item, served = law.fetch('/ma/loi/65-99')
    assert served == 0 and item['metadata']['kind'] == 'text' and item['metadata']['articles'] == 6
    assert '§ الكتاب الأول: الاتفاقيات المتعلقة بالشغل › الفرع الثالث: أجل الإخطار' in item['text']
    assert 'المادة 51 (/ma/loi/65-99/art_51): يترتب عن إنهاء عقد الشغل' in item['text']


def test_errors_say_what_to_do(labour):
    with pytest.raises(law.Problem, match=r'has no article 700 .*6 articles.*read_articles'):
        law.fetch('/ma/loi/65-99/art_700')
    with pytest.raises(law.Problem, match=r'No text at /ma/loi/1-01\. Search'):
        law.fetch('/ma/loi/1-01')
    with pytest.raises(law.Problem, match='not a 3adala address'):
        law.fetch('the labour code')


def test_read_articles_reads_a_run_and_says_where_to_read_on(labour):
    text, data, served = law.read_articles('/ma/loi/65-99', start='50', count=3)
    assert served == 3 and [a['label'] for a in data['articles']] == ['المادة 50', 'المادة 51', 'المادة 52']
    assert data['range'] == [2, 4] and data['total'] == 6 and data['next'] == '/ma/loi/65-99/art_53'
    assert ART_51_NOW in text and 'Next: read_articles from 53 (2 more articles).' in text
    assert 'Toute rupture' not in text
    assert 'Toute rupture' in law.read_articles('/ma/loi/65-99/art_51', count=1, french=True)[0]


def test_read_articles_on_a_date_reads_the_version_of_that_day(labour):
    text, data, _ = law.read_articles('/ma/loi/65-99/art_51', count=1, on='2010-01-01')
    assert ART_51_THEN in text and data['version']['kind'] == 'as_published' and data['version']['official'] is True
    assert data['on'] == '2010-01-01'
    text, data, _ = law.read_articles('/ma/loi/65-99', on='1990-01-01', count=1)
    assert data['note'].startswith('This text was published in the Bulletin officiel on 2003-12-08, after 1990-01-01')
    assert data['note'] in text
    # Published by then, but held only from a later version: said, article by article.
    text, data, _ = law.read_articles('/ma/loi/65-99', on='2004-01-01', count=1)
    assert data['note'].startswith('3adala holds this text only as it reads from 2004-06-08')
    assert '(No change to this article after 2004-01-01 is recorded.)' in text
    with pytest.raises(law.Problem, match='YYYY-MM-DD'):
        law.read_articles('/ma/loi/65-99', on='last year')


def test_check_references_resolves_each_reference(labour):
    text, data = law.check_references(['المادة 51 من القانون رقم 65.99', 'المادة 700 من القانون رقم 65.99',
                                       'merci beaucoup'])
    first, second, third = data['references']
    assert first['found'][0]['state'] == 'found' and first['found'][0]['id'] == '/ma/loi/65-99/art_51'
    assert first['found'][0]['status'] == 'in force'
    assert second['found'][0]['state'] == 'text_only'
    assert third['found'] == []
    assert 'not read as a reference' in text and f'{SITE}/ma/loi/65-99/art_51' in text
    with pytest.raises(law.Problem):
        law.check_references(['x'] * 51)


def test_bulletin_lists_an_issue_and_the_latest_week(labour):
    one = law.bulletin('5167')['issues'][0]
    assert one['key'] == '5167' and one['texts'][0]['id'] == '/ma/loi/65-99' and one['texts'][0]['page'] == 3969
    assert law.bulletin()['issues'][0]['key'] == '5167'
    assert '• Law: القانون رقم 65.99 المتعلق بمدونة الشغل (p. 3969)' in law.bulletin_text(law.bulletin())
    with pytest.raises(law.Problem, match='No issue 9999'):
        law.bulletin('9999')
    assert law.fetch('bo/5167')[0]['metadata']['kind'] == 'bulletin_issue'


def test_search_flattens_the_sites_answer_into_the_standard_shape():
    answer = {'jump': {'state': 'found', 'text': {'path': '/ma/loi/65-99', 'title': 'القانون رقم 65.99', 'status': 'in_force',
                                                  'name': {'ar': 'مدونة الشغل'}},
                       'article': {'label': 'المادة 53', 'path': '/ma/loi/65-99/art_53'}},
              'results': [{'text': {'path': '/ma/loi/65-99', 'title': 'القانون رقم 65.99', 'status': 'in_force',
                                    'name': {'ar': 'مدونة الشغل'}, 'type': 'law'}, 'title_match': False,
                           'articles': [{'label': 'المادة 53', 'path': '/ma/loi/65-99/art_53', 'snippet': [{'t': 'x'}]},
                                        {'label': 'المادة 54', 'path': '/ma/loi/65-99/art_54',
                                         'snippet': [{'t': 'أجل '}, {'t': 'الإخطار', 'hit': True}]}]}],
              'repaired': None}
    with mock.patch('apps.search.services.search.search', return_value=answer) as asked:
        out = law.search('المادة 53 من مدونة الشغل')
    assert asked.call_args.kwargs == {'via': 'mcp', 'log': True}
    ids = [r['id'] for r in out['results']]
    assert ids == ['/ma/loi/65-99/art_53', '/ma/loi/65-99', '/ma/loi/65-99/art_54']
    assert out['results'][2] == {'id': '/ma/loi/65-99/art_54', 'title': 'المادة 54 — مدونة الشغل',
                                 'url': f'{SITE}/ma/loi/65-99/art_54', 'text': 'أجل الإخطار', 'status': 'in force',
                                 'kind': 'article'}
    with pytest.raises(law.Problem):
        law.search('  ')
