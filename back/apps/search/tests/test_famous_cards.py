"""The famous articles' cards (F5, F9 of the famous-articles review) on any database: an article named as the question named it
first, its French on a French page, its words cut at a word, the changes the Bulletin printed (each amending text once,
a bill's apart), the articles of its own code that cite it, read once a corpus generation."""
from datetime import date

import ma_law
import pytest

from apps.consolidation.models import Change
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.search.services import famous
from apps.search.services.index import rebuild
from apps.translations.models import FrenchArticle

pytestmark = pytest.mark.django_db

PENAL = '/akn/ma/act/dahir/1-59-413'
LONG = 'كل علاقة جنسية بين رجل وامرأة لا تربط بينهما علاقة الزوجية تكون جريمة الفساد. ' * 12


def row_of(code: str, number: str) -> int:
    return next(i for i, r in enumerate(famous.table()['rows']) if (r['code'], r['number']) == (code, number))


def code(uri, kind, number, title, articles, **more):
    text = Text.objects.create(akn_uri=uri, type=kind, number=number, title_ar=title, status='in_force', **more)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2004, 2, 5), consolidation=Consolidation.ADALA)
    for order, (label, n, body) in enumerate(articles, 1):
        Article.objects.create(version=v, order=order, label=label, number=n, body=body, eid=f'art_{n}')


@pytest.fixture
def codes():
    code(PENAL, 'dahir', '1-59-413', 'ظهير شريف بالمصادقة على مجموعة القانون الجنائي', [
        ('الفصل 490', '490', LONG),
        ('الفصل 493', '493', 'الجرائم المعاقب عليها في الفصلين 490 و491 لا تثبت إلا بمحضر، والفصل 490 كذلك.'),
        ('الفصل 494', '494', 'تطبق أحكام الفصل 490 من مدونة الأسرة.')])
    code('/akn/ma/act/loi/70-03', 'law', '70-03', 'القانون رقم 70.03 بمثابة مدونة الأسرة', [
        ('المادة 20', '20', 'لقاضي الأسرة أن يأذن بزواج الفتى والفتاة دون سن الأهلية.')])
    code('/akn/ma/act/loi/10-26', 'law', '10-26', 'القانون رقم 10.26 بتغيير الفصل 490', [('المادة 1', '1', 'يغير الفصل 490.')])
    common = {'text_uri': PENAL, 'number': '490', 'by_kind': 'law', 'by_number': '10-26', 'by_uri': '/akn/ma/act/loi/10-26'}
    Change.objects.create(verb='modified', source='reading', state='read', issue=7600, issue_bis=True, page=12,
                          published_on=date(2026, 3, 2), **common)
    Change.objects.create(verb='modified', source='adala', issue=7600, published_on=date(2026, 3, 3), **common)
    Change.objects.create(verb='modified', source='reading', state='unclear', **common)          # a reading not shown
    Change.objects.create(verb='repealed', source='bill', state='proposed', **{**common, 'by_uri': '/akn/ma/act/projet-loi/60-26'})
    FrenchArticle.objects.create(text_uri=PENAL, order=490, label='Article 490', number='490',
                                 body='Sont punies les relations sexuelles hors mariage. ' * 12)
    rebuild(log=lambda m: None)


def test_a_card_shows_the_article_its_changes_and_its_own_codes_articles_that_cite_it(codes):
    penal, family = row_of('penal', '490'), row_of('family', '20')
    cards = famous.cards([penal, family], word='madda', lang='fr')
    assert [c['path'] for c in cards] == ['/ma/loi/70-03/art_20', '/ma/dahir/1-59-413/art_490']   # «المادة» asked first
    card = cards[1]
    # Its words to the last whole word before BODY letters, the cut said.
    assert card['body'].endswith('…') and len(card['body']) <= famous.BODY + 1 and LONG.startswith(card['body'][:-1])
    assert card['french']['label'] == 'Article 490' and card['french']['body'].endswith('…')
    assert cards[0]['french'] is None
    # The amending law once (its reading and Adala's note), the bill apart, the unclear reading never.
    assert [{k: v for k, v in c.items() if k != 'by'} for c in card['changes']] == [
        {'verb': 'modified', 'published': date(2026, 3, 2), 'issue': '7600-bis', 'page': 12}]
    assert card['changes'][0]['by']['path'] == '/ma/loi/10-26'
    assert card['proposed'] == [{'by': None, 'verb': 'repealed'}]
    # Art. 493 cites it (twice, said once); art. 494 names another code's 490.
    assert [c['path'] for c in card['cited_by']] == ['/ma/dahir/1-59-413/art_493'] and card['cited_more'] == 0
    assert [c['path'] for c in famous.cards([penal, family], word='fasl')] == ['/ma/dahir/1-59-413/art_490', '/ma/loi/70-03/art_20']
    assert [c['path'] for c in famous.cards([family, penal], word='art')] == ['/ma/loi/70-03/art_20', '/ma/dahir/1-59-413/art_490']
    assert famous.cards([penal])[0]['french'] is None                      # an Arabic page
    # A famous article the code on the site does not hold: no card, no line while typing; asked as «article», no order.
    assert famous.cards([row_of('penal', '222')]) == [] and famous.suggestions('222') == []
    assert famous.read('article 490', ma_law.parse_query('article 490'))['word'] == 'art'
    assert famous.suggested(' ') == []


def test_the_citing_articles_and_the_shelf_are_read_once_a_corpus_generation(codes, settings):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def bodies(ctx):          # the query that reads the code's articles for those that cite the card's
        return [q for q in ctx.captured_queries if q['sql'].startswith('SELECT "search_entry"."text_path" AS "text_path", '
                                                                      '"search_entry"."eid" AS "eid", "search_entry"."body"')]

    settings.CACHES = {**settings.CACHES, 'answers': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                                                      'LOCATION': 'famous-answers'}}
    penal = row_of('penal', '490')
    with CaptureQueriesContext(connection) as first:
        cards = famous.cards([penal])
    with CaptureQueriesContext(connection) as again:
        assert famous.cards([penal]) == cards
    assert len(bodies(first)) == 1 and bodies(again) == []
    assert len(again) == len(first) - 3              # nor the shelf's texts (two queries)
    assert [c['path'] for c in cards[0]['cited_by']] == ['/ma/dahir/1-59-413/art_493']


def test_nothing_to_show_is_no_card():
    assert famous.cards([row_of('penal', '490')]) == []          # no code of the shelf on the site
    assert famous.maybe([row_of('penal', '490')]) == [] and famous.suggestions('490') == []
