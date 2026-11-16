"""`load_bill`: a finance bill's two born-digital files (the Ministry's Arabic and French) become a text of its own,
`/akn/ma/act/projet-loi/<n>`, a version per stage with its French beside it, and what its articles would change in the
tax code is kept as proposals dated by the bill's «Dates d'effet», never applied (P1, P2, P17)."""
import io
from datetime import date

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.consolidation.models import Change
from apps.corpus.models import Consolidation, Status, Text, Version
from apps.parliament.tests.pdfs import HEAD_AR, HEAD_FR, plain_ar, plain_fr, write_pdf
from apps.sources.models import Document
from apps.translations.models import FrenchArticle, FrenchText

pytestmark = pytest.mark.django_db

BILL = '/akn/ma/act/projet-loi/60-26'
CGI = '/akn/ma/act/code/cgi'


# The Arabic as the layer gives it: the lam-alif of the first heading turned, an amount's groups in visual order, a
# negative amount's sign last, a quoted passage closed by a turned guillemet.
ARABIC = [
    HEAD_AR + ['المملكة المغربية', 'الجزء الأول', 'املادة األولى',
               'تستمر الجهات المختصة في القيام خلال السنة المالية 2027 بما يلي :',
               'المادة 2', 'تحدث مناصب مالية.',
               'المادة 3', 'رصيد الميزانية العامة 000 000 000 60', 'رصيد الحسابات الخصوصية 690 921 000 88-'],
    HEAD_AR + ['- 2 -'] + plain_ar(4, 6) + [
        'المادة 7',
        'I.- تغير وتتمم على النحو التالي أحكام المواد 59 و73 و247 و252 من المدونة العامة للضرائب :',
        '«المادة 59.- الخصوم المطبقة على الأجور',
        '«يخصم من مبلغ الأجر الإجمالي 35% برسم المصاريف المهنية.',
        '«المادة 73.- سعر الضريبة',
        '«- شريحة الدخل إلى غاية 60 000 درهم معفاة من الضريبة.',
        '«المادة 247.- التدابير الانتقالية',
        '«تطبق التدابير الانتقالية الآتية.',
        '«المادة 252.- تحديد الحصة',
        '«تحدد الحصة بنسبة 30% من المبلغ.',
        'II.- تغير على النحو التالي أحكام المادة 73 من المدونة العامة للضرائب :',
        '«المادة 73.- سعر الضريبة الجديد',
        '«تطبق الأسعار الجديدة.«',                          # its closing guillemet turned, as the layer gives it
        'المادة 8',
        'تغير على النحو التالي أحكام المادة 5 من القانون رقم 47.06 المتعلق بجبايات الجماعات المحلية :',
        '«المادة 5.- الرسم المهني',
        '«يفرض الرسم على كل نشاط.'],
    HEAD_AR + ['- 3 -'] + plain_ar(9, 20),
]

FRENCH = [
    HEAD_FR + ['PREMIERE PARTIE', 'Article premier', 'Les administrations continuent leurs opérations en 2027.']
    + plain_fr(2, 6),
    HEAD_FR + [
        'Article 7',
        'I.- Les dispositions des articles 59, 73 et 247 du code général des impôts sont modifiées et complétées comme suit :',
        '« Article 73.- Taux de l’impôt',
        'IV.- Dates d’effet',
        '1 – Les dispositions de l’article 73 du code général des impôts sont applicables aux revenus acquis à compter '
        'du 1er janvier 2031.',
        '2 – Les dispositions de l’article 59 du code général des impôts relatives à l’abattement sont applicables '
        'aux revenus acquis à compter du 1er janvier 2028.',
        '3 – Les dispositions de l’article 247 quater du code général des impôts sont applicables à compter du 1er '
        'juillet 2027.',
    ] + plain_fr(8, 20),
]


@pytest.fixture
def files(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path

    def write(arabic=ARABIC, french=FRENCH, name='plf2027'):
        write_pdf(tmp_path / 'sources' / 'mef' / f'{name}_Ar.pdf', arabic, rtl=True)
        write_pdf(tmp_path / 'sources' / 'mef' / f'{name}_Fr.pdf', french)
        return f'sources/mef/{name}_Ar.pdf', f'sources/mef/{name}_Fr.pdf'
    return write


def load(arabic, french, *, on='2026-10-20', stage='filed'):
    out = io.StringIO()
    call_command('load_bill', arabic, french, '--number', '60.26', '--year', '2027', '--on', on, '--stage', stage,
                 '--url', 'https://www.finances.gov.ma/plf2027_Ar.pdf', stdout=out)
    return out.getvalue()


def test_a_bill_becomes_a_text_of_its_own_with_its_french_and_stands_nowhere(files):
    said = load(*files())
    bill = Text.objects.get(akn_uri=BILL)
    assert (bill.type, bill.number, bill.status) == ('bill', '60-26', Status.UNKNOWN)
    assert bill.title_ar == 'مشروع قانون المالية رقم 60.26 للسنة المالية 2027'
    assert bill.title_fr == 'Projet de loi de finances n° 60-26 pour l’année budgétaire 2027'
    ar, fr = Document.objects.get(language='ar'), Document.objects.get(language='fr')
    assert (ar.source, ar.kind, ar.url) == ('mef', 'parliament', 'https://www.finances.gov.ma/plf2027_Ar.pdf')
    assert fr.url == 'https://www.finances.gov.ma/plf2027_Fr.pdf'
    assert ar.meta == {'stage': 'filed', 'bill': '60.26', 'year': 2027}
    version = bill.versions.get()
    assert (version.consolidation, version.valid_from, version.source_document, version.source_pages) == (
        Consolidation.BILL, date(2026, 10, 20), ar, '1-3')
    articles = list(version.articles.order_by('order'))
    assert [a.number for a in articles] == [str(n) for n in range(1, 21)]
    assert [a.eid for a in articles[:2]] == ['art_1', 'art_2']
    # The turned heading read as the first article, under its division; the title above it is no article's.
    assert (articles[0].label, articles[0].heading_path, articles[0].printed_page) == (
        'المادة الأولى', ['الجزء الأول'], 1)
    assert articles[0].body == 'تستمر الجهات المختصة في القيام خلال السنة المالية 2027 بما يلي :'
    # Amounts back in reading order, a negative one with its sign first.
    assert articles[2].body == 'رصيد الميزانية العامة 60 000 000 000\nرصيد الحسابات الخصوصية -88 690 921 000'
    assert '«المادة 73.- سعر الضريبة' in articles[6].body.splitlines()
    assert articles[6].body.splitlines()[-1] == '«المادة 73.- سعر الضريبة الجديد تطبق الأسعار الجديدة.»'
    assert (articles[6].printed_page, articles[19].printed_page) == (2, 3)
    french = FrenchText.objects.get(text_uri=BILL)
    assert (french.type, french.number, french.issue_number, french.issue_date, french.document_sha, french.pages) == (
        'bill', '60-26', 0, date(2026, 10, 20), fr.sha256, '1-2')
    assert french.title == bill.title_fr
    french_articles = list(FrenchArticle.objects.filter(text_uri=BILL))
    assert [(a.number, a.label) for a in french_articles[:2]] == [('1', 'Article premier'), ('2', 'Article 2')]
    assert french_articles[0].body == 'Les administrations continuent leurs opérations en 2027.'
    assert said.startswith(f'{BILL}: 20 articles (Arabic), 20 French, stage filed on 2026-10-20; ')
    assert "'turned': 2" in said and said.endswith('4 proposed changes  (new text)\n')


def test_what_the_bill_would_change_is_kept_as_proposals_dated_by_its_dates_of_effect(files):
    load(*files())
    proposals = {(c.text_uri, c.number): c for c in Change.objects.all()}
    # 252 is quoted in the Arabic but not named by the French lead; 73's second passage is the same change again.
    assert set(proposals) == {(CGI, '59'), (CGI, '73'), (CGI, '247'), ('/akn/ma/act/loi/47-06', '5')}
    assert {(c.source, c.state, c.by_uri) for c in proposals.values()} == {('bill', 'proposed', BILL)}
    rate = proposals[CGI, '73']
    assert (rate.effective_on, rate.effective_rule) == (date(2031, 1, 1), 'stated')
    assert rate.effective_words.startswith('1 – Les dispositions de l’article 73')
    assert rate.wording[0] == 'سعر الضريبة' and 'partial' not in rate.detail
    # A paragraph that dates only the provisions «relatives à» one thing dates part of the change.
    wages = proposals[CGI, '59']
    assert wages.effective_on == date(2028, 1, 1) and wages.detail['partial'] is True
    # A paragraph that dates 247 quater says nothing of 247; nor do the code's paragraphs of another law's change.
    for undated in (proposals[CGI, '247'], proposals['/akn/ma/act/loi/47-06', '5']):
        assert undated.effective_on is None and undated.effective_rule != 'stated'


def test_a_later_stage_is_a_version_more_and_the_same_stage_again_replaces_its_own(files):
    arabic, french = files()
    other = Change.objects.create(text_uri=CGI, number='6', verb='modified', source=Change.Source.BILL, by_kind='bill',
                                  by_number='50-25', by_uri='/akn/ma/act/projet-loi/50-25', state=Change.State.PROPOSED)
    load(arabic, french)
    said = load(arabic, french, on='2026-11-15', stage='representatives')
    bill = Text.objects.get(akn_uri=BILL)
    assert sorted(bill.versions.values_list('valid_from', flat=True)) == [date(2026, 10, 20), date(2026, 11, 15)]
    assert '(new text)' not in said and 'stage representatives on 2026-11-15' in said
    load(arabic, french, on='2026-11-15', stage='representatives')
    assert Version.objects.filter(text=bill).count() == 2
    assert bill.versions.get(valid_from=date(2026, 11, 15)).articles.count() == 20
    # The proposals are the bill's latest reading, never added to the ones before; another bill's stay.
    assert Change.objects.filter(by_uri=BILL).count() == 4 and Change.objects.filter(pk=other.pk).exists()
    assert FrenchArticle.objects.filter(text_uri=BILL).count() == 20 and FrenchText.objects.count() == 1


def test_a_file_that_is_not_there_is_refused(files):
    arabic, _ = files()
    with pytest.raises(CommandError, match=r'^sources/mef/missing_Fr\.pdf: not found$'):
        load(arabic, 'sources/mef/missing_Fr.pdf')
    assert not Text.objects.exists()


@pytest.mark.parametrize('arabic, french, said', [
    ([HEAD_AR + plain_ar(1, 3)], [HEAD_FR + plain_fr(1, 3)], 'articles: 3 Arabic, 3 French'),
    ([HEAD_AR + plain_ar(1, 21)], [HEAD_FR + plain_fr(1, 20)], 'articles: 21 Arabic, 20 French'),
])
def test_a_file_cut_into_too_few_articles_or_not_as_many_as_its_french_is_refused(files, arabic, french, said):
    with pytest.raises(CommandError, match=f'^{said}$'):
        load(*files(arabic, french))
    assert not Text.objects.exists() and not Change.objects.exists()

