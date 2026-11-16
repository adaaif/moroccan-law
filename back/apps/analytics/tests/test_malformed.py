"""No malformed request answers 500 at any address of apps.analytics (OP53 of the open-source audit): a list where an
object is read, a NUL, other digits, an impossible date, a number past any column, an over-long string. The shapes and
the walk over every route are `knock` and `malformed` in back/conftest.py."""


def test_no_malformed_request_answers_500(knock, malformed):
    assert knock('analytics', malformed) == []
