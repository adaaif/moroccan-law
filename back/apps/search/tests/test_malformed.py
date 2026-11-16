"""No malformed request answers 500 at any address of apps.search (OP53 of the open-source audit): a list where an object
is read, a NUL, other digits, an impossible date, a number past any column, an over-long string. The shapes and the
walk over every route are `knock` and `malformed` in back/conftest.py."""


def test_no_malformed_request_answers_500(knock, malformed):
    assert knock('search', malformed) == []


def test_a_page_or_a_year_in_other_digits_is_the_first_page_and_no_bound():
    """«²» passes `str.isdigit()` and fails in `int()`: `?page=²` answered 500. Arabic-Indic digits are numbers to both."""
    from apps.search.api import views
    assert views._page('²') == 1 and views._page('٣') == 3 and views._page('3') == 3
    assert views._year('²٠٢٤') is None and views._year('٢٠٢٤') == 2024 and views._year('2024') == 2024
