"""No malformed request answers 500 at any address of apps.explain (OP53 of the open-source audit): a list where an object
is read, a NUL, other digits, an impossible date, a number past any column, an over-long string. The shapes and the
walk over every route are `knock` and `malformed` in back/conftest.py."""
import pytest


def test_no_malformed_request_answers_500(knock, malformed):
    assert knock('explain', malformed) == []

from apps.discussion.tests.conftest import lease, make_user, signed_in, uploads  # noqa: E402, F401  (fixtures)


@pytest.mark.django_db
def test_an_explanations_fields_of_another_kind_are_refused(api, lease):
    writer = signed_in(api, make_user('nadia'))
    article = '/ma/loi/2013/67-12/art_34'
    r = writer.post('/api/explain/save/', {'path': article, 'register': 'ar', 'body': 'شرح', 'sources': [{}]}, format='json')
    assert (r.status_code, r.json()) == (400, {'errors': [{'field': 'sources', 'code': 'invalid'}]})
    for url, body in (('/api/explain/report/', {'revision': ['1'], 'reason': 'wrong'}),
                      ('/api/explain/act/', {'revision': {'a': 1}, 'act': 'keep'})):
        r = writer.post(url, body, format='json')
        assert (r.status_code, r.json()) == (400, {'errors': [{'field': 'revision', 'code': 'invalid'}]}), url
    # A broken link in the words is a link the gates hold, never an error.
    r = writer.post('/api/explain/save/', {'path': article, 'register': 'ar', 'body': 'انظر https://[', 'consent': True},
                    format='json')
    assert r.status_code < 500
