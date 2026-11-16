"""F1 of the family plan: corrections read against a page's image, recorded and applied from a YAML file."""
from datetime import UTC, date

import pytest
from django.core.management import call_command

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.quality.models import Correction

pytestmark = pytest.mark.django_db


def test_a_page_reading_puts_words_right_and_survives_a_reload(tmp_path):
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/70-03', type='law', number='70-03', title_ar='مدونة الأسرة')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2021, 7, 29), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='المادة 346', number='346', eid='art_346',
                           body='أصحاب الثلث ثالثة: الأخوات ألبوين وبنتا الإ بن.')
    spec = tmp_path / 'fixes.yaml'
    spec.write_text('text: /ma/loi/70-03\ndocument: samples/adala/adala_118.pdf\nread_on: "2026-10-20"\nfixes:\n'
                    '  - {arts: [346], wrong: ثالثة, right: ثلاثة}\n  - {arts: [346], wrong: ألبوين, right: لأبوين}\n'
                    '  - {arts: [346], wrong: الإ بن, right: الإبن}\n', encoding='utf-8')
    call_command('apply_page_reading', str(spec))
    assert Article.objects.get(eid='art_346').body == 'أصحاب الثلث ثلاثة: الأخوات لأبوين وبنتا الإبن.'
    c = Correction.objects.get(wrong='ثالثة')
    assert (c.source, c.status, c.evidence['read_on']) == ('page', 'applied', '2026-10-20')
    # Run again: nothing recorded twice.
    call_command('apply_page_reading', str(spec))
    assert Correction.objects.count() == 3


def test_a_heading_put_right_mends_every_article_it_stands_over_and_comes_back_after_a_reload(tmp_path):
    from apps.quality.services.corrections import reapply
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/70-03', type='law', number='70-03', title_ar='مدونة الأسرة')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2021, 7, 29), consolidation=Consolidation.ADALA)
    head = ['الكتاب الأول: الزواج', 'الباب الأول: الأهلية والوالية في الزواج']
    for n in (18, 19, 20):
        Article.objects.create(version=v, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}',
                               heading_path=head[:1] if n == 18 else head, body='الولاية حق للمرأة.')
    spec = tmp_path / 'fixes.yaml'
    spec.write_text('text: /ma/loi/70-03\ndocument: samples/adala/adala_118.pdf\nread_on: "2026-10-20"\nfixes: []\n'
                    'headings:\n  - {wrong: والوالية, right: والولاية}\n', encoding='utf-8')
    call_command('apply_page_reading', str(spec))
    assert Article.objects.get(eid='art_20').heading_path[1] == 'الباب الأول: الأهلية والولاية في الزواج'
    assert Correction.objects.get().path == '/ma/loi/70-03/art_19'      # listed where the heading first stands
    # A reload brings the misread heading back; the correction mends it again.
    Article.objects.filter(eid='art_20').update(heading_path=head)
    assert reapply(list(Article.objects.all()), text.akn_uri) == 1
    assert 'والولاية' in Article.objects.get(eid='art_20').heading_path[1]


def test_a_word_put_back_is_put_back_once(tmp_path):
    # T1 of the work plan: Adala's layer stops art. 217 at «بنص»; the page goes on «تنظيمي وأيام العطل».
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99', title_ar='مدونة الشغل')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 7, 16), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='المادة 217', number='217', eid='art_217',
                           body='تحدد قائمة الأعياد بنص.')
    spec = tmp_path / 'fixes.yaml'
    spec.write_text('text: /ma/loi/65-99\ndocument: sources/adala/labour_65_99.pdf\nread_on: "2026-10-20"\nfixes:\n'
                    '  - {arts: [217], wrong: الأعياد بنص, right: الأعياد بنص تنظيمي وأيام العطل}\n', encoding='utf-8')
    call_command('apply_page_reading', str(spec))
    call_command('apply_page_reading', str(spec))
    assert Article.objects.get().body == 'تحدد قائمة الأعياد بنص تنظيمي وأيام العطل.'


def test_mended_specs_put_pages_articles_by_address_and_dates_right(tmp_path):
    """FX2 of the mended-Bulletin review: several texts in one file, a page put right by its place in the file and kept
    right when the page is read again, an article without a number found by its address, a date, a cover no text holds."""
    from datetime import datetime

    from apps.quality.services.corrections import reapply_pages
    from apps.sources.models import Document, Issue, Page

    def bo(number):
        doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'h{number}', path=f'BO_{number}.pdf',
                                      mime='application/pdf', bytes=1, language='ar',
                                      fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
        return Issue.objects.create(edition='general_ar', number=number, date=date(1960, 12, 16), document=doc)

    issue = bo(2512)
    page = Page.objects.create(document=issue.document, index=2, kind='scan',
                               text='« الفصل الاول\nيمنع ماسكو الكيف في المنطقة السابقة\nالفصل الثانى\nمكتب التنبخ')
    cover = bo(1)
    Page.objects.create(document=cover.document, index=0, kind='scan', text='عدد 1 ثمن النسخة عشرون سانتيم')
    text = Text.objects.create(akn_uri='/akn/ma/act/dahir/1-60-138', type='dahir', number='1-60-138',
                               title_ar='ظهير شريف', first_published_in=issue, signed_on=date(1960, 12, 7))
    v = Version.objects.create(text=text, language='ar', valid_from=date(1960, 12, 16),
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='الفصل الثانى', number='', eid='art_1', body='يباشر مكتب التنبخ')
    spec = tmp_path / 'proven.yaml'
    spec.write_text('text: /ma/dahir/1-60-138\nread_on: "2026-11-02"\nsigned_on: "1960-12-06"\nfixes:\n'
                    '  - {eids: [art_1], wrong: مكتب التنبخ, right: مكتب التبغ}\npages:\n'
                    '  - {index: 2, wrong: يمنع ماسكو الكيف, right: يمنح ماسكو الكيف}\n---\n'
                    'issue: {edition: general_ar, number: 1}\nread_on: "2026-11-02"\npages:\n'
                    '  - {index: 0, wrong: ثمن النسخة عشرون سانتيم, right: ثمن الصحيفة عشرون صانتيم}\n', encoding='utf-8')
    call_command('apply_page_reading', str(spec))
    page.refresh_from_db()
    assert 'يمنح ماسكو الكيف' in page.text
    assert Article.objects.get(eid='art_1').body == 'يباشر مكتب التبغ'
    assert Text.objects.get(pk=text.pk).signed_on == date(1960, 12, 6)
    assert Page.objects.get(document=cover.document).text == 'عدد 1 ثمن الصحيفة عشرون صانتيم'
    assert Correction.objects.get(path='/bo/general_ar/2512#p2').source == 'page'
    # The page read again: the misreading comes back, the recorded correction puts it right again.
    page.text = '« الفصل الاول\nيمنع ماسكو الكيف في المنطقة السابقة'
    assert reapply_pages([page]) == 1 and 'يمنح' in page.text
    assert reapply_pages([page]) == 0                  # already right: nothing changes
    call_command('apply_page_reading', str(spec))      # run again: nothing recorded twice
    assert Correction.objects.count() == 3


SPEC = '''---
---
text: /ma/dahir/1-26-91
document: issues/bo_ar/BO_7554_ar.pdf
read_on: "2026-11-01"
fixes:
  - {arts: [1], wrong: بثالثة, right: بثلاثة}
  - {arts: [1, 2], wrong: الأجور, right: الأجرة}
  - {arts: [99], wrong: الفصل, right: المادة}
  - {arts: [2], wrong: ألم, right: لأم}
headings:
  - {wrong: والوالية, right: والولاية}
  - {wrong: والقوامة, right: والقيمومة}
title:
  - {wrong: الحكومه, right: الحكومة}
  - {wrong: رقم 1.62.91, right: رقم 1.26.91}
  - {wrong: بتنصيب, right: بتعين}
preamble:
  - {wrong: الفصل 74, right: الفصل 47}
  - {wrong: الدستور الجديد, right: الدستور}
  - {wrong: الظهير, right: المرسوم}
---
text: /ma/dahir/1-26-93
read_on: "2026-11-01"
title_is: ظهير شريف رقم 1.26.93 بتعيين كتاب الدولة
signed_on: "2026-10-30"
---
issue: {edition: general_ar, number: 7554, suffix: bis}
read_on: "2026-11-01"
pages:
  - {index: 0, wrong: الجريدة الرسمبة, right: الجريدة الرسمية}
  - {index: 5, wrong: عدد, right: العدد}
  - {index: 0, wrong: ثمن النسخة, right: ثمن العدد}
  - {index: 0, wrong: السنة 115, right: السنة 114}
'''


@pytest.fixture
def government(tmp_path):
    from datetime import datetime

    from apps.sources.models import Document, Issue, Page
    # The issue the file names is 7554 bis; 7554 itself is not touched.
    for suffix in ('', 'bis'):
        doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'h7554{suffix}', path=f'BO_7554{suffix}.pdf',
                                      mime='application/pdf', bytes=1, language='ar',
                                      fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
        Issue.objects.create(edition='general_ar', number=7554, suffix=suffix, date=date(2026, 11, 1), document=doc)
        Page.objects.create(document=doc, index=0, kind='scan', text='الجريدة الرسمبة السنة 114 عدد 7554')
    text = Text.objects.create(akn_uri='/akn/ma/act/dahir/1-26-91', type='dahir', number='1-26-91',
                               title_ar='ظهير شريف رقم 1.26.91 بتعيين أعضاء الحكومه')
    head = ['الباب الأول: الأهلية والوالية']
    for day, preamble in ((date(2026, 11, 1), 'بناء على الدستور ولا سيما الفصل 74 منه'),
                          (date(2026, 11, 2), 'بناء على الدستور ولا سيما الفصل 74 منه'),
                          (date(2026, 11, 3), 'بناء على الدستور ولا سيما الفصل 47 منه')):
        v = Version.objects.create(text=text, language='ar', valid_from=day, consolidation=Consolidation.AS_PUBLISHED,
                                   preamble=preamble)
        Article.objects.create(version=v, order=1, label='المادة 1', number='1', eid='art_1', heading_path=head,
                               body='تحدد الأجور بثالثة أشهر.')
        Article.objects.create(version=v, order=2, label='المادة 2', number='2', eid='art_2', heading_path=head,
                               body='ثم لأم الأم.')
    # A person applied the proofreader's correction to art. 2 already: the reading's fix finds nothing left to do.
    Correction.objects.create(path='/ma/dahir/1-26-91/art_2', wrong='ألم', right='لأم', before='ثم', after='الأم',
                              source='proofread', status='applied')
    Text.objects.create(akn_uri='/akn/ma/act/dahir/1-26-93', type='dahir', number='1-26-93', title_ar='ظهير شريف',
                        signed_on=date(2026, 10, 30))
    spec = tmp_path / 'government.yaml'
    spec.write_text(SPEC, encoding='utf-8')
    return text, spec


def test_a_reading_puts_right_articles_headings_title_preamble_and_pages_and_says_what_it_could_not(government):
    from io import StringIO

    from apps.sources.models import Page
    text, spec = government
    before = Text.objects.get(pk=text.pk).updated_at
    out = StringIO()
    call_command('apply_page_reading', str(spec), stdout=out)
    assert out.getvalue().splitlines() == [
        # Two words (in the article of each version: once each), six headings, the title, two preambles of three.
        '/ma/dahir/1-26-91: 4 corrections recorded, 11 articles changed',
        '  not applied: art. 99',
        '  not applied: art. 2: «ألم» not found',
        '  not applied: heading «والقوامة» not found',
        '  not applied: title: «بتنصيب» not found',
        '  not applied: preamble: «الظهير» not found',
        '/ma/dahir/1-26-93: 0 corrections recorded, 1 articles changed',
        'BO 7554-bis (general_ar): 3 page corrections recorded, 1 pages changed',
        '  not applied: page 5: no such page',
        '  not applied: page 0: «ثمن النسخة» not found']
    assert Text.objects.get(pk=text.pk).updated_at > before            # its answers kept before are stale
    assert sorted(Article.objects.values_list('body', flat=True)) == ['تحدد الأجرة بثلاثة أشهر.'] * 3 + ['ثم لأم الأم.'] * 3
    assert {tuple(h) for h in Article.objects.values_list('heading_path', flat=True)} == {('الباب الأول: الأهلية والولاية',)}
    assert Text.objects.get(pk=text.pk).title_ar == 'ظهير شريف رقم 1.26.91 بتعيين أعضاء الحكومة'
    assert set(Version.objects.values_list('preamble', flat=True)) == {'بناء على الدستور ولا سيما الفصل 47 منه'}
    assert Text.objects.get(akn_uri='/akn/ma/act/dahir/1-26-93').title_ar == 'ظهير شريف رقم 1.26.93 بتعيين كتاب الدولة'
    assert dict(Page.objects.values_list('document__issue__suffix', 'text')) == {
        'bis': 'الجريدة الرسمية السنة 114 عدد 7554', '': 'الجريدة الرسمبة السنة 114 عدد 7554'}
    # Run again: what was recorded is in the text already; only what could not be done is said again.
    out = StringIO()
    call_command('apply_page_reading', str(spec), stdout=out)
    assert out.getvalue().splitlines() == [
        '/ma/dahir/1-26-91: 0 corrections recorded, 0 articles changed',
        '  not applied: art. 99',
        '  not applied: heading «والقوامة» not found',
        '  not applied: title: «بتنصيب» not found',
        '  not applied: preamble: «الظهير» not found',
        '/ma/dahir/1-26-93: 0 corrections recorded, 0 articles changed',
        'BO 7554-bis (general_ar): 0 page corrections recorded, 0 pages changed',
        '  not applied: page 5: no such page',
        '  not applied: page 0: «ثمن النسخة» not found']


def test_a_reading_names_a_text_or_an_issue_the_corpus_holds(tmp_path):
    from django.core.management.base import CommandError
    spec = tmp_path / 'x.yaml'
    spec.write_text('text: /ma/loi/99-99\nread_on: "2026-11-01"\n', encoding='utf-8')
    with pytest.raises(CommandError, match='/ma/loi/99-99: no such text'):
        call_command('apply_page_reading', str(spec))
    spec.write_text('issue: {edition: general_ar, number: 9999, suffix: bis}\nread_on: "2026-11-01"\n', encoding='utf-8')
    with pytest.raises(CommandError, match="'number': 9999, 'suffix': 'bis'}: no such issue"):
        call_command('apply_page_reading', str(spec))
