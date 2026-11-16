"""FX6 of the mended-Bulletin review: every article in its text."""
from datetime import UTC, date, datetime

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.services import articles
from apps.quality.models import Correction
from apps.sources.models import Document, Issue, Page

pytestmark = pytest.mark.django_db


def kif_dahir(page_text, labels, preamble=''):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='h2512', path='BO_2512.pdf',
                                  mime='application/pdf', bytes=1, language='ar', page_count=1,
                                  fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    issue = Issue.objects.create(edition='general_ar', number=2512, date=date(1960, 12, 16), document=doc,
                                 first_page_number=3749)
    Page.objects.create(document=doc, index=2, printed_number=3751, kind='scan', text=page_text)
    text = Text.objects.create(akn_uri='/akn/ma/act/dahir/1-60-138', type='dahir', number='1-60-138',
                               title_ar='ظهير شريف', first_published_in=issue, first_published_page=3751)
    v = Version.objects.create(text=text, language='ar', valid_from=issue.date, source_pages='3751-3751',
                               preamble=preamble, consolidation=Consolidation.AS_PUBLISHED)
    for k, (label, body) in enumerate(labels, 1):
        Article.objects.create(version=v, order=k, label=label, eid=f'art_{k}', body=body, printed_page=3751)
    return v


PAGE = ('أصدرنا أمرنا الشريف بما يأتي :\n« الفصل الاول\nيمنح ماسكو الكيف في المنطقة السابقة للحماية الإسبانية '
        'تعويضا قدره أربعة دراهم\nالفصل الثانى\nيباشر دفع هذا التعويض مكتب التبغ بمجرد تسلمه تلك المنتوجات')


def test_an_article_number_whatever_its_spelling():
    assert [articles.number_of(x) for x in ('الفصل الثانى', 'الفصل الحادى عشر', 'المادة 3', 'فصل فريد')] == [2, 11, 3, None]


def test_articles_get_the_number_their_label_carries():
    kif_dahir(PAGE, [('الفصل الثانى', 'يباشر دفع هذا التعويض مكتب التبغ بمجرد تسلمه تلك المنتوجات')])
    assert articles.numbers(write=True) == 1
    assert Article.objects.get().number == '2'


def test_article_one_comes_back_from_its_page_and_addresses_follow():
    v = kif_dahir(PAGE, [('الفصل الثانى', 'يباشر دفع هذا التعويض مكتب التبغ بمجرد تسلمه تلك المنتوجات')])
    Correction.objects.create(path='/ma/dahir/1-60-138/art_1', wrong='التنبخ', right='التبغ', source='page',
                              status='applied')
    assert articles.problems()['missing'] == [v]
    assert articles.restore_first(v)
    rows = list(v.articles.order_by('order').values_list('eid', 'label', 'body'))
    assert rows[0][:2] == ('art_1', 'الفصل الاول') and rows[0][2].startswith('يمنح ماسكو الكيف')
    assert 'الإسبانية' in rows[0][2]                                     # as printed, not folded
    assert rows[1][:2] == ('art_2', 'الفصل الثانى')
    assert Correction.objects.get().path == '/ma/dahir/1-60-138/art_2'   # the correction follows its article


def test_an_article_one_after_article_two_goes_first():
    v = kif_dahir(PAGE, [('الفصل الثانى', 'يباشر دفع هذا التعويض'), ('الفصل الاول', 'يمنح ماسكو الكيف')])
    assert articles.problems()['late'] == [v]
    assert articles.put_in_order(v)
    assert list(v.articles.order_by('order').values_list('eid', 'label')) == [('art_1', 'الفصل الاول'),
                                                                             ('art_2', 'الفصل الثانى')]


def test_an_article_one_in_the_preamble_comes_out():
    v = kif_dahir(PAGE, [('الفصل الثاني', 'يباشر دفع هذا التعويض')],
                  preamble='بمقتضى الظهير الشريف المؤرخ في 24 أبريل 1954\nأصدرنا أمرنا الشريف بما يأتي :\nالفصل الأول\nيمنح ماسكو الكيف')
    assert articles.problems()['preamble'] == [v]
    assert articles.split_preamble(v)
    v.refresh_from_db()
    assert v.preamble.endswith('بما يأتي :')
    assert list(v.articles.order_by('order').values_list('eid', 'body')) == [('art_1', 'يمنح ماسكو الكيف'),
                                                                            ('art_2', 'يباشر دفع هذا التعويض')]
