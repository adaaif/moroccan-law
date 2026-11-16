"""RD14 of the readers review: two answers asked one query for each row (hundreds of them on a full database)."""
from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.consolidation.models import Change
from apps.corpus.models import Article, Text, Version
from apps.corpus.services import citations
from apps.search.services import search
from apps.translations.models import FrenchArticle

pytestmark = pytest.mark.django_db


def _code(articles: int):
    code = Text.objects.create(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99', title_ar='مدونة الشغل')
    v = Version.objects.create(text=code, language='ar', valid_from=date(2026, 7, 16), consolidation='adala')
    for n in range(1, articles + 1):
        Article.objects.create(version=v, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}', body='إجازة الولادة أربعة عشر أسبوعا.')
        FrenchArticle.objects.create(text_uri=code.akn_uri, order=n, label=f'Article {n}', number=str(n),
                                     body='La salariée dispose d\'un congé de maternité de quatorze semaines.')
    return code


@pytest.mark.parametrize('articles', [3, 30])
def test_find_in_a_text_in_french_asks_the_same_queries_whatever_the_texts_length(articles):
    _code(articles)
    with CaptureQueriesContext(connection) as asked:
        found = search.find_in('/ma/loi/65-99', 'congé de maternité')
    assert found['count'] == articles
    assert len(asked) <= 6, [q['sql'][:90] for q in asked]


@pytest.mark.parametrize('changes', [2, 20])
def test_an_articles_changes_ask_for_their_texts_once(changes):
    code = _code(1)
    for n in range(changes):
        by = Text.objects.create(akn_uri=f'/akn/ma/act/loi/{n}-25', type='law', number=f'{n}-25', title_ar='قانون يغير مدونة الشغل')
        Change.objects.create(text_uri=code.akn_uri, number='1', verb='amended', source='reading', state='read',
                              by_uri=by.akn_uri, by_kind='law', by_number=f'{n}-25', published_on=date(2025, 1, 1 + n))
    with CaptureQueriesContext(connection) as asked:
        rows = citations._changes(code, '1', None)
    assert len(rows) == changes and all(r['by']['in_corpus'] is False for r in rows)
    assert len(asked) <= 3, [q['sql'][:90] for q in asked]
