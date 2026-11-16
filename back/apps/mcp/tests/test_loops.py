"""`check_references` costs the same for five references as for fifty (no query inside a loop): every citation the
references hold is resolved in one call, with what `resolve` answers for each alone, the dated ones («ظهير 12 غشت
1913») included."""
from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.corpus.models import Text
from apps.corpus.services.citations import resolve, resolve_many
from apps.mcp.services import law
from apps.search.tests.test_checker import corpus, held  # noqa: F401  (fixtures)

pytestmark = pytest.mark.django_db
REFERENCES = ['المادة 2 من القانون رقم 12.26', 'المادة 9 من القانون رقم 12.26 والقانون رقم 5.25', 'الفصل 230 من ق.ل.ع',
              'المادة 3 من مدونة الأسرة', 'الفصل 1 من القانون رقم 1.58', 'المادة 7 من القانون رقم 60.26',
              'القانون رقم 99.99', 'ج.ر 7533', 'ج.ر 9999 مكرر', 'المادة 5', 'ظهير 12 غشت 1913',
              'الفصل 2 من ظهير 9 رمضان 1331 (12 أغسطس 1913)', 'ظهير 1 يناير 1958', 'شكرا']


@pytest.fixture
def dated(corpus):
    """Two texts signed on 12 August 1913, a dahir and one kept as a law (so that day names neither); a dahir alone
    signed on 1 January 1958."""
    held('/akn/ma/act/dahir/1913/obligations', articles=('1', '2'), type='dahir', title='ظهير الالتزامات والعقود')
    held('/akn/ma/act/loi/1913/procedure', articles=('1',), type='law', title='ظهير المسطرة المدنية')
    held('/akn/ma/act/dahir/1958/1-58-001', articles=('1',), type='dahir', title='ظهير الحريات العامة')
    Text.objects.filter(akn_uri__contains='/1913/').update(signed_on=date(1913, 8, 12))
    Text.objects.filter(akn_uri__contains='/1958/').update(signed_on=date(1958, 1, 1))


def citations(references) -> list[dict]:
    import ma_law
    return [c for ref in references for c in (list(ma_law.parse_citations(ref)) or list(ma_law.parse_query(ref)))[:5]]


def test_a_list_of_citations_is_answered_as_each_alone_dates_included(dated):
    cites = citations(REFERENCES)
    assert any(c.get('date') for c in cites)
    for since in (None, date(2026, 1, 1)):
        assert resolve_many(cites, checker=True, since=since) == [resolve(c, since) for c in cites]


@pytest.mark.parametrize('since', ['', '2026-01-01'])
def test_check_references_costs_the_same_for_five_references_as_for_fifty(dated, since):
    costs = []
    few = ['المادة 9 من القانون رقم 12.26 والقانون رقم 5.25', 'الفصل 230 من ق.ل.ع', 'المادة 7 من القانون رقم 60.26',
           'ج.ر 7533', 'ظهير 1 يناير 1958']          # one of each kind a list asks its own queries for
    for references in (few, (REFERENCES * 4)[:50]):
        with CaptureQueriesContext(connection) as queries:
            _text, data = law.check_references(references, since=since)
        assert [r['reference'] for r in data['references']] == references
        costs.append(len(queries))
    assert costs[0] == costs[1], costs
    states = {r['reference']: [f['state'] for f in r['found']] for r in data['references']}
    assert states['ظهير 12 غشت 1913'] == ['unknown'] and states['ظهير 1 يناير 1958'] == ['found']
    assert states['شكرا'] == []
