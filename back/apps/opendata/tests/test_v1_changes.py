"""What changed since a day (apps/opendata/services/changes.py, GET /api/v1/changes): the texts the Bulletin published
and the changes it published to the texts the site holds, newest first, a page at a time by a cursor that holds its
place while rows arrive, never further back than a year and a day."""
from datetime import timedelta

import pytest

from apps.accounts.services.refusals import Refused
from apps.consolidation.models import Change
from apps.corpus.models import Text
from apps.opendata.services import changes
from apps.opendata.tests.test_v1 import ago, change_of, get, issue_of, law_of, made, requests_open  # noqa: F401  (fixtures)
from apps.opendata.tests.helpers import keyed
from apps.mcp.tests.conftest import labour  # noqa: F401  (a fixture)
from apps.sources.models import Edition

pytestmark = pytest.mark.django_db
SITE = 'http://localhost:5190'


def test_a_text_and_a_change_say_what_a_copy_needs(made):
    page = changes.since(str(ago(30)))
    assert page['since'] == str(ago(30)) and page['next'] is None
    assert page['published'] == [{
        'id': '/ma/loi/12-26', 'url': f'{SITE}/ma/loi/12-26', 'title': 'القانون رقم 12-26', 'title_fr': None,
        'type': 'law', 'number': '12.26', 'status': 'in force', 'on': str(ago(20)),
        'published_in': {'bo': '7533', 'edition': 'general_ar', 'date': str(ago(20)), 'page': 100,
                         'url': f'{SITE}/bo/general_ar/7533'}}]
    assert page['amended'] == [{
        'id': '/ma/loi/65-99', 'url': f'{SITE}/ma/loi/65-99', 'title': 'القانون رقم 65.99 المتعلق بمدونة الشغل',
        'type': 'law', 'article': '51', 'article_id': '/ma/loi/65-99/art_51', 'how': 'modified', 'on': str(ago(20)),
        'effective_on': str(ago(20) + timedelta(days=30)),
        'by': {'id': '/ma/loi/12-26', 'title': 'القانون رقم 12-26', 'kind': 'law', 'number': '12.26',
               'article': 'المادة 2'},
        'published_in': {'bo': '7533', 'edition': 'general_ar', 'date': str(ago(20)), 'page': 101,
                         'url': f'{SITE}/bo/general_ar/7533'}}]


def test_only_what_the_bulletin_published_since_that_day_and_the_site_shows_as_fact(made):
    amending = made['amending']
    old = issue_of(7400, ago(200))
    law_of('1-25', old)                                                   # before the day asked
    Text.objects.create(akn_uri='/akn/ma/act/projet-loi/60-26', type='bill', title_ar='مشروع قانون',
                        first_published_in=made['recent'])               # a bill is no Bulletin text
    for fields in ({'source': Change.Source.MODEL}, {'source': Change.Source.BILL, 'state': Change.State.PROPOSED},
                   {'state': Change.State.UNCLEAR}, {'state': Change.State.CONFLICT},
                   {'text_uri': '/akn/ma/act/loi/99-99'},                 # a text the site does not hold
                   {'day': ago(200)}):
        change_of(amending, **fields)
    change_of(amending, number='', state=Change.State.CHECKED, by_uri='', issue=None, page=None,
              effective_on=None)                                          # the whole text, by a text not held
    page = changes.since(str(ago(30)))
    assert [t['id'] for t in page['published']] == ['/ma/loi/12-26']
    whole, one = page['amended']
    assert (whole['article'], whole['article_id'], whole['effective_on']) == (None, None, None)
    assert whole['by'] == {'id': None, 'title': None, 'kind': 'law', 'number': '12.26', 'article': 'المادة 2'}
    assert whole['published_in'] == {'bo': None, 'edition': 'general_ar', 'date': str(ago(20)), 'page': None,
                                     'url': None}
    assert one['article_id'] == '/ma/loi/65-99/art_51'
    # Further back, the older law is there too.
    assert [t['id'] for t in changes.since(str(ago(365)))['published']] == ['/ma/loi/12-26', '/ma/loi/1-25']


def test_an_issue_the_site_does_not_hold_has_no_link_and_an_article_it_lacks_no_address(made):
    change_of(made['amending'], number='700', issue=7999)
    first = changes.since(str(ago(30)))['amended'][0]
    assert first['article'] == '700' and first['article_id'] is None
    assert first['published_in']['bo'] == '7999' and first['published_in']['url'] is None


def test_newest_first_and_on_one_day_the_texts_before_the_changes(made):
    later = issue_of(7540, ago(5))
    other = issue_of(7539, ago(5), edition=Edition.TRANSLATION_FR)
    second = law_of('13-26', later, page=10)
    law_of('14-26', other, page=3)
    change_of(second, number='52')
    page = changes.since(str(ago(30)))
    assert [(t['id'], t['on']) for t in page['published']] == [
        ('/ma/loi/14-26', str(ago(5))), ('/ma/loi/13-26', str(ago(5))), ('/ma/loi/12-26', str(ago(20)))]
    assert page['published'][0]['published_in']['url'] == f'{SITE}/bo/translation_fr/7539'
    assert [(c['article'], c['on']) for c in page['amended']] == [('52', str(ago(5))), ('51', str(ago(20)))]


@pytest.mark.parametrize('size', [2, 3, 4])
def test_pages_follow_one_another_by_their_cursor_whatever_arrives_meanwhile(made, monkeypatch, size):
    for k in range(4):                                       # four days, a text and two changes each
        issue = issue_of(7541 + k, ago(10 - k))
        law = law_of(f'{20 + k}-26', issue)
        change_of(law, number='49')
        change_of(law, number='50')
    monkeypatch.setattr(changes, 'PAGE', 1000)
    whole = changes.since(str(ago(30)))
    monkeypatch.setattr(changes, 'PAGE', size)
    first = page = changes.since(str(ago(30)))
    published, amended, pages = [], [], 0
    while True:
        published += page['published']
        amended += page['amended']
        pages += 1
        assert len(page['published']) + len(page['amended']) <= size
        if page['next'] is None:
            break
        if pages == 1:                # a row arrives between two pages: newer than the cursor, it waits for a new walk
            change_of(made['amending'], number='53', day=ago(0))
        page = changes.since(str(ago(30)), page['next'])
    # Each list whole, in its order, every item once, in as many pages as the size makes.
    assert published == whole['published'] and amended == whole['amended']
    assert len(published) + len(amended) == 4 + 8 + 2 and pages == -(-14 // size)
    if size == 3:
        # The first page: the newest day's text, then its two changes, the newest row first; the cursor is the last.
        last = Change.objects.get(by_uri='/akn/ma/act/loi/23-26', number='49')
        assert [t['id'] for t in first['published']] == ['/ma/loi/23-26']
        assert [c['article'] for c in first['amended']] == ['50', '49'] and first['next'] == f'{ago(7)}.a.{last.pk}'


def test_a_change_whose_text_went_between_two_queries_is_left_out():
    gone = Change(text_uri='/akn/ma/act/loi/1-01', number='', verb='repealed', source=Change.Source.READING,
                  by_kind='law', by_number='2.26', published_on=ago(1))
    assert changes._change_items([gone]) == []


@pytest.mark.parametrize('since, cursor, expected', [
    ('', '', ('since', 'required')),
    ('yesterday', '', ('since', 'invalid')),
    ('2026-02-30', '', ('since', 'invalid')),
    (None, '', ('since', 'too_far')),
    ('today', 'x', ('cursor', 'invalid')),
    ('today', '2026-13-01.p.1', ('cursor', 'invalid')),
    ('today', '2026-11-01.z.1', ('cursor', 'invalid')),
    ('today', '2026-11-01.p.' + '9' * 19, ('cursor', 'invalid')),
])
def test_what_since_and_the_cursor_refuse(since, cursor, expected):
    since = str(ago(367)) if since is None else str(ago(0)) if since == 'today' else since
    with pytest.raises(Refused) as refused:
        changes.since(since, cursor)
    assert (refused.value.field, refused.value.code) == expected
    assert changes.since(str(ago(366)))['published'] == []          # a year and a day back is still answered


def test_a_page_costs_the_same_few_queries_whatever_it_holds(made, django_assert_num_queries):
    with django_assert_num_queries(6):
        small = changes.since(str(ago(30)))
    for k in range(6):
        issue = issue_of(7600 + k, ago(15 - k))
        for n in range(3):
            law = law_of(f'{30 + k * 3 + n}-26', issue, page=n + 1)
            change_of(law, number=str(49 + n))
            change_of(law, number='', by_uri='')
    with django_assert_num_queries(6):
        big = changes.since(str(ago(30)))
    assert len(small['amended']) == 1 and len(big['amended']) == 1 + 36 and len(big['published']) == 1 + 18
    with django_assert_num_queries(2):                         # nothing changed: the two lists' queries alone
        assert changes.since(str(ago(0))) == {'since': str(ago(0)), 'published': [], 'amended': [], 'next': None}


def test_the_read_answers_the_page_and_its_refusals(api, made):
    _, key = keyed()
    assert get(api, f'/api/v1/changes?since={ago(30)}&cursor=', key).json()['published'][0]['id'] == '/ma/loi/12-26'
    r = get(api, f'/api/v1/changes?since={ago(0)}&cursor=nope', key)
    assert (r.status_code, r.json()) == (400, {'errors': [{'field': 'cursor', 'code': 'invalid'}]})
