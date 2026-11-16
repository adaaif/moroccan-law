"""The search tool over HTTP on the site's own search (BM25, so ParadeDB): a citation jumps to its text or article, a
bill is said to be no law, a title alone is a result, a repaired query says what was searched, nothing found says what
to try."""
import json
from datetime import date

import pytest
from django.core.cache import cache
from django.db import connection

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.mcp.tests.conftest import ART_51_NOW
from apps.mcp.tests.test_server import rpc, server_url, the_clock_stands_still  # noqa: F401  (fixtures)
from apps.search.services.index import rebuild

pytestmark = [pytest.mark.django_db(transaction=True),
              pytest.mark.skipif(connection.vendor != 'postgresql', reason='BM25 needs ParadeDB (TEST_DATABASE_URL)')]
SITE = 'http://localhost:5190'
WORDS = ' '.join(f'كلمة{n}' for n in range(1, 51))           # fifty words: a cited article's first forty are given


@pytest.fixture
def indexed(labour):
    bill = Text.objects.create(akn_uri='/akn/ma/act/projet-loi/60-26', type='bill', number='60-26',
                               number_as_printed='60.26', title_ar='مشروع قانون المالية رقم 60.26 للسنة المالية 2027')
    v = Version.objects.create(text=bill, language='ar', valid_from=date(2026, 10, 20), consolidation=Consolidation.BILL)
    Article.objects.create(version=v, order=1, label='المادة 7', number='7', eid='art_7',
                           body='تغير مقتضيات المدونة العامة للضرائب المتعلقة بالضريبة على الدخل.')
    Text.objects.create(akn_uri='/akn/ma/act/decret/2-96-1', type='decree', number='2-96-1', number_as_printed='2.96.1',
                        title_ar='مرسوم رقم 2.96.1 بتحديد شروط تربية النحل')        # its title alone is held
    Article.objects.filter(version__text=labour, number='54').update(body=WORDS)
    rebuild(log=lambda m: None)


def search(url, query):
    result = rpc(url, 'tools/call', {'name': 'search', 'arguments': {'query': query}},
                 forwarded='203.0.113.120').json()['result']
    return json.loads(result['content'][0]['text'])


def test_search_answers_in_the_shape_deep_research_expects(server_url, indexed):
    cache.clear()
    law = search(server_url, 'القانون رقم 65.99')                 # a citation of the text: the text first
    assert law['results'][0] == {'id': '/ma/loi/65-99', 'title': 'مدونة الشغل', 'url': f'{SITE}/ma/loi/65-99',
                                 'text': 'القانون رقم 65.99 المتعلق بمدونة الشغل', 'status': 'in force', 'kind': 'text'}
    assert [r['id'] for r in law['results']].count('/ma/loi/65-99') == 1
    cited, text = search(server_url, 'المادة 54 من القانون رقم 65.99')['results']
    assert text['id'] == '/ma/loi/65-99' and cited['id'] == '/ma/loi/65-99/art_54' and cited['text'] == ' '.join(WORDS.split()[:40]) + ' …'
    short = search(server_url, 'المادة 51 من القانون رقم 65.99')['results'][0]
    assert short['text'] == ART_51_NOW                                  # twenty words: given whole
    bill = search(server_url, 'الضريبة على الدخل')['results']
    assert [(r['id'], r['status']) for r in bill] == [('/ma/projet-loi/60-26/art_7', 'a bill: not law')]
    titled = search(server_url, 'تربية النحل')['results']
    assert titled == [{'id': '/ma/decret/2-96-1', 'title': 'مرسوم رقم 2.96.1 بتحديد شروط تربية النحل',
                       'url': f'{SITE}/ma/decret/2-96-1', 'text': 'مرسوم رقم 2.96.1 بتحديد شروط تربية النحل',
                       'status': 'status not established', 'kind': 'text'}]
    repaired = search(server_url, 'hgqvdfm')                        # «الضريبة» typed on a French keyboard
    assert repaired['searched_as'] == 'الضريبة' and repaired['results'][0]['id'] == '/ma/projet-loi/60-26/art_7'
    nothing = search(server_url, 'xyzzy qwerty')
    assert nothing == {'results': [], 'note': "Nothing found. Try the law's own words in Arabic or French, the text's "
                                              "number («القانون 65.99»), or fewer words."}
    assert len(law['results']) == 3
