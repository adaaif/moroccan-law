"""What an article leads to (HM20 of the hard-moment review): the topic items that cite it, from the folders'
map, built once a process, shown as the site shows its drafts, keyed by the article's address."""
import pytest
from django.core.management import call_command

from apps.corpus.models import Article
from apps.topics.services import kit
from apps.topics.tests.test_kit import HUB, family  # noqa: F401 — the fixture: a family folder and code art. 65

pytestmark = pytest.mark.django_db


def test_an_article_leads_to_the_items_that_cite_it_drafts_only_as_drafts_show(family, settings):
    assert kit.cites_of('/ma/loi/70-03') == {'articles': {}}
    settings.SHOW_DRAFTS = True
    marry = kit.cites_of('/ma/loi/70-03')['articles']['art_65']
    assert marry == [{'topic': 'family', 'name': marry[0]['name'], 'ref': 'journeys/marry', 'kind': 'journeys',
                      'path': '/topics/family/journeys/marry', 'title': {'ar': 'الزواج', 'fr': 'Le mariage'},
                      'open': False, 'bill': False, 'state': 'draft'}]
    assert marry[0]['name']['ar'] == 'الأسرة'


def test_a_checked_item_leads_there_for_everyone_and_says_when_its_article_changed(family, settings):
    call_command('approve_topic', 'family', 'journeys/marry', '--by', 'a reviewer')
    assert [e['state'] for e in kit.cites_of('/ma/loi/70-03')['articles']['art_65']] == ['checked']
    Article.objects.filter(eid='art_65').update(body='يحدث ملف إلكتروني لعقد الزواج.')
    assert [e['state'] for e in kit.cites_of('/ma/loi/70-03')['articles']['art_65']] == ['stale']


def test_a_tool_comes_before_a_journey_and_a_bills_item_after_the_laws(family, settings):
    settings.SHOW_DRAFTS = True
    (family / 'hub.yaml').write_text(HUB.replace(
        '{key: dates, tool: true, open: true,',
        '{key: dates, tool: true, open: true, cites: [/ma/loi/70-03/art_65],').replace(
        'tools:\n', 'tools:\n  - {key: bill, tool: true, title: {ar: المشروع, fr: Le projet}, cites: [/ma/projet-loi/60-26/art_7, /ma/loi/70-03/art_65]}\n'),
        encoding='utf-8')
    kit.load.cache_clear()
    found = kit.cites_of('/ma/loi/70-03')['articles']['art_65']
    assert [(e['ref'], e['open'], e['bill']) for e in found] == [
        ('tools/dates', True, False), ('journeys/marry', False, False), ('tools/bill', False, True)]


def test_the_answer_takes_a_few_queries_whatever_the_text_and_refuses_what_is_no_address(family, api, django_assert_max_num_queries):
    call_command('approve_topic', 'family', 'journeys/marry', '--by', 'a reviewer')
    # 4: the first answer after a check reads the checks once (apps/topics/services/kit/folders.py, `_checks`).
    with django_assert_max_num_queries(4):
        out = api.get('/api/topics/cites/?text=/ma/loi/70-03')
    assert out.status_code == 200 and [e['ref'] for e in out.json()['articles']['art_65']] == ['journeys/marry']
    with django_assert_max_num_queries(0):
        assert api.get('/api/topics/cites/?text=/ma/loi/65-99').json() == {'articles': {}}
    assert api.get('/api/topics/cites/?text=../etc').json() == {'errors': [{'field': 'text', 'code': 'invalid'}]}


def test_the_labour_codes_severance_article_leads_to_the_end_of_contract_tool_first(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    art53 = kit.cites_of('/ma/loi/65-99')['articles']['art_53']
    assert art53[0]['path'] == '/topics/work/tools/end' and art53[0]['open']
    assert any(e['ref'] == 'journeys/dismissed' for e in art53)
    # The tax scale: the law's tools first, the 2027 bill's after them, marked.
    art73 = kit.cites_of('/ma/code/cgi')['articles']['art_73']
    assert art73[0]['ref'] == 'tools/salary' and not art73[0]['bill']
    assert [e['ref'] for e in art73 if e['bill']][:1] == ['tools/bill']
    assert [e['bill'] for e in art73] == sorted(e['bill'] for e in art73)
