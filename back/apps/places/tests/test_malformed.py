"""No malformed request answers 500 at any address of apps.places (OP53 of the open-source audit): a list where an object
is read, a NUL, other digits, an impossible date, a number past any column, an over-long string. The shapes and the
walk over every route are `knock` and `malformed` in back/conftest.py."""
import pytest


def test_no_malformed_request_answers_500(knock, malformed):
    assert knock('places', malformed) == []


@pytest.mark.django_db
@pytest.mark.parametrize('after', ['2024-99-99|/akn/ma/x|1', '٢٠٢٤-٠١-٠١|/akn/ma/x|1', '2024-02-30|/akn/ma/x|-1'])
def test_a_cursor_whose_day_is_no_day_is_refused(api, after):
    """The cursor's pattern let «2024-99-99» through, and its day was read in mentions(), outside the view's refusal."""
    from apps.places.models import Place
    Place.objects.create(slug='rabat', kind=Place.Kind.values[0], name_ar='الرباط', name_fr='Rabat')
    r = api.get('/api/places/rabat/mentions/', {'after': after})
    assert (r.status_code, r.json()) == (400, {'errors': [{'field': 'after', 'code': 'invalid'}]})
    assert api.get('/api/places/rabat/mentions/', {'after': '2024-01-31|/akn/ma/x|1'}).status_code == 200
