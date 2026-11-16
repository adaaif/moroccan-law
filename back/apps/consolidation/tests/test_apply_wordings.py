"""`apply_wordings` (the health review, S3): a person's file gives a dotted amendment its whole wording and dates a
text whose entry into force hangs on a condition; the links then run for the text, and running the file again changes
nothing."""
import datetime
from io import StringIO

import pytest
from django.core.management import call_command

from apps.consolidation.models import Change, Doubt
from apps.consolidation.services import engine
from apps.consolidation.tests.test_links import text
from apps.corpus.models import Status

pytestmark = pytest.mark.django_db
WORDING = """\
# 27.22 rewrote 65.00 art. 1 with dots that stand on no anchor: the article whole, as it reads once changed.
text: /akn/ma/act/loi/65-00
by: /akn/ma/act/loi/27-22
by_article: المادة الأولى
checked: owner-provisional
articles:
  1:
    - 'تستفيد الفئات التالية :'
    - '- موظفو وأعوان الدولة ؛'
    - '- المستقلون.'
"""
IN_FORCE = """\
text: /akn/ma/act/loi/65-00
by: /akn/ma/act/loi/65-00
checked: owner-provisional
in_force:
  since: 2005-08-18
  because: 'المراسيم المتخذة لتطبيقه، الجريدة الرسمية عدد 5344'
"""


def test_a_persons_wording_and_day_of_force_are_kept_as_resolved_doubts_and_the_text_is_rebuilt(tmp_path):
    amo = text('/akn/ma/act/loi/65-00', 'law', '65-00', 'قانون رقم 65.00 بمثابة مدونة التغطية الصحية الأساسية',
               datetime.date(2002, 11, 21), [('المادة 1', 'يسري التأمين على :\n- موظفي وأعوان الدولة ؛\n- الأجراء.'),
                                             ('المادة 147', 'تدخل أحكام هذا القانون حيز التنفيذ، ابتداء من تاريخ النشر '
                                                            'بالجريدة الرسمية للنصوص التطبيقية اللازمة لتنصيب أجهزة الوكالة.')],
               number_issue=5058)
    law = text('/akn/ma/act/loi/27-22', 'law', '27-22', 'قانون رقم 27.22 بتغيير وتتميم القانون رقم 65.00',
               datetime.date(2022, 11, 30), [('المادة الأولى', 'تغير أحكام المادة 1 من القانون السالف الذكر رقم 65.00 :\n'
                                                               '«المادة 1. - تستفيد الفئات التالية :\n«- موظفو وأعوان............ ؛\n'
                                                               '«- المستقلون.»')], number_issue=7147)
    engine.run([law], log=lambda *_: None)
    assert not amo.versions.filter(consolidation='machine').exists()          # the dots stand on no anchor
    (tmp_path / 'wording.yaml').write_text(WORDING)
    (tmp_path / 'in_force.yaml').write_text(IN_FORCE)
    for _ in range(2):
        out = StringIO()
        call_command('apply_wordings', str(tmp_path / 'wording.yaml'), str(tmp_path / 'in_force.yaml'), stdout=out)
    said = out.getvalue().splitlines()
    assert said[:2] == [f'{tmp_path / "wording.yaml"}: 1 articles worded',
                        f'{tmp_path / "in_force.yaml"}: 0 articles worded, in force since 2005-08-18']
    resolved = Doubt.objects.filter(status='resolved')
    assert resolved.count() == 2 and not resolved.filter(resolved_at=None).exists()
    assert sorted(resolved.values_list('text_uri', 'number', 'by_uri', 'by_article', 'reason', 'note')) == [
        (amo.akn_uri, '', amo.akn_uri, '', 'when', 'in_force.yaml (owner-provisional)'),
        (amo.akn_uri, '1', law.akn_uri, 'المادة الأولى', 'unplaced', 'wording.yaml (owner-provisional)')]
    assert resolved.get(reason='unplaced').detail == {
        'wording': ['تستفيد الفئات التالية :', '- موظفو وأعوان الدولة ؛', '- المستقلون.'], 'checked': 'owner-provisional',
        'file': 'wording.yaml'}
    assert resolved.get(reason='when').detail == {'on': '2005-08-18', 'because': 'المراسيم المتخذة لتطبيقه، الجريدة الرسمية عدد 5344',
                                                   'checked': 'owner-provisional', 'file': 'in_force.yaml'}
    machine = amo.versions.get(consolidation='machine')
    assert machine.articles.get(number='1').body.splitlines() == ['تستفيد الفئات التالية :', '- موظفو وأعوان الدولة ؛',
                                                                  '- المستقلون.']
    assert Change.objects.get(text_uri=amo.akn_uri, source='reading').state == 'checked'
    stand = engine.standing(amo)
    assert stand['status'] == Status.IN_FORCE and stand['in_force_since'] == datetime.date(2005, 8, 18)
