"""No malformed request answers 500 at any address of apps.corpus (OP53 of the open-source audit): a list where an object
is read, a NUL, other digits, an impossible date, a number past any column, an over-long string. The shapes and the
walk over every route are `knock` and `malformed` in back/conftest.py."""
import pytest


def test_no_malformed_request_answers_500(knock, malformed):
    assert knock('corpus', malformed) == []


@pytest.mark.django_db
@pytest.mark.parametrize('since', ['2024-99-99', '²', 'x' * 300, '9' * 40])
def test_the_texts_list_refuses_a_moment_it_cannot_compare(api, since):
    """`?since=` went straight into `updated_at__gte` and its ValidationError answered 500."""
    r = api.get('/api/corpus/texts/', {'since': since})
    assert (r.status_code, r.json()) == (400, {'errors': [{'field': 'since', 'code': 'invalid'}]})
    assert api.get('/api/corpus/texts/', {'since': '2024-01-01T00:00:00Z'}).status_code == 200
