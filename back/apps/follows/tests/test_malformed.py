"""No malformed request answers 500 at any address of apps.follows (OP53 of the open-source audit): a list where an object
is read, a NUL, other digits, an impossible date, a number past any column, an over-long string. The shapes and the
walk over every route are `knock` and `malformed` in back/conftest.py."""
import pytest


def test_no_malformed_request_answers_500(knock, malformed):
    assert knock('follows', malformed) == []


@pytest.mark.django_db
def test_a_followed_place_past_its_column_is_refused(api):
    """A commune's name is followed as typed («/places/<its name>»): one past the column answered 500 in Postgres."""
    from apps.discussion.tests.conftest import make_user, signed_in
    reader = signed_in(api, make_user('nadia'))
    r = reader.post('/api/follows/', {'path': '/places/' + 'س' * 400}, format='json')
    assert (r.status_code, r.json()) == (404, {'errors': [{'field': 'path', 'code': 'not_found'}]})
    assert reader.post('/api/follows/', {'path': '/places/سلا'}, format='json').status_code == 201
