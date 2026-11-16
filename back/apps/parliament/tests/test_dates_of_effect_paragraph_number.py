"""A «Dates d'effet» paragraph's own number is no code article. Bill 60.26's article 7-IV numbers its paragraphs 1 to
14, and its paragraph «11 –» dates articles 220, 225 and 225 bis: read as article 11, it dated the bill's proposed
change to the code's article 11 (named by the lead, dated by no paragraph) with words about the commissions' appeals."""
from datetime import date

import pytest
from django.core.management import call_command

from apps.consolidation.models import Change
from apps.parliament.services import finance_bill
from apps.parliament.tests.pdfs import write_pdf
from apps.parliament.tests.test_load_bill import HEAD_AR, HEAD_FR, plain_ar, plain_fr

BODY = ('IV.- Dates d’effet\n'
        '1 – Les dispositions de l’article 6-I du code général des impôts sont applicables à compter du 1er janvier 2027.\n'
        '11 – Les dispositions des articles 220-VI et 225-I du code général des impôts sont applicables aux recours '
        'introduits devant les commissions à compter du 1er juillet 2027.')


def test_a_paragraphs_own_number_dates_no_code_article():
    assert set(finance_bill.dates_of_effect(BODY)) == {'6', '220', '225'}


@pytest.mark.django_db
def test_a_code_article_no_paragraph_names_keeps_no_stated_date(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    arabic = [HEAD_AR + plain_ar(1, 6) + [
        'المادة 7', 'I.- تغير وتتمم على النحو التالي أحكام المادتين 6 و11 من المدونة العامة للضرائب :',
        '«المادة 6.- الإعفاءات', '«تعفى العمليات الآتية.', '«المادة 11.- التكاليف غير القابلة للخصم',
        '«لا تقبل في الخصم المبالغ الآتية.'] + plain_ar(8, 20)]
    french = [HEAD_FR + plain_fr(1, 6) + [
        'Article 7',
        'I.- Les dispositions des articles 6 et 11 du code général des impôts sont modifiées et complétées comme suit :',
        *BODY.split('\n')] + plain_fr(8, 20)]
    write_pdf(tmp_path / 'b_Ar.pdf', arabic, rtl=True)
    write_pdf(tmp_path / 'b_Fr.pdf', french)
    call_command('load_bill', 'b_Ar.pdf', 'b_Fr.pdf', '--number', '60.26', '--year', '2027', '--on', '2026-10-20',
                 stdout=None)
    dated = dict(Change.objects.values_list('number', 'effective_on'))
    assert dated == {'6': date(2027, 1, 1), '11': None}
