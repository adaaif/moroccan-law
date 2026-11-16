"""The commands that cut an issue's texts again from its page readings (T3 of the work plan, and after a fix to how
lines are read): `recut_swallowed` names the texts the contents missed and loads them with --write, `recut_texts`
cuts each text of texts.json again, `reload_issues` loads issues again from their texts.json. Each names what it would
do first."""
import json
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.tests.test_recut import issue  # noqa: F401  (the fixture: BO 7383, 27.23 swallowed by 10.20)
from apps.sources.models import Document, Edition, Issue, Page

pytestmark = pytest.mark.django_db


def run(*args, **opts) -> str:
    out = StringIO()
    call_command(*args, stdout=out, **opts)
    return out.getvalue()


def test_recut_swallowed_names_the_texts_then_loads_them_with_write(issue):
    said = run('recut_swallowed', issue=7383)
    assert '7383: law 27.23 p.1531, 2 articles, its dahir in /akn/ma/act/loi/10-20 المادة 2' in said
    assert '7383: order 148.25 p.1531, 1 articles, dropped' in said        # no article holds its heading's words
    assert said.endswith('2 texts to cut again, 0 left alone\n') and not Text.objects.filter(number='27-23').exists()
    # Only issues holding a text with a title and nothing under it: this one holds none.
    assert run('recut_swallowed', '--empty') == '0 texts to cut again, 0 left alone\n'

    before = _texts_json(issue).read_text()
    said = run('recut_swallowed', '--write', '--no-files', issue=7383)
    assert "'hosts': 1" in said
    assert list(Article.objects.filter(version__text__akn_uri='/akn/ma/act/loi/27-23').order_by('order')
                .values_list('label', flat=True)) == ['المادة الأولى', 'المادة الثانية']
    assert not Article.objects.filter(version__text__akn_uri='/akn/ma/act/loi/10-20', body__contains='27.23').exists()
    assert _texts_json(issue).read_text() == before                         # --no-files: the database alone


def test_recut_swallowed_leaves_alone_what_is_quoted_reprinted_misnumbered_or_without_articles(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    page = '\n'.join([
        'استدراك خطإ وقع في الجريدة الرسمية',
        'قرار لوزير الفلاحة رقم 3770.18 صادر في 12 من رجب 1446 (13 يناير 2025) بتتميم لائحة.',
        'المادة الأولى', 'تتمم اللائحة.',
        'ظهير شريف رقم 1.16.10 صادر في 2 جمادى الأولى 1437 (10 فبراير 2016) بتنفيذ القانون رقم 48.15 المتعلق بالكهرباء.',
        'المادة الأولى', 'نص.',
        'قرار لوزير التشغيل رقم 1482 صادر في 12 من رجب 1446 (13 يناير 2025) بتحديد لائحة.',
        'المادة الأولى', 'نص.',
        'مرسوم رقم 2.25.100 صادر في 12 من رجب 1446 (13 يناير 2025) بتحديد شروط منح الرخص الإدارية للمهن.',
        'لا مادة هنا، بل كلام متصل.',
        'مرسوم رقم 2.25.101 صادر في 12 من رجب 1446 (13 يناير 2025) بتحديد لائحة المهن المنظمة.',
        'المادة الأولى', 'المادة 2',
        'مرسوم رقم 2.25.102 صادر في 12 من رجب 1446 (13 يناير 2025) بتحديد شروط ممارسة مهنة التمريض في القطاع الخاص.',
        'المادة الأولى', 'تحدد الشروط.',
        'ظهير شريف رقم 1.22.70 صادر في 12 من رجب 1446 (13 يناير 2025) بتنفيذ القانون التنظيمي رقم 14.22 المتعلق بالمحكمة.',
        'الحمد لله وحده،', 'قانون تنظيمي رقم 48.22', 'يتعلق بالمحكمة الدستورية', 'المادة الأولى', 'نص.'])
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='7384'.ljust(64, '0'), path='BO_7384_ar.pdf',
                                  mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now(), page_count=2)
    Page.objects.create(document=doc, index=0, printed_number=1599, text='فهرست')
    Page.objects.create(document=doc, index=1, printed_number=1600, text=page)
    Issue.objects.create(edition=Edition.GENERAL_AR, number=7384, date=date(2025, 3, 6), document=doc,
                         first_page_number=1598)
    # The issue holds a decree on nursing under its right number, and organic law 48.22, read whole.
    nursing = Text.objects.create(akn_uri='/akn/ma/act/decret/2-25-120', type='decree', number='2-25-120',
                                  title_ar='مرسوم رقم 2.25.120 بتحديد شروط ممارسة مهنة التمريض في القطاع الخاص',
                                  first_published_page=1600)
    Version.objects.create(text=nursing, language='ar', valid_from=date(2025, 3, 6), source_document=doc,
                           consolidation=Consolidation.AS_PUBLISHED)
    court = Text.objects.create(akn_uri='/akn/ma/act/loi-organique/48-22', type='organic_law', number='48-22',
                                number_as_printed='48.22', title_ar='قانون تنظيمي رقم 48.22')
    v = Version.objects.create(text=court, language='ar', valid_from=date(2025, 3, 6), source_document=doc,
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='المادة الأولى', eid='art_1', body='نص.')
    said = run('recut_swallowed')
    assert said.splitlines() == [
        '7384: 3770.18 p.1600 left alone (quoted by a corrigendum)',
        '7384: 48.15 p.1600 left alone (signed long before the issue: a reprint, not its publication)',
        '7384: 1482 p.1600 left alone (a misread number (an order is numbered N.YY))',
        '7384: 2.25.100 p.1600 left alone (no article found in its pages)',
        '7384: 2.25.101 p.1600 left alone (its articles came out empty: read the pages again)',
        '7384: 2.25.102 p.1600 left alone (its subject titles a text on the same page)',
        '7384: 14.22 p.1600 left alone (held as 48.22)',
        '0 texts to cut again, 7 left alone']
    assert run('recut_swallowed', '--write').endswith('0 texts to cut again, 7 left alone\n')
    assert Text.objects.count() == 2


def test_recut_texts_cuts_each_text_again_and_writes_with_write(issue):
    path = _texts_json(issue)
    saved = json.loads(path.read_text())
    fresh = saved[0]['articles']
    whole = len(fresh)
    saved[0]['articles'] = saved[0]['articles'][:1]                      # a cut that lost its later articles
    path.write_text(json.dumps(saved, ensure_ascii=False))
    said = run('recut_texts', '7383')
    assert f': 1 → {whole} articles' in said and said.endswith(f'7383: {whole - 1} articles cut otherwise (not written)\n')
    assert len(json.loads(path.read_text())[0]['articles']) == 1
    assert run('recut_texts', '7383', '--write').endswith(f'7383: {whole - 1} articles cut otherwise\n')
    [item] = json.loads(path.read_text())
    assert item['articles'] == fresh and item['pages'] == [1530, 1531]
    assert run('recut_texts', '7383') == '7383: 0 articles cut otherwise (not written)\n'


def test_recut_texts_refuses_an_issue_with_no_texts_json(issue):
    _texts_json(issue).unlink()
    with pytest.raises(CommandError, match=r'7383: no texts\.json'):
        call_command('recut_texts', '7383')


def _texts_json(issue):
    from apps.corpus.services.recut import workdir
    return workdir(issue) / 'texts.json'


def test_reload_issues_without_write_names_the_shared_texts_and_leaves_covers_alone(issue):
    copy_doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='7383c'.ljust(64, '0'),
                                       path='BO_7383c.pdf', mime='application/pdf', language='ar', bytes=1,
                                       fetched_at=timezone.now())
    copy = Issue.objects.create(edition=Edition.GENERAL_AR, number=7383, suffix='bis', date=issue.date, document=copy_doc,
                                copy_of=issue)
    work = _texts_json(copy).parent
    work.mkdir(parents=True)
    (work / 'texts.json').write_text('[]')
    law = Text.objects.get(akn_uri='/akn/ma/act/loi/10-20')
    other = law.versions.get()
    other.pk, other.source_document = None, copy_doc
    other.valid_from = date(2025, 3, 4)
    other.save()
    said = run('reload_issues')
    assert said.splitlines() == ['2 covers and copies left as they are (--covers loads them)',
                                 '1 texts hold versions from two issues; 0 issues to load',
                                 '  /akn/ma/act/loi/10-20: ' + law.title_ar[:80]]
    assert law.versions.count() == 2                                     # a dry run changes nothing
