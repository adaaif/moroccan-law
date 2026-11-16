"""No malformed request answers 500 at any address of apps.topics (OP53 of the open-source audit): a list where an object
is read, a NUL, other digits, an impossible date, a number past any column, an over-long string. The shapes and the
walk over every route are `knock` and `malformed` in back/conftest.py."""
import pytest

pytestmark = pytest.mark.needs('fribidi')     # the topics' link pictures are among the addresses


def test_no_malformed_request_answers_500(knock, malformed):
    assert knock('topics', malformed) == []
