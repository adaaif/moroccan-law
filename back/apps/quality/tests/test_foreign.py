"""T3 of the work plan: a word read with letters of another alphabet is fixed from the page's second reading when that
reading prints, between the same neighbours, an Arabic word the BO prints elsewhere."""
from collections import Counter
from datetime import UTC, date, datetime

import pytest
from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.quality.models import Correction
from apps.quality.services import foreign
from apps.quality.services.corrections import put_right
from apps.sources.models import Document, OcrRun, Page

pytestmark = pytest.mark.django_db


def test_the_second_reading_fixes_a_word_with_hebrew_letters_and_a_doubtful_one_waits():
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='b' * 64, path='x.pdf', mime='application/pdf',
                                  language='ar', bytes=1, fetched_at=timezone.now())
    kept = 'ينشر هذا المرسوم بالجريدة الرسمية. وحרר بالرباط في 3 مارس 2025.\nكما تحدد الآجال مدdownهما ومعاملاتهما.'
    page = Page.objects.create(document=doc, index=0, printed_number=1525, kind='text', text=kept)
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='columns-3192', text=kept)
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='page-1596',
                          text='ينشر هذا المرسوم بالجريدة الرسمية.\nوحرر بالرباط في 3 مارس 2025.\nكما تحدد الآجال مدىهما ومعاملاتهما.')
    text = Text.objects.create(akn_uri='/akn/ma/act/decret/2-25-1', type='decree', number='2-25-1', title_ar='مرسوم')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2025, 3, 3), consolidation=Consolidation.AS_PUBLISHED,
                               source_document=doc)
    Article.objects.create(version=v, order=1, label='المادة الأولى', number='1', eid='art_1', body=kept, printed_page=1525)
    counts = foreign.suggest(words=Counter({'وحرر': 900, 'مدىهما': 0}), log=lambda *a: None)
    assert counts == {'flagged': 2, 'applied': 1, 'waiting': 1}
    fixed = Correction.objects.get(wrong='وحרר')
    assert (fixed.right, fixed.status, fixed.source, fixed.evidence['page']) == ('وحرر', 'applied', 'witness', 1525)
    assert Correction.objects.get(wrong='مدdownهما').status == 'suggested'
    assert foreign.apply_witnessed() == 1
    assert 'وحرر بالرباط' in Article.objects.get(version=v).body


def test_a_word_with_latin_letters_is_put_right_as_it_stands():
    c = Correction(wrong='دirhماً', right='درهما')
    assert put_right('ستة عشر دirhماً وتسعة', c) == 'ستة عشر درهما وتسعة'


def test_a_fix_that_only_adds_words_is_never_applied_twice():
    # 58.25's division heading had lost its second half; a machine version copies the corrected heading and puts it
    # right again (the health review, S4).
    c = Correction(wrong='القسم الثاني: المحاكم الابتدائية', right='القسم الثاني: المحاكم الابتدائية والأقسام المتخصصة')
    once = put_right('القسم الثاني: المحاكم الابتدائية', c)
    assert once == c.right and put_right(once, c) == c.right
    assert put_right(f'{c.right} ثم القسم الثاني: المحاكم الابتدائية', c) == f'{c.right} ثم {c.right}'


def test_a_witness_needs_both_neighbours_an_arabic_word_and_the_misreadings_own_ends():
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='c' * 64, path='y.pdf', mime='application/pdf',
                                  language='ar', bytes=1, fetched_at=timezone.now())
    kept = 'وحרר بالرباط. تحدد الآجال مدdownهما ومعاملاتهما. شهادة البaccalوريا العلمية. ثم ذكرת هنا.'
    # The first page holds the misreadings with no second reading; the next one was read twice more.
    Page.objects.create(document=doc, index=0, printed_number=10, kind='scan', text=kept)
    page = Page.objects.create(document=doc, index=1, printed_number=11, kind='scan', text=kept)
    # In the order they are asked, newest first: the reading kept, a failed one, one with no Arabic word or other ends
    # there, then the one that witnesses.
    for minute, (variant, text) in enumerate((
            ('columns-3192', kept), ('page-1596', ''),
            ('strips', 'تحدد الآجال مدى2هما ومعاملاتهما. شهادة الثانوية العلمية.'),
            ('page-3192', 'وحرر بالرباط. تحدد الآجال مداهما ومعاملاتهما. شهادة الباكالوريا العلمية.'))):
        run = OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant=variant, text=text)
        OcrRun.objects.filter(pk=run.pk).update(created_at=datetime(2026, 11, 1, 10, 59 - minute, tzinfo=UTC))
    text = Text.objects.create(akn_uri='/akn/ma/act/decret/2-25-9', type='decree', number='2-25-9', title_ar='مرسوم')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2025, 3, 3), consolidation=Consolidation.AS_PUBLISHED,
                               source_document=doc)
    Article.objects.create(version=v, order=1, label='المادة الأولى', number='1', eid='art_1', body=kept)
    Correction.objects.create(path='/ma/decret/2-25-9/art_1', wrong='ذكرת', right='ذكرت', source='review')
    # A second reading that holds the misreading too, elsewhere, is no witness for it.
    other = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='d' * 64, path='z.pdf', mime='application/pdf',
                                    language='ar', bytes=1, fetched_at=timezone.now())
    misread = 'يحدد الأجل حسب الحا' + 'ל' + 'ة للعمل.'
    page = Page.objects.create(document=other, index=0, printed_number=12, kind='scan', text=misread)
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='page-3192',
                          text='يحدد الأجل حسب الحالة للعمل. انظر الحا' + 'ל' + 'ة.')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2025, 4, 3), consolidation=Consolidation.AS_PUBLISHED,
                               source_document=other)
    Article.objects.create(version=v, order=1, label='المادة الأولى', number='1', eid='art_1', body=misread)
    counts = foreign.suggest(words=Counter({'مداهما': 1, 'الباكالوريا': 5, 'الحالة': 9}), log=lambda *a: None)
    # «وحרר» opens the article: no word before it to find it by.
    assert counts == {'flagged': 5, 'no witness': 2, 'waiting': 1, 'applied': 1, 'known': 1}
    made = {c.wrong: (c.right, c.status, c.evidence) for c in Correction.objects.filter(source='witness')}
    assert made == {'مدdownهما': ('مداهما', 'suggested', {'page': 11, 'engine': 'claude-haiku-5-5', 'variant': 'page-3192',
                                                          'printed': 1}),
                    'البaccalوريا': ('الباكالوريا', 'applied', {'page': 11, 'engine': 'claude-haiku-5-5',
                                                               'variant': 'page-3192', 'printed': 5})}
    assert foreign.apply_witnessed() == 1
    assert 'شهادة الباكالوريا العلمية' in Article.objects.get(version__source_document=doc).body
    assert foreign.apply_witnessed() == 0                                # already right
