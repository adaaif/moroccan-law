"""1. read: what a text says of others without changing them (row L4 of the links review) — references redirected to it,
implementing texts it keeps in force, a correction, a Constitutional Court ruling — and an instruction whose text is not
named plainly, each kept for a person rather than guessed."""
import datetime

import pytest

from apps.consolidation.models import Change, Doubt
from apps.consolidation.services import engine
from apps.consolidation.tests.test_links import text
from apps.corpus.models import Mention

pytestmark = pytest.mark.django_db
DAY = datetime.date(2026, 8, 10)


def said(t):
    return set(Mention.objects.filter(from_uri=t.akn_uri).exclude(kind='cites').values_list('from_eid', 'kind', 'to_uri'))


def test_redirected_references_and_kept_implementing_texts_are_mentions_never_changes():
    law = text('/akn/ma/act/loi/64-23', 'law', '64-23', 'قانون رقم 64.23 يتعلق بالوكالات الجهوية للتعمير والإسكان', DAY, [
        ('المادة 23', 'تعتبر الإحالات إلى القانون رقم 19.88 في النصوص التشريعية والتنظيمية الجاري بها العمل إحالات إلى '
                      'هذا القانون.'),
        ('المادة 24', 'تظل سارية المفعول النصوص المتخذة لتطبيق القانون رقم 19.88 إلى حين تعويضها.'),
        # A reference that stays a reference, and a law's own words kept for a while, are neither.
        ('المادة 25', 'تبقى الإحالات إلى القانون رقم 19.88 الواردة في العقود صحيحة.\n'
                      'تظل سارية المفعول مقتضيات القانون رقم 19.88 المتعلقة بالمستخدمين إلى غاية 2027.')])
    engine.run([law], log=lambda *_: None)
    assert said(law) == {('art_1', 'redirects', '/akn/ma/act/loi/19-88'), ('art_2', 'keeps', '/akn/ma/act/loi/19-88')}
    assert not Change.objects.exists()


def test_a_correction_and_a_courts_ruling_are_said_and_left_to_a_person():
    correction = text('/akn/ma/act/decret/2-26-10', 'decree', '2-26-10', 'استدراك خطأ وقع في القانون رقم 2.00 المتعلق بحقوق المؤلف',
                      DAY, [('فصل فريد', 'في الصفحة 1112، بدلا من «المصنف»، يقرأ «المصنفات».')])
    ruling = text('/akn/ma/act/decision/250-26', 'decision', '250-26',
                  'قرار المحكمة الدستورية رقم 250/26 بشأن القانون التنظيمي رقم 130.13 لقانون المالية', DAY,
                  [('المادة 1', 'تصرح بأن المادة 5 من القانون التنظيمي رقم 130.13 غير مطابقة للدستور.')], number_issue=7534)
    conform = text('/akn/ma/act/decision/251-26', 'decision', '251-26', 'قرار المحكمة الدستورية رقم 251/26 بشأن القانون رقم 15.02',
                   DAY, [('المادة 1', 'تصرح بأن القانون رقم 15.02 مطابق للدستور.')], number_issue=7534)
    engine.run([correction, ruling, conform], log=lambda *_: None)
    assert said(correction) == {('', 'corrects', '/akn/ma/act/loi/2-00')}
    assert said(ruling) == {('', 'rules_on', '/akn/ma/act/loi-organique/130-13')}
    assert said(conform) == {('', 'rules_on', '/akn/ma/act/loi/15-02')}           # found conforming: nothing to check
    assert set(Doubt.objects.values_list('text_uri', 'by_uri', 'reason')) == {
        ('/akn/ma/act/loi/2-00', correction.akn_uri, 'correction'),
        ('/akn/ma/act/loi-organique/130-13', ruling.akn_uri, 'court')}


def test_an_instruction_whose_text_is_not_named_plainly_is_a_doubt_not_a_guess():
    law = text('/akn/ma/act/loi/13-26', 'law', '13-26', 'قانون رقم 13.26', DAY, [
        ('المادة الأولى', 'تغير أحكام المادة 8 من القانون السالف الذكر كما يلي :\n«المادة 8. - نص جديد.»')])
    engine.run([law], log=lambda *_: None)
    assert not Change.objects.exists()
    assert list(Doubt.objects.values_list('by_uri', 'by_article', 'reason', 'text_uri')) == [
        (law.akn_uri, 'المادة الأولى', 'target_unknown', '')]
