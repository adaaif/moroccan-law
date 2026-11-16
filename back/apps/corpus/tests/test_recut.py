"""Laws read into the text before them (T3 of the work plan): found by their promulgating dahir, cut again from the
issue's page readings, and the article that held them given back its own words."""
import json
from datetime import date

import pytest
from django.utils import timezone

from apps.corpus.models import Article, Text
from apps.corpus.services import recut
from apps.corpus.services.issue_structure import load_texts, segment_issue, split_articles, issue_lines
from apps.sources.models import Document, Edition, Issue, Page

pytestmark = pytest.mark.django_db

PAGES = [
    'فهرست\nقانون رقم 10.20 يتعلق بالشغل المنزلي ........ 1530',
    ('ظهير شريف رقم 1.25.02 صادر في 21 من شعبان 1446 (20 فبراير 2025) بتنفيذ القانون رقم 10.20 يتعلق بالشغل المنزلي.\n'
     'الحمد لله وحده،\nوحرر بالرباط في 21 من شعبان 1446 (20 فبراير 2025).\nقانون رقم 10.20\nيتعلق بالشغل المنزلي\n'
     'المادة الأولى\nيطبق هذا القانون على العمال المنزليين.\nالمادة 2\nيدخل هذا القانون حيز التنفيذ من تاريخ نشره.'),
    ('ظهير شريف رقم 1.25.03 صادر في 21 من شعبان 1446 (20 فبراير 2025) بتنفيذ القانون رقم 27.23 بتغيير وتتميم القانون رقم 18.12 المتعلق بالتعويض عن حوادث الشغل.\n'
     'الحمد لله وحده،\nوحرر بالرباط في 21 من شعبان 1446 (20 فبراير 2025).\n*\n* *\nقانون رقم 27.23\n'
     'بتغيير وتتميم القانون رقم 18.12\nالمتعلق بالتعويض عن حوادث الشغل\nالمادة الأولى\nتحل عبارة «الإدارة المختصة» محل عبارة «المدير الإقليمي للتشغيل».\n'
     'المادة الثانية\nيتعين على المشغل أن يصرح بالحادثة لدى الإدارة المختصة.\n'
     'قرار لوزير التشغيل رقم 148.25 صادر في 12 من رجب 1446 (13 يناير 2025) بتتميم لائحة.\nالمادة الأولى\nتتمم اللائحة.'),
]
TOC = [{'section': 'general', 'rubric': '', 'type': 'law', 'number_as_printed': '10.20',
        'title': 'ظهير شريف رقم 1.25.02 صادر في 21 من شعبان 1446 (20 فبراير 2025) بتنفيذ القانون رقم 10.20',
        'signed_on_gregorian': '2025-02-20', 'signed_on_hijri': '', 'page': 1530}]


@pytest.fixture
def issue(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='7383' * 16, path='BO_7383_ar.pdf',
                                  mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now(), page_count=3)
    for i, text in enumerate(PAGES):
        Page.objects.create(document=doc, index=i, printed_number=1529 + i, text=text)
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7383, date=date(2025, 3, 3), document=doc,
                                 first_page_number=1529)
    work = tmp_path / 'reports' / 'issues' / issue.key
    work.mkdir(parents=True)
    (work / 'toc.json').write_text(json.dumps(TOC, ensure_ascii=False))
    # The pipeline's cut, as it was: the contents name 10.20 only, so its span runs on to the issue's end.
    lines = issue_lines(issue)
    span = segment_issue(issue, TOC)[0]
    cut = split_articles(lines[span[0]:span[1]])
    item = {'toc': TOC[0], 'pages': [1530, 1531], 'front': cut['front'], 'articles': cut['articles'], 'tail': cut['tail'],
            'stop': 'end_turn', 'error': '',
            'data': {'found': True, 'type': 'law', 'number_as_printed': '10.20', 'title': '', 'signed_on_gregorian': '2025-02-20',
                     'signed_on_hijri': '', 'authority': '', 'promulgating_dahir': '1.25.02', 'preamble': [],
                     'closing': '', 'signatories': [], 'cites': [], 'amends': []}}
    (work / 'texts.json').write_text(json.dumps([item], ensure_ascii=False))
    load_texts(issue, [item])
    return issue


def test_a_law_the_contents_missed_is_found_by_its_dahir_and_cut_from_the_pages(issue):
    host = Article.objects.get(version__text__akn_uri='/akn/ma/act/loi/10-20', eid='art_2')
    assert 'قانون رقم 27.23' in host.body          # the fault: 27.23 inside art. 2 of 10.20
    p, order = recut.plan(issue)
    assert (p['kind'], p['printed'], p['dahir'], p['gregorian']) == ('law', '27.23', '1.25.03', '2025-02-20')
    # Since the housing plan (H5), an order the contents missed is found by its own heading too.
    assert (order['kind'], order['printed'], order['gregorian']) == ('order', '148.25', '2025-01-13')
    assert [a['label'] for a in p['item']['articles']] == ['المادة الأولى', 'المادة الثانية']
    assert 'قرار' not in p['item']['articles'][-1]['body']     # the next text's heading ends the cut
    assert p['host'].pk == host.pk


def test_the_repair_loads_the_law_gives_the_host_its_words_back_and_survives_a_reload(issue):
    recut.repair(issue, log=lambda *a: None)
    law = Text.objects.get(akn_uri='/akn/ma/act/loi/27-23')
    assert law.title_ar.startswith('قانون رقم 27.23 بتغيير وتتميم القانون رقم 18.12')
    assert law.promulgating_dahir == '1.25.03' and law.signed_on == date(2025, 2, 20)
    assert list(Article.objects.filter(version__text=law).values_list('label', flat=True)) == ['المادة الأولى', 'المادة الثانية']
    host = Article.objects.get(version__text__akn_uri='/akn/ma/act/loi/10-20', eid='art_2')
    assert host.body == 'يدخل هذا القانون حيز التنفيذ من تاريخ نشره.'
    assert recut.plan(issue) == []
    saved = json.loads((recut.workdir(issue) / 'texts.json').read_text())
    load_texts(issue, saved)                     # a reload of the issue keeps the repair
    assert Article.objects.get(version__text__akn_uri='/akn/ma/act/loi/10-20', eid='art_2').body == host.body
    assert Article.objects.filter(version__text__akn_uri='/akn/ma/act/loi/27-23').count() == 2


def test_an_order_is_found_by_its_heading_its_number_read_the_right_way_and_a_promulgation_left_to_its_law(issue):
    lines = [(1531, 'قرار لوزير التشغيل رقم 25.148 صادر في 12 من رجب 1446 (13 يناير 2025) بتتميم لائحة.'), (1531, 'وزير التشغيل،'),
             (1531, 'ظهير شريف رقم 1.24.65 صادر في 11 من جمادى الآخرة 1446 (13 ديسمبر 2024) بتنفيذ قانون المالية رقم 60.24'),
             (1531, 'الحمد لله وحده،')]
    [order] = recut.heads(issue, lines)
    assert (order['kind'], order['printed'], order['gregorian']) == ('order', '148.25', '2025-01-13')


def test_the_repair_ends_the_host_at_the_first_heading_it_swallowed(issue):
    recut.repair(issue, log=lambda *a: None)
    order = Text.objects.get(number_as_printed='148.25')
    assert order.title_ar.startswith('قرار لوزير التشغيل رقم 148.25 صادر في 12 من رجب 1446 (13 يناير 2025)')
    assert list(Article.objects.filter(version__text=order).values_list('body', flat=True)) == ['تتمم اللائحة.']
    law = Text.objects.get(akn_uri='/akn/ma/act/loi/27-23')
    assert 'قرار' not in Article.objects.filter(version__text=law).last().body
