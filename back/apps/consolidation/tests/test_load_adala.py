"""`load_adala`: an Adala file read from its Word text layer (or, when the layer is no text, from its page images) into a
version of its text, its footnotes kept on the document, and those that say what changed an article written as that
article's history (Change, source «adala»)."""
import datetime
import json
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.consolidation.models import Change
from apps.consolidation.services import layer
from apps.consolidation.tests.files import lexicon, tsv, word_pdf
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Document, DocumentKind, Source
from apps.sources.services.ingest import ingest_file
from apps.translations.tests.files import Tesseract

pytestmark = pytest.mark.django_db
B, MARK, FOOT = 16, 10, 13          # the law's size, a footnote mark's, the footnotes'


@pytest.fixture
def corpus(settings, tmp_path):
    """The corpus folder of this test, its lexicon read afresh (the reader keeps it once read)."""
    settings.CORPUS_DIR = tmp_path
    layer.lexicon.cache_clear()
    yield tmp_path
    layer.lexicon.cache_clear()


def register(corpus, name, pages, **kw):
    path = word_pdf(corpus / 'sources' / 'adala' / name, pages, **kw)
    ingest_file(path, source=Source.ADALA, kind=DocumentKind.CONSOLIDATED_TEXT, language='ar',
                url=f'https://adala.justice.gov.ma/api/uploads/{name}')
    return f'sources/adala/{name}'


def load(*args):
    out = StringIO()
    call_command('load_adala', *args, stdout=out)
    return out.getvalue()


# A code approved by a dahir, as the penal code's file prints it: the dahir's title on two lines (the second opening
# with its date in brackets, its mark on the BO footnote), the dahir's own articles, then the code's from 1 again.
PENAL = [
    [[('صيغة محينة بتاريخ 21 فبراير 2019', B)]],
    [[('ظهير شريف رقم 1.59.413 صادر في 28 جمادى الثانية 1382', B)],
     [('(26 نونبر 1962) بالمصادقة على مجموعة القانون الجنائي', B), ('1', MARK)],
     [('يصدر جنابنا الشريف بما يلي:', B)],
     [('الفصل الأول', B)],
     [('يصادق على مجموعة القانون الجنائي الملحقة بظهيرنا هذا.', B)],
     [('الفصل الثاني', B)],
     [('ينشر ظهيرنا هذا بالجريدة الرسمية.', B)],
     [('الفصل 1', B)],
     [('يحدد التشريع الجنائي أفعال الإنسان التي يعدها جرائم.', B), ('2', MARK)],
     [('- 1 -', 14)],
     [('1 - الجريدة الرسمية عدد 2640 مكرر بتاريخ 5 يونيو 1963، ص .1253؛ كما تم تغييره وتتميمه بمقتضى القانون رقم 33.18.',
       FOOT)],
     [('2 - انظر القرار رقم 269.04.', FOOT)]],
    [[('الجزء الأول: في الجريمة', B)],
     [('الفصل 2', B)],
     [('لا يسوغ لأحد أن يعتذر بجهله التشريع الجنائي.', B), ('3', MARK)],
     [('الفصل 3', B)],
     [('لا يسوغ مؤاخذة أحد على فعل لا يعد جريمة.', B), ('4', MARK)],
     [('- 2 -', 14)],
     [('3 - عوضت أحكام الفصل 2 أعلاه، بمقتضى المادة الفريدة من القانون رقم 65.21 الصادر بتنفيذه الظهير الشريف رقم '
       '1.21.70، الجريدة', FOOT)],
     [('الرسمية عدد 7006 مكرر بتاريخ 22 يوليو 2021، ص .5650', FOOT)],
     [('4 - نسخت الفقرة الثانية بمقتضى المادة الثانية من القانون الصادر بتنفيذه الظهير الشريف رقم 1.20.91، الجريدة '
       'الرسمية عدد 6948، ص .8642', FOOT)]],
]


def words_of(pages):
    return [t for lines in pages for runs in lines for t, _ in runs]


def test_a_code_approved_by_a_dahir_keeps_the_dahirs_articles_apart_and_its_footnotes_become_witnesses(corpus):
    words = lexicon(corpus, words_of(PENAL))
    # A word in six the corpus has never printed: the layer is text all the same, under the share that sends a file
    # to its page images.
    for w in ('يسوغ', 'يعتذر', 'بجهله', 'مؤاخذة', 'جريمة', 'يصادق', 'بظهيرنا', 'ينشر', 'ظهيرنا', 'أفعال'):
        del words[w]
    (corpus / 'derived' / 'lexicon.json').write_text(json.dumps(words, ensure_ascii=False))
    path = register(corpus, 'adala_89.pdf', PENAL)
    said = load(path)
    text = Text.objects.get(akn_uri='/akn/ma/act/dahir/1-59-413')
    assert (text.type, text.number, text.number_as_printed, text.status) == ('dahir', '1-59-413', '1.59.413', 'in_force')
    # The title's second line, opening with its date, is the title's; its mark is the BO footnote's.
    assert text.title_ar == ('ظهير شريف رقم 1.59.413 صادر في 28 جمادى الثانية 1382 (26 نونبر 1962) بالمصادقة على '
                             'مجموعة القانون الجنائي')
    version = Version.objects.get(text=text)
    doc = Document.objects.get(path=path)
    assert (version.language, version.consolidation, version.valid_from, version.source_document, version.source_pages) == (
        'ar', Consolidation.ADALA, datetime.date(2019, 2, 21), doc, '1-3')
    # The dahir's own two articles are the preamble; the code's articles keep their numbers from 1.
    assert version.preamble == ('الفصل الأول\nيصادق على مجموعة القانون الجنائي الملحقة بظهيرنا هذا.\n\n'
                                'الفصل الثاني\nينشر ظهيرنا هذا بالجريدة الرسمية.')
    assert list(Article.objects.filter(version=version).order_by('order').values_list(
        'order', 'label', 'number', 'eid', 'heading_path', 'body', 'printed_page')) == [
        (1, 'الفصل 1', '1', 'art_1', [], 'يحدد التشريع الجنائي أفعال الإنسان التي يعدها جرائم.', 2),
        (2, 'الفصل 2', '2', 'art_2', ['الجزء الأول: في الجريمة'], 'لا يسوغ لأحد أن يعتذر بجهله التشريع الجنائي.', 3),
        (3, 'الفصل 3', '3', 'art_3', ['الجزء الأول: في الجريمة'], 'لا يسوغ مؤاخذة أحد على فعل لا يعد جريمة.', 3)]
    assert (doc.meta['as_of'], doc.meta['first_issue'], doc.meta['first_page']) == ('2019-02-21', 2640, 1253)
    assert doc.meta['layer'] == {'words': 71, 'turned': 0, 'unknown': 11}
    assert [(f['number'], f['page'], f['article'], f['text'][:24]) for f in doc.meta['footnotes']] == [
        (1, 1, '', 'الجريدة الرسمية عدد 2640'), (2, 1, 'الفصل 1', 'انظر القرار رقم .269.04'),
        (3, 2, 'الفصل 2', 'عوضت أحكام الفصل 2 أعلاه'), (4, 2, 'الفصل 3', 'نسخت الفقرة الثانية بمقت')]
    # Only the footnote that names the law that changed art. 2 is a witness: art. 1's says nothing changed, art. 3's
    # names only the dahir that promulgated the changing law, and the title's is no article's.
    assert list(Change.objects.values_list('text_uri', 'number', 'verb', 'source', 'by_kind', 'by_number', 'by_uri',
                                           'issue', 'issue_bis', 'page')) == [
        (text.akn_uri, '2', 'replaced', 'adala', 'law', '65-21', '/akn/ma/act/loi/65-21', 7006, True, 5650)]
    assert said == (f'{path}: 3 articles, 4 footnotes (1 changes), as of 2019-02-21, 11/71 words unknown  '
                    f'{text.akn_uri}  (new text)\n')
    # Run again, the file replaces its own version and its own witnesses.
    assert not load(path).rstrip().endswith('(new text)')
    assert Version.objects.filter(text=text).count() == 1 and Change.objects.count() == 1


# A law headed by the dahir that promulgates it (the housing lease law 67.12): its title runs on to a third line whose
# footnote mark the layer gave in the text's own size; the file's cover gives no date.
LEASE = [
    [[('وزارة العدل', B)]],
    [[('ظهير شريف رقم 1.13.111 صادر في 15 من محرم 1435', B)],
     [('(19 نوفمبر 2013) بتنفيذ القانون رقم 67.12 المتعلق بتنظيم العلاقات', B)],
     [('التعاقدية بين المكري والمكتري 1', B)],
     [('الحمد لله وحده، الطابع الشريف - بداخله: محمد بن الحسن بن محمد بن يوسف الله وليه', B)],
     [('المادة الأولى', B)],
     [('تطبق مقتضيات هذا القانون على أكرية المحلات المعدة للسكنى.', B)],
     [('المادة 2', B)],
     [('يبرم عقد الكراء بمحرر كتابي ثابت التاريخ.', B)],
     [('1 - الجريدة الرسمية عدد 6208 بتاريخ 28 نوفمبر 2013، ص .7328', FOOT)]],
]


def test_a_law_headed_by_its_dahir_is_filed_as_the_law_dated_as_told_and_keeps_the_title_the_bo_gave_it(corpus):
    lexicon(corpus, words_of(LEASE))
    path = register(corpus, 'adala_67_12.pdf', LEASE)
    with pytest.raises(CommandError, match=r'not read whole \(articles 2, title «القانون رقم 67\.12 المتعلق بتنظيم '
                                           r'العلاقات التعاقدية بين المكري والمكتري», date None\)$'):
        load(path)
    printed = 'قانون رقم 67.12 يتعلق بتنظيم العلاقات التعاقدية بين المكري والمكتري للمحلات المعدة للسكنى أو للاستعمال المهني'
    held = Text.objects.create(akn_uri='/akn/ma/act/loi/67-12', type='law', number='67-12', title_ar=printed)
    Version.objects.create(text=held, language='ar', valid_from=datetime.date(2013, 11, 28),
                           consolidation=Consolidation.AS_PUBLISHED)
    said = load(path, '--as-of', '2026-07-16')
    held.refresh_from_db()
    # The title the BO printed stands: the text was read from the BO itself.
    assert held.title_ar == printed
    adala_version = held.versions.get(consolidation=Consolidation.ADALA)
    assert adala_version.valid_from == datetime.date(2026, 7, 16)
    assert list(adala_version.articles.values_list('number', flat=True)) == ['1', '2']
    doc = Document.objects.get(path=path)
    # The number the layer set after the title is its footnote's mark: the BO issue that first printed the law.
    assert (doc.meta['first_issue'], doc.meta['first_page']) == (6208, 7328)
    assert said.startswith(f'{path}: 2 articles, 1 footnotes (0 changes), as of 2026-07-16, ') and \
        said.rstrip().endswith('/akn/ma/act/loi/67-12')


def test_a_document_not_registered_from_adala_is_refused(corpus):
    with pytest.raises(CommandError, match=r'^sources/adala/none\.pdf: no Adala document at this path$'):
        load('sources/adala/none.pdf')


# A file whose text layer is no text (decree 2.10.311's «يج إيداع الطل»): its pages are read from their images.
# Tesseract gives each line's words in reading order, its brackets the right way round, the cover's date set small as a
# footnote's line, a heading's footnote mark after its number, a number it could not read, and a letter's dots misread.
SCANNED = [
    tsv([(100, 60, 'وزارة العدل'), (200, 40, 'صيغة محينة بتاريخ 12 مارس 2018')]),
    tsv([(100, 40, 'ظهير شريف صادر في 9 رمضان 1331 (12 أغسطس 1913) بمثابة قانون الالتزامات والعقود'),
         (150, 40, 'الفصل 1'), (200, 40, 'رفم الحساب يحدده المكري.'),
         (250, 40, 'الفصل 2 3'), (300, 40, 'يعتبر نفل الملك بيعا.'),
         (350, 40, 'الفصل ©'), (400, 40, 'لا يلزم أحد بما لم يلتزم به.'),
         (450, 40, 'الفصل 4'), (500, 40, 'تسري هذه الأحكام على الكافة.'),
         (650, 30, '1 - الجريدة الرسمية عدد 46 بتاريخ 12 شتنبر 1913، ص 78'), (680, 30, '2 - يراجع القرار رقم 2711.10.'),
         (700, 30, '- 2 -'), (720, 30, '7')]),
    tsv([]),
]


def test_a_layer_that_is_no_text_is_read_from_the_page_images_and_a_text_with_no_number_needs_its_address(corpus,
                                                                                                           monkeypatch):
    words = lexicon(corpus, [line for reading in SCANNED for line in reading.split('\t')] + ['رقم'])
    del words['رفم'], words['نفل']        # the misread words are none the corpus prints
    words['نقل'] = 5                        # printed too rarely to put a misread dot right
    (corpus / 'derived' / 'lexicon.json').write_text(json.dumps(words, ensure_ascii=False))
    # Three words in seven unknown: the layer is no text.
    path = register(corpus, 'adala_doc.pdf', [[[('وزارة العد', B)]], [[('ظهير شريف صادر بمثاب قانو', B)]], []],
                    size=(200, 150))
    tesseract = Tesseract(SCANNED * 3)
    monkeypatch.setattr('subprocess.run', tesseract)
    with pytest.raises(CommandError, match=r'not read whole \(articles 4, title «ظهير شريف صادر في 9 رمضان 1331 \(12 '
                                           r'أغسطس 1913\) بمثابة قانون الالتزامات والعقود», date 2018-03-12\)$'):
        load(path)
    said = load(path, '--uri', '/akn/ma/act/code/doc')
    # Each page rendered at 288 dpi and read as one block of Arabic lines, in TSV.
    assert tesseract.calls[0]['args'] == ['tesseract', '-', '-l', 'ara', '--psm', '6', 'tsv']
    assert tesseract.sizes[:3] == [(800, 600)] * 3
    text = Text.objects.get(akn_uri='/akn/ma/act/code/doc')
    assert (text.type, text.number, text.status, text.title_ar) == (
        'dahir', '', 'in_force', 'ظهير شريف صادر في 9 رمضان 1331 (12 أغسطس 1913) بمثابة قانون الالتزامات والعقود')
    version = text.versions.get()
    assert list(version.articles.values_list('number', 'body')) == [
        ('1', 'رقم الحساب يحدده المكري.'), ('2', 'يعتبر نفل الملك بيعا.'), ('3', 'لا يلزم أحد بما لم يلتزم به.'),
        ('4', 'تسري هذه الأحكام على الكافة.')]
    doc = Document.objects.get(path=path)
    # The marks are lost on an image: the first footnote (not the last), the BO's, gives where the text was first printed.
    assert (doc.meta['as_of'], doc.meta['first_issue'], doc.meta['first_page']) == ('2018-03-12', 46, 78)
    assert doc.meta['layer']['read_by'] == 'tesseract'
    # The page's number, printed either way, is no footnote's words.
    assert [(f['number'], f['page'], f['article'], f['text']) for f in doc.meta['footnotes']] == [
        (1, 1, '', 'الجريدة الرسمية عدد 46 بتاريخ 12 شتنبر 1913، ص 78'), (2, 1, '', 'يراجع القرار رقم 2711.10.')]
    assert said.rstrip().endswith('/akn/ma/act/code/doc  (new text)')
    # Run again at the same address, the text there is the one the file is loaded into.
    assert load(path, '--uri', '/akn/ma/act/code/doc').rstrip().endswith('/akn/ma/act/code/doc')
    assert Text.objects.filter(akn_uri='/akn/ma/act/code/doc').count() == 1 and text.versions.count() == 1


@pytest.mark.parametrize('head, kind', [
    # A head that names no kind of text (the land-registration dahir's file opens on its subject): a dahir, as the old
    # texts known by their address alone are.
    ('التحفيظ العقاري', 'dahir'),
    ('مرسوم رقم 2.10.311 بتطبيق أحكام القانون رقم 52.05 المتعلق بمدونة السير على الطرق', 'decree'),
    ('القرار المشترك لوزير التجهيز والنقل رقم 2711.10 بتحديد شكل رخصة السياقة', 'order'),
])
def test_a_text_loaded_at_its_address_takes_the_kind_its_title_names(corpus, head, kind):
    pages = [[[('صيغة محينة بتاريخ 16 يوليو 2026', B)]],
             [[(head, B)], [('المادة 1', B)], [('تطبق هذه الأحكام على جميع العقارات.', B)],
              [('المادة 2', B)], [('ينشر هذا النص بالجريدة الرسمية.', B)]]]
    lexicon(corpus, words_of(pages))
    path = register(corpus, 'adala_at.pdf', pages)
    load(path, '--uri', '/akn/ma/act/code/land-registration')
    text = Text.objects.get(akn_uri='/akn/ma/act/code/land-registration')
    assert (text.type, text.number, text.status) == (kind, '', 'in_force')
    assert list(text.versions.get().articles.values_list('number', flat=True)) == ['1', '2']
