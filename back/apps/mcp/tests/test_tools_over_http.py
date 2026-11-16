"""Each tool as an assistant calls it over HTTP (one stateless request a call, as ChatGPT sends them): a good call's
answer, and each refusal's words, which say what to do."""
import pytest
from django.core.cache import cache

from apps.mcp.tests.test_server import rpc, server_url, the_clock_stands_still  # noqa: F401  (fixtures)

pytestmark = pytest.mark.django_db(transaction=True)
SITE = 'http://localhost:5190'


def answer(url, name, arguments):
    """(is it an error, its first text, its structured data) for one tool call from one address."""
    result = rpc(url, 'tools/call', {'name': name, 'arguments': arguments}, forwarded='203.0.113.80').json()['result']
    return bool(result.get('isError')), result['content'][0]['text'], result.get('structuredContent')


def test_each_tool_answers_a_good_call_and_says_what_to_do_after_a_wrong_one(server_url, labour):
    cache.clear()
    calls = [
        ('fetch', {'id': '/ma/loi/065-99/art_51'}),                     # the number with the zero the BO prints
        ('fetch', {'id': '/ma/loi/1-01'}),
        ('fetch', {'id': 'https://www.sgg.gov.ma/BO/AR/2003/BO_5167_Ar.pdf'}),      # another site's link
        ('fetch', {'id': 'https://3adala.com/ma/loi/65-99/art_700'}),
        ('read_articles', {'id': '/ma/loi/65-99', 'count': 1, 'on': '1990-01-01'}),
        ('read_articles', {'id': '/ma/loi/65-99', 'on': 'last year'}),
        ('read_articles', {'id': '/ma/loi/65-99', 'count': 21}),
        ('check_references', {'references': ['المادة 51 من القانون رقم 65.99'], 'since': '2026-01-01'}),
        ('check_references', {'references': ['المادة 51 من القانون رقم 65.99'], 'since': 'yesterday'}),
        ('get_bulletin', {'issue': '5167'}),
        ('get_bulletin', {'issue': 'the last one'}),
        ('search', {'query': '   '}),
    ]
    said = [answer(server_url, name, arguments) for name, arguments in calls]
    assert [error for error, _, _ in said] == [False, True, True, True, False, True, True, False, True, False, True, True]
    fetched, unknown, not_an_address, no_article, before, not_a_date, too_many, checked, bad_since, issue, bad_issue, \
        no_words = said
    assert '"id": "/ma/loi/65-99/art_51"' in fetched[1]
    assert unknown[1] == 'No text at /ma/loi/1-01. Search for it by its name or number with the search tool.'
    assert not_an_address[1] == ('«/BO/AR/2003/BO_5167_Ar.pdf» is not a 3adala address. Use an id from search, such '
                                 'as /ma/loi/65-99/art_51.')
    assert no_article[1].startswith('مدونة الشغل has no article 700 in its current version (6 articles). Use '
                                    'read_articles on /ma/loi/65-99')
    assert 'This text was published in the Bulletin officiel on 2003-12-08, after 1990-01-01: it did not exist yet.' \
        in before[1]
    assert before[2]['on'] == '1990-01-01' and before[2]['articles'][0]['label'] == 'المادة 49'
    assert not_a_date[1] == '«last year» is not a date: give it as YYYY-MM-DD, e.g. 2022-03-01.'
    assert 'count' in too_many[1]                                       # at most 20, refused before any article is read
    assert checked[2]['since'] == '2026-01-01' and checked[2]['references'][0]['found'][0]['changed_since'] == []
    assert bad_since[1] == '«yesterday» is not a date: give it as YYYY-MM-DD.'
    assert issue[2]['issues'][0]['texts'] == [{'id': '/ma/loi/65-99', 'kind': 'Law', 'page': 3969}]
    assert 'title' not in issue[2]['issues'][0]['texts'][0]          # the title once, in the text
    assert bad_issue[1] == '«the last one» is not an issue number: give it as 7533 or 7533-bis.'
    assert no_words[1].startswith('Give words to search')
