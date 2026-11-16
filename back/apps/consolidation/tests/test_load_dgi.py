"""`load_dgi`: the DGI's yearly edition of the tax code, its Arabic read into a version of the code, its French beside
it, and each finance law a French footnote names written as a witness that it changed the article (Change, «dgi»)."""
import datetime
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.consolidation.models import Change
from apps.consolidation.services import dgi, layer
from apps.consolidation.tests.files import lexicon, word_pdf
from apps.corpus.models import Consolidation, Text
from apps.sources.models import Document
from apps.translations.models import FrenchArticle, FrenchText

pytestmark = pytest.mark.django_db
S, MARK, FOOT = 10, 6, 8         # the edition's text, a footnote's mark, the footnotes

# The Arabic edition's first page, in the shapes its layer gives: the table of contents, a preface, a book, headings
# printed in visual order, a heading alone on its line with its title (or «(تنسخ)») on the next, a reference to an
# article that only looks like a heading, a footnote set at the text's size, a mark on its own line, the running head,
# two headings out of the page's order.
FIRST = [
    [('المدونة العامة للضرائب', S)],
    [('المادة 1.- تعريف ............ 5', S)],
    [('تقديم هذه الطبعة.', S)],
    [('الكتاب الأول: قواعد الوعاء', S)],
    [('المادة -.1 تعريف', S)],
    [('تطبق هذه المدونة على الضرائب.', S), ('1', MARK)],
    [('المادة 2', S)],
    [('الأشخاص الخاضعون', S)],
    [('يخضع للضريبة كل شخص كما هو منصوص عليه في', S)],
    [('المادة 5', S)],
    [('أعلاه.', S)],
    [('المادة .3 - المبالغ', S)],
    [('يخصم ما قدره 600 درهم. تم إدراج هذه الفقرة بمقتضى البند I من المادة 7 من قانون المالية لسنة 2026', S)],
    [('2', MARK)],
    [('126 المدونة العامة للضرائب', S)],
    # The layer gives art. 5's heading before art. 4's: the articles are put back in their order.
    [('المادة 5', S)],
    [('يحدد السعر في %10 من المبلغ.', S), ('2', MARK)],
    [('المادة 7 - III أدناه بتخفيض المبلغ.', S)],
    [('المادة 4', S)],
    [('(تنسخ)', S)],
    [('نص لم يعد ساريا.', S)],
    [('1 - تم تغيير هذه المادة بمقتضى المادة 8 من قانون المالية رقم 60.24 للسنة المالية 2025', FOOT)],
    [('2 - أضيفت هذه الفقرة بمقتضى المادة 7 من قانون المالية رقم 50.25', FOOT)],
]
# The finance laws' provisions the edition annexes after the code: other texts, not read.
ANNEX = [[('المقتضيات الجبائية المتعلقة بالمدونة العامة للضرائب', S)], [('المادة -.6 أحكام انتقالية', S)],
         [('تطبق هذه الأحكام على السنة المالية.', S)]]


def filler(first: int, last: int) -> list[list[list[tuple[str, float]]]]:
    """Articles `first` to `last`, a heading and a line each, forty lines a page."""
    lines = [line for n in range(first, last + 1) for line in ([(f'المادة -.{n} حكم', S)], [('نص هذه المادة.', S)])]
    return [lines[k:k + 40] for k in range(0, len(lines), 40)]


# The French edition: a preface that names a finance law's article before the code's own «Article premier», the running
# head and the divisions printed among an article's words, a repealed article, and the footnotes that name the finance
# law that gave each passage its words (two in one note, one carried on to the next line).
FRENCH = [
    [[('PRÉFACE', S)], [('La présente édition est mise à jour par la Direction Générale des Impôts au premier janvier.', S)],
     [('Article 5 de la loi de finances n° 43-06 pour l’année budgétaire 2007.', S), ('1', MARK)],
     [('1 Article 5 de la loi de finances n° 43-06 pour l’année budgétaire 2007', FOOT)]],
    [[('Article premier.- Champ d’application', S)], [('Le présent code regroupe les impôts.', S), ('2', MARK)],
     [('7 CODE GÉNÉRAL DES IMPÔTS', S)],
     [('2 Article 8 de la loi de finances n° 60-24 pour l’année budgétaire 2025', FOOT)]],
    [[('Article 2.- Personnes imposables', S)],
     [('Sont soumises à l’impôt les sociétés. TITRE II L’IMPOT SUR LE REVENU', S), ('3', MARK), ('4', MARK)],
     [('3 Articles 7 et 9 des lois de finances respectives n° 43-10 et n° 115-12', FOOT)],
     [('pour les années budgétaires 2011 et 2013', FOOT)],
     [('4 Article 7 de la loi de finances n° 43-10 pour l’année budgétaire 2011', FOOT)]],
    [[('Article 3.- (abrogé) IV.- REGIME DE L’AUTO-ENTREPRENEUR', S)], [('Article 4.- Taux', S)],
     [('Le taux est fixé à 20%.', S), ('5', MARK)],
     [('5 Article 6 de la loi de finances n° 48-09 pour l’année budgétaire 2010', FOOT)],
     [('120 dirhams par an.', FOOT)]],
]


@pytest.fixture
def corpus(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    lexicon(tmp_path, [t for line in FIRST + ANNEX + filler(6, 6)[0] for t, _ in line])
    layer.lexicon.cache_clear()
    word_pdf(tmp_path / 'sources' / 'dgi' / 'cgi_2026_fr.pdf', FRENCH, rtl=False)
    yield tmp_path
    layer.lexicon.cache_clear()


def load(*args):
    out = StringIO()
    call_command('load_dgi', *args, stdout=out)
    return out.getvalue()


def test_the_arabic_editions_shapes_are_read_into_articles_and_too_few_are_refused(corpus):
    path = word_pdf(corpus / 'sources' / 'dgi' / 'cgi_2026_ar.pdf', [FIRST])
    read = dgi.read(str(path))
    assert [(a.label, a.heading_path, a.lines) for a in read.text.articles] == [
        ('المادة 1', ['الكتاب الأول: قواعد الوعاء', 'تعريف'], ['تطبق هذه المدونة على الضرائب.']),
        # «المادة 5» alone on a line, «أعلاه.» after it: a reference that goes on with the sentence.
        ('المادة 2', ['الكتاب الأول: قواعد الوعاء', 'الأشخاص الخاضعون'],
         ['يخضع للضريبة كل شخص كما هو منصوص عليه في المادة 5 أعلاه.']),
        # The footnote set at the text's size leaves the body; the mark on its own line went to the words before it.
        ('المادة 3', ['الكتاب الأول: قواعد الوعاء', 'المبالغ'], ['يخصم ما قدره 600 درهم.']),
        # Nothing after a repeal is the article's.
        ('المادة 4', ['الكتاب الأول: قواعد الوعاء'], ['(تنسخ)']),
        # A heading alone whose next line ends a sentence has no title; «المادة 7 - III أدناه» is a reference.
        ('المادة 5', ['الكتاب الأول: قواعد الوعاء'], ['يحدد السعر في 10% من المبلغ.', 'المادة 7 - III أدناه بتخفيض المبلغ.'])]
    # Each footnote goes to the first article whose words carry its mark.
    assert [(f.number, f.article) for f in read.footnotes] == [(1, 'المادة 1'), (2, 'المادة 3')]
    with pytest.raises(CommandError, match=r'^sources/dgi/cgi_2026_ar\.pdf: only 5 articles read$'):
        load('sources/dgi/cgi_2026_ar.pdf', 'sources/dgi/cgi_2026_fr.pdf', '--as-of', '2026-01-01')
    assert not Text.objects.exists()


def test_a_file_that_is_not_there_is_refused(corpus):
    with pytest.raises(CommandError, match=r'^sources/dgi/cgi_2027_ar\.pdf: not found$'):
        load('sources/dgi/cgi_2027_ar.pdf', 'sources/dgi/cgi_2026_fr.pdf', '--as-of', '2027-01-01')


def test_the_edition_becomes_the_codes_version_its_french_beside_it_and_its_notes_witnesses(corpus):
    word_pdf(corpus / 'sources' / 'dgi' / 'cgi_2026_ar.pdf', [FIRST] + filler(6, 200) + [ANNEX])
    said = load('sources/dgi/cgi_2026_ar.pdf', 'sources/dgi/cgi_2026_fr.pdf', '--as-of', '2026-01-01')
    text = Text.objects.get(akn_uri='/akn/ma/act/code/cgi')
    assert (text.type, text.title_ar, text.title_fr) == ('law', 'المدونة العامة للضرائب', 'Code général des impôts')
    version = text.versions.get()
    arabic = Document.objects.get(path='sources/dgi/cgi_2026_ar.pdf')
    french_doc = Document.objects.get(path='sources/dgi/cgi_2026_fr.pdf')
    assert (version.language, version.consolidation, version.valid_from, version.source_document, version.source_pages) == (
        'ar', Consolidation.DGI, datetime.date(2026, 1, 1), arabic, '1-12')
    articles = list(version.articles.order_by('order').values_list('order', 'label', 'number', 'eid', 'heading_path',
                                                                    'body', 'printed_page'))
    book = 'الكتاب الأول: قواعد الوعاء'
    assert articles[:6] == [
        (1, 'المادة 1', '1', 'art_1', [book, 'تعريف'], 'تطبق هذه المدونة على الضرائب.', 1),
        (2, 'المادة 2', '2', 'art_2', [book, 'الأشخاص الخاضعون'], 'يخضع للضريبة كل شخص كما هو منصوص عليه في المادة 5 أعلاه.', 1),
        (3, 'المادة 3', '3', 'art_3', [book, 'المبالغ'], 'يخصم ما قدره 600 درهم.', 1),
        (4, 'المادة 4', '4', 'art_4', [book], '(تنسخ)', 1),
        (5, 'المادة 5', '5', 'art_5', [book], 'يحدد السعر في 10% من المبلغ.\nالمادة 7 - III أدناه بتخفيض المبلغ.', 1),
        (6, 'المادة 6', '6', 'art_6', [book, 'حكم'], 'نص هذه المادة.', 2)]
    # The annexed provisions after the code are left out: its last article is 200, on the edition's eleventh page.
    assert len(articles) == 200 and articles[-1] == (200, 'المادة 200', '200', 'art_200', [book, 'حكم'], 'نص هذه المادة.', 11)
    for doc, language in ((arabic, 'ar'), (french_doc, 'fr')):
        assert (doc.source, doc.kind, doc.language, doc.url) == ('dgi', 'consolidated_text', language, 'https://www.tax.gov.ma')
    assert arabic.meta['as_of'] == '2026-01-01'
    assert arabic.meta['layer']['unknown'] == 0 and arabic.meta['layer']['words'] > 600
    # The French text is the one the French BO first printed: finance law 43-06's, BO 5487 bis of 1 January 2007.
    french = FrenchText.objects.get(text_uri=text.akn_uri)
    assert (french.type, french.number, french.title, french.signed_on, french.issue_number, french.issue_suffix,
            french.issue_date, french.document_sha, french.pages, french.consolidated_to) == (
        'law', '', 'Code général des impôts', datetime.date(2006, 12, 31), 5487, 'bis', datetime.date(2007, 1, 1),
        french_doc.sha256, '1-4', datetime.date(2026, 1, 1))
    assert list(FrenchArticle.objects.order_by('order').values_list(
        'text_uri', 'order', 'label', 'number', 'body', 'printed_page')) == [
        (text.akn_uri, 1, 'Article premier', '1', 'Champ d’application Le présent code regroupe les impôts.', 2),
        (text.akn_uri, 2, 'Article 2', '2', 'Personnes imposables Sont soumises à l’impôt les sociétés.', 3),
        (text.akn_uri, 3, 'Article 3', '3', '(abrogé)', 4),
        (text.akn_uri, 4, 'Article 4', '4', 'Taux Le taux est fixé à 20%.', 4)]
    # The preface's note (the finance law that made the code) is no article's; a law two notes of one article name is one
    # witness.
    assert {uri for uri, in Change.objects.values_list('text_uri')} == {text.akn_uri}
    assert list(Change.objects.order_by('id').values_list('number', 'verb', 'source', 'by_kind', 'by_number', 'by_uri',
                                                          'by_article')) == [
        ('1', 'modified', 'dgi', 'law', '60-24', '/akn/ma/act/loi/60-24', '8'),
        ('2', 'modified', 'dgi', 'law', '43-10', '/akn/ma/act/loi/43-10', '7'),
        ('2', 'modified', 'dgi', 'law', '115-12', '/akn/ma/act/loi/115-12', '9'),
        ('4', 'modified', 'dgi', 'law', '48-09', '/akn/ma/act/loi/48-09', '6')]
    assert said.startswith('/akn/ma/act/code/cgi: 200 articles (Arabic), 4 French, 5 footnotes, 4 witnesses; layer ')
    assert said.rstrip().endswith('(new text)')
    # Next year's edition loaded over it replaces the version, the French articles and the witnesses it gave.
    said = load('sources/dgi/cgi_2026_ar.pdf', 'sources/dgi/cgi_2026_fr.pdf', '--as-of', '2027-01-01')
    assert not said.rstrip().endswith('(new text)')
    assert list(text.versions.values_list('valid_from', flat=True)) == [datetime.date(2027, 1, 1)]
    assert FrenchArticle.objects.count() == 4 and Change.objects.count() == 4
    assert FrenchText.objects.get().consolidated_to == datetime.date(2027, 1, 1)
