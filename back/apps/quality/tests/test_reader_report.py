"""The weekly report: searches without an answer, the ones that led nowhere, slow pages; the endpoints that feed it."""
from io import StringIO

import pytest
from django.core.management import call_command

from apps.quality.models import PageTiming
from apps.search.models import SearchLog

pytestmark = pytest.mark.django_db


def test_report_reads_searches_and_timings(client):
    nothing = SearchLog.objects.create(query='كراء', folded='كراء', results=0)
    nowhere = SearchLog.objects.create(query='السير', folded='السير', results=4)
    led = SearchLog.objects.create(query='الشغل', folded='الشغل', results=2)
    assert client.post('/api/search/opened/', {'log': led.pk, 'rank': 1}, content_type='application/json').status_code == 204
    assert client.post('/api/search/opened/', {'log': led.pk, 'rank': 5}, content_type='application/json').status_code == 204
    led.refresh_from_db()
    assert led.opened == 1  # the first answer opened is kept
    assert client.post('/api/quality/timing/', {'kind': 'article', 'ms': 3200}, content_type='application/json').status_code == 204
    assert client.post('/api/quality/timing/', {'kind': 'nope', 'ms': 3200}, content_type='application/json').status_code == 400
    out = StringIO()
    call_command('reader_report', stdout=out)
    text = out.getvalue()
    assert '3 searches; 1 found nothing; 1 found texts but led nowhere; 0 about violence' in text
    assert f'| {nothing.folded} | 1 |' in text and f'| {nowhere.folded} | 1 |' in text
    assert '| An article | 1 | 3.2 s | 3.2 s | 100 % |' in text
    assert PageTiming.objects.count() == 1


def test_report_counts_private_searches_and_whether_topic_pages_helped():
    """F14, F15 of the family plan: a search about violence is a count, never its words; «هل ساعدك هذا؟» by page."""
    from apps.topics.models import Helped
    SearchLog.objects.create(query='', folded='', results=0, understood_as='private')
    Helped.objects.create(path='/topics/family/journeys/marry', helped=True)
    Helped.objects.create(path='/topics/family/journeys/marry', helped=False, reason='unclear')
    out = StringIO()
    call_command('reader_report', stdout=out)
    text = out.getvalue()
    assert '0 searches; 0 found nothing; 0 found texts but led nowhere; 1 about violence' in text
    assert '| /topics/family/journeys/marry | 1 | 1 | 1 | 0 | 0 |' in text


def test_report_counts_the_tools_use_the_words_cut_in_two_and_writes_its_file(tmp_path):
    from datetime import date as day
    from datetime import timedelta

    from django.utils import timezone

    from apps.corpus.models import Article, Consolidation, Text, Version
    from apps.quality.models import Correction
    from apps.topics.models import ToolUse
    today = timezone.localdate()
    for path, event, count in (('/topics/road/tools/fine', 'open', 3), ('/topics/road/tools/fine', 'share', 1),
                               ('/topics/work/tools/end', 'open', 9)):
        ToolUse.objects.create(on=today, path=path, event=event, count=count)
    ToolUse.objects.create(on=today - timedelta(days=30), path='/topics/old', event='open', count=99)    # a month ago
    # The text with fewer words cut in two first: the table lists the text with most first.
    family = Text.objects.create(akn_uri='/akn/ma/act/loi/70-03', type='law', number='70-03', title_ar='مدونة الأسرة')
    v = Version.objects.create(text=family, language='ar', valid_from=day(2016, 1, 1), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='المادة 1', number='1', eid='art_1', body='وتو ابعها')
    labour = Text.objects.create(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99', title_ar='مدونة الشغل')
    v = Version.objects.create(text=labour, language='ar', valid_from=day(2026, 7, 16), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='المادة 66', number='66', eid='art_66', body='على الاستغ الالت وتو ابعها')
    Article.objects.create(version=v, order=2, label='المادة 67', number='67', eid='art_67', body='وتو ابعها')
    bo = Text.objects.create(akn_uri='/akn/ma/act/loi/1-26', type='law', number='1-26', title_ar='قانون')
    v = Version.objects.create(text=bo, language='ar', valid_from=day(2026, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='المادة 1', number='1', eid='art_1', body='وتوابعها الاستغلالات ' * 5)
    Correction.objects.create(path='/ma/loi/65-99/art_67', wrong='وتو ابعها', right='وتوابعها', source='split')
    # Set aside, and proposed by another reader: neither waits as a split on /corrections.
    Correction.objects.create(path='/ma/loi/65-99/art_66', wrong='وتو ابعها', right='وتوابعها', source='split',
                              status='rejected')
    Correction.objects.create(path='/ma/loi/70-03/art_1', wrong='وتو ابعها', right='وتوابعها', source='review')
    out = tmp_path / 'week.md'
    stdout = StringIO()
    call_command('reader_report', '--out', str(out), stdout=stdout)
    assert stdout.getvalue() == f'written to {out}\n'
    text = out.read_text()
    events = ' | '.join(['open', 'share', 'picture', 'remind', 'listen', 'right', 'wrong', 'door', 'tick'])
    assert (f"## How the topics' tools were used\n\n| Page | {events} |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            '| /topics/work/tools/end | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |\n'
            '| /topics/road/tools/fine | 3 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |\n') in text
    assert ('## Words cut in two\n\n4 in 3 articles; 1 proposed on /corrections (`proofread --split` proposes the rest).\n\n'
            '| Text | Words | Articles |\n| --- | --- | --- |\n| /ma/loi/65-99 | 3 | 2 |\n| /ma/loi/70-03 | 1 | 1 |\n') in text
    assert '/topics/old' not in text


def test_report_says_none_where_nothing_was_seen():
    out = StringIO()
    call_command('reader_report', stdout=out)
    text = out.getvalue()
    assert "## How the topics' tools were used\n\nNone.\n" in text and text.endswith('## Words cut in two\n\nNone.\n')
    assert 'among the first three' not in text


def test_report_says_how_often_the_answer_opened_was_among_the_first_three():
    for rank in (1, 3, 4, None):
        SearchLog.objects.create(query='كراء', folded='كراء', results=9, understood_as='words', opened=rank)
    out = StringIO()
    call_command('reader_report', stdout=out)
    text = out.getvalue()
    assert '| words | 4 | 75 % |' in text
    assert 'The answer opened was among the first three in 67 % of searches that opened one.' in text
