"""FX6 of the mended-Bulletin review, where the mending stops: an article 1 the pages do not show where it should stand, a
preamble whose article 1 is too short to be one, articles that cannot be ordered by number; and two articles of one
number keep two addresses."""
import pytest

from apps.corpus.models import Article, Text
from apps.corpus.services import articles
from apps.corpus.tests.test_articles_mended import PAGE, kif_dahir

pytestmark = pytest.mark.django_db


def again():
    """The next case on an empty corpus: kif_dahir makes the same issue each time."""
    from apps.sources.models import Document, Issue
    Text.objects.all().delete()
    Issue.objects.all().delete()
    Document.objects.all().delete()


def test_a_label_with_no_number_in_it_has_none():
    assert articles.number_of('') is None and articles.number_of('الفصل') is None
    assert articles.number_of('الفصل الأول') == 1


def test_article_one_is_not_taken_from_pages_that_do_not_show_it_before_article_two():
    empty = kif_dahir(PAGE, [])
    assert articles.found_first(empty) is None and not articles.restore_first(empty)
    again()
    # The first article's words are on the page, but no «الفصل الاول» heading stands before them.
    v = kif_dahir('أصدرنا أمرنا الشريف بما يأتي :\nيباشر دفع هذا التعويض مكتب التبغ بمجرد تسلمه',
                  [('الفصل الثانى', 'يباشر دفع هذا التعويض مكتب التبغ بمجرد تسلمه')])
    assert articles.found_first(v) is None
    again()
    # What stands between «الفصل الاول» and the first article holds another article's heading: not article 1 alone.
    v = kif_dahir('الفصل الاول\nيمنح تعويض\nالفصل الثالث\nنص\nالفصل الرابع\nيباشر دفع هذا التعويض مكتب التبغ بمجرد تسلمه',
                  [('الفصل الرابع', 'يباشر دفع هذا التعويض مكتب التبغ بمجرد تسلمه')])
    assert articles.found_first(v) is None


def test_articles_are_put_in_order_only_when_each_has_a_number_and_they_are_not():
    v = kif_dahir(PAGE, [('فصل فريد', 'نص'), ('الفصل الاول', 'نص')])
    assert not articles.put_in_order(v)
    again()
    v = kif_dahir(PAGE, [('الفصل الاول', 'نص'), ('الفصل الثانى', 'نص')])
    assert not articles.put_in_order(v)


def test_an_article_one_written_inline_in_the_preamble_comes_out_unless_too_short():
    v = kif_dahir(PAGE, [('الفصل الثاني', 'يباشر دفع هذا التعويض')],
                  preamble='بناء على الظهير الشريف، الفصل الأول: يمنح ماسكو الكيف تعويضا')
    assert articles.split_preamble(v)
    v.refresh_from_db()
    assert v.preamble == 'بناء على الظهير الشريف،'
    assert list(v.articles.order_by('order').values_list('eid', 'label', 'body')) == [
        ('art_1', 'الفصل الأول', 'يمنح ماسكو الكيف تعويضا'), ('art_2', 'الفصل الثاني', 'يباشر دفع هذا التعويض')]
    again()
    v = kif_dahir(PAGE, [('الفصل الثاني', 'نص')], preamble='بناء على الظهير، الفصل الأول: يعمل')
    assert not articles.split_preamble(v) and v.articles.count() == 1
    again()
    v = kif_dahir(PAGE, [('الفصل الثاني', 'نص')], preamble='بناء على الظهير الشريف')
    assert not articles.split_preamble(v)


def test_two_articles_of_one_number_keep_two_addresses_when_the_text_is_put_in_order():
    v = kif_dahir(PAGE, [('الفصل الثانى', 'ب'), ('الفصل الاول', 'أ'), ('الفصل الثانى', 'ج')])
    assert articles.put_in_order(v)
    assert list(Article.objects.filter(version=v).order_by('order').values_list('eid', 'body')) == [
        ('art_1', 'أ'), ('art_2', 'ب'), ('art_2_3', 'ج')]
