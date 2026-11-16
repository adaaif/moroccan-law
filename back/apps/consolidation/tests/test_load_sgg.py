"""`load_sgg_consolidated` (row 19): each SGG file read from its kept text layer into a version of its text, dated by the
last change it holds, and each article's notes into its history (Change, source «sgg»)."""
import datetime
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.consolidation.models import Change
from apps.corpus.models import Text
from apps.sources.models import Document, Page

pytestmark = pytest.mark.django_db
# The layer as the SGG's file gives it: brackets mirrored, a title whose number it lost (the list's title stands in).
COVER = 'تم إعداد هذه النسخة\nالقانون رقم 2.00\nصيغة موطدة بتاريخ\nسبتمبر 2026'
# Its articles' notes fall on three days: 10 August 2026 (the last before the file's date), 5 March 2025 (in a «مكرر»
# issue, by a decree, on an article that is only its note), and 12 October 2026, after the file's date.
BODY = ('1\nالأمانة العامة للحكومة\nالقانون رقم المتعلق بحقوق المؤلف\n'
        ')ج.ر عدد 4796 بتاريخ 14 من صفر 1421 )18 ماي 2000(، ص : 1112(\n'
        'الباب الأول: أحكام عامة\nالمادة 1\n)غيرت وتممت بموجب المادة الأولى من القانون رقم 013.26 الصادر بتنفيذه الظهير الشريف رقم 1.26.68؛ '
        'ج.ر عدد 7533 بتاريخ 26 من صفر 1448 )10 أغسطس 2026(، ص: 5141(\nيقصد بالمصطلحات المعاني التالية :\n'
        'المادة 2\n)نسخت بموجب المادة الثالثة من القانون رقم 20.26؛ ج.ر عدد 7560 بتاريخ 2 من ربيع الآخر 1448 '
        ')12 أكتوبر 2026(، ص: 6000(\nيسري هذا القانون على المصنفات الأدبية والفنية.')
LAST = ('الباب الثاني: أحكام ختامية\nالمادة 3\n)نسخت بموجب المادة 4 من المرسوم رقم 2.25.100؛ ج.ر عدد 7390 مكرر بتاريخ 4 '
        'رمضان 1446 )5 مارس 2025(، ص: 1500(')
NOTE_3 = ('(نسخت بموجب المادة 4 من المرسوم رقم 2.25.100؛ ج.ر عدد 7390 مكرر بتاريخ 4 رمضان 1446 (5 مارس 2025)، ص: 1500)')
# A text whose articles carry no note stands at the file's own date; a number printed twice keeps both articles apart.
UNNOTED = ('صيغة محينة بتاريخ 3 يونيو 2024', 'القانون رقم 9.88 المتعلق بالقواعد المحاسبية الواجب على التجار العمل بها\n'
           'المادة 1\nيجب على كل تاجر أن يمسك محاسبة.\nالمادة 1\nتمسك المحاسبة وفق القواعد المقررة.')


def sgg_file(stem, pages, title=''):
    doc = Document.objects.create(source='sgg_consolidated', kind='consolidated_text', sha256=stem.ljust(64, '0'),
                                  url=f'https://www.sgg.gov.ma/Portals/0/lois/{stem}_ar.pdf', path=f'sources/sgg/{stem}.pdf',
                                  mime='application/pdf', language='ar', bytes=1, page_count=len(pages),
                                  fetched_at=timezone.now(), title=title)
    Page.objects.bulk_create([Page(document=doc, index=k, kind='text', layer_text=p) for k, p in enumerate(pages)])
    return doc


def load(*args):
    out, err = StringIO(), StringIO()
    call_command('load_sgg_consolidated', *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def test_each_file_becomes_a_version_dated_by_its_last_change_and_its_notes_the_articles_history():
    listed = 'القانون رقم 2.00 المتعلق بحقوق المؤلف والحقوق المجاورة'
    doc = sgg_file('2_00', [COVER, BODY, LAST], title=listed)
    sgg_file('17_04', ['صفحة لا مادة فيها'])
    sgg_file('9_88', list(UNNOTED), title='Loi 9.88')
    said, warned = load()
    text = Text.objects.get(akn_uri='/akn/ma/act/loi/2-00')
    assert (text.title_ar, text.type, text.number, text.number_as_printed, text.status) == (
        listed, 'law', '2-00', '2.00', 'in_force')
    version = text.versions.get()
    # Dated by the last change it holds on its own date (September 2026), not the first: October's note is after it.
    assert (version.language, version.consolidation, version.valid_from, version.source_document, version.source_pages) == (
        'ar', 'sgg', datetime.date(2026, 8, 10), doc, '1-3')
    assert list(version.articles.order_by('order').values_list(
        'order', 'label', 'number', 'eid', 'heading_path', 'body', 'printed_page')) == [
        (1, 'المادة 1', '1', 'art_1', ['الباب الأول: أحكام عامة'], 'يقصد بالمصطلحات المعاني التالية :', 2),
        (2, 'المادة 2', '2', 'art_2', ['الباب الأول: أحكام عامة'], 'يسري هذا القانون على المصنفات الأدبية والفنية.', 2),
        # An article that is only its note reads as the note.
        (3, 'المادة 3', '3', 'art_3', ['الباب الثاني: أحكام ختامية'], NOTE_3, 3)]
    nine = Text.objects.get(akn_uri='/akn/ma/act/loi/9-88')
    assert nine.title_ar == 'القانون رقم 9.88 المتعلق بالقواعد المحاسبية الواجب على التجار العمل بها'
    assert nine.versions.get().valid_from == datetime.date(2024, 6, 3)
    assert list(nine.versions.get().articles.order_by('order').values_list('number', 'eid', 'body')) == [
        ('1', 'art_1', 'يجب على كل تاجر أن يمسك محاسبة.'), ('1', 'art_1_2', 'تمسك المحاسبة وفق القواعد المقررة.')]
    doc.refresh_from_db()
    assert {k: doc.meta[k] for k in ('stem', 'as_of', 'first_issue', 'first_page')} == {
        'stem': '2_00', 'as_of': '2026-09-01', 'first_issue': 4796, 'first_page': 1112}
    assert list(Change.objects.order_by('number').values_list(
        'text_uri', 'number', 'verb', 'source', 'by_kind', 'by_number', 'by_uri', 'by_article', 'issue', 'issue_bis', 'page',
        'published_on')) == [
        (text.akn_uri, '1', 'modified', 'sgg', 'law', '13-26', '/akn/ma/act/loi/13-26', 'المادة الأولى', 7533, False, 5141,
         datetime.date(2026, 8, 10)),
        (text.akn_uri, '2', 'repealed', 'sgg', 'law', '20-26', '/akn/ma/act/loi/20-26', 'المادة الثالثة', 7560, False, 6000,
         datetime.date(2026, 10, 12)),
        (text.akn_uri, '3', 'repealed', 'sgg', 'decree', '2-25-100', '/akn/ma/act/decret/2-25-100', 'المادة 4', 7390, True,
         1500, datetime.date(2025, 3, 5))]
    assert warned == '17_04: no articles read\n'
    lines = said.splitlines()
    layer = doc.meta['layer']
    assert lines[0] == (f"        2_00     3 articles    3 notes  from 2026-08-10  {layer['unknown']}/{layer['words']} words "
                        f'unknown  {text.akn_uri}')
    assert lines[1].startswith('        9_88     2 articles    0 notes  from 2024-06-03  ')
    assert lines[2] == "{'texts': 2, 'articles': 5, 'notes': 3, 'created': 2}"
    # Only the files named: the one loaded is left as it is.
    said, warned = load('--only', '17_04')
    assert said == "{'texts': 0, 'articles': 0, 'notes': 0, 'created': 0}\n" and warned == '17_04: no articles read\n'
    assert Change.objects.count() == 3 and text.versions.count() == 1
    # Run again, a file replaces its own version and notes.
    said, warned = load('--only', '2_00')
    assert said.endswith("{'texts': 1, 'articles': 3, 'notes': 3, 'created': 0}\n") and warned == ''
    assert Change.objects.count() == 3 and text.versions.count() == 1
