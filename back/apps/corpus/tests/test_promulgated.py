"""Which dahir promulgates a law, from the Bulletin's own sentence (apps/corpus/services/promulgated.py)."""
from collections import Counter

import pytest
from django.core.management import call_command

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.services import promulgated

FAMILY = 'طبقا لأحكام القانون رقم 70.03 بمثابة مدونة الأسرة الصادر بتنفيذه الظهير الشريف رقم 1.04.22 بتاريخ 12 من ذي الحجة 1424'


def test_the_sentence_names_the_law_and_its_dahir():
    votes = promulgated.read([FAMILY, 'القانون رقم 65-99 المتعلق بمدونة الشغل الصادر بتنفيذه الظهير الشريف رقم 1-03-194', None, ''])
    assert votes == {'70-03': Counter({'1.04.22': 1}), '65-99': Counter({'1.03.194': 1})}
    # The dahir belongs to the law named last before it, never to one across another number or a sentence's end.
    amended = 'القانون رقم 17.95 كما تم تغييره بالقانون رقم 20.05 الصادر بتنفيذه الظهير الشريف رقم 1.08.18'
    assert dict(promulgated.read([amended])) == {'20-05': Counter({'1.08.18': 1})}
    assert promulgated.read(['القانون رقم 70.03. وقد صدر بتنفيذه الظهير الشريف رقم 1.04.22']) == {}


def test_a_law_gets_its_dahir_only_when_the_sentences_are_many_and_agree():
    assert promulgated.settled('70-03', Counter({'1.04.22': 6})) == '1.04.22'
    assert promulgated.settled('70-03', Counter({'1.04.22': 3})) is None                    # too few
    assert promulgated.settled('70-03', Counter({'1.04.22': 6, '1.04.23': 2})) is None      # they disagree
    assert promulgated.settled('70-03', Counter({'1.93.22': 6})) is None                    # a 1993 dahir for a 2003 bill
    assert promulgated.settled('7-81', Counter({'1.81.254': 9})) == '1.81.254'
    assert promulgated.settled('70-03', None) is None
    assert promulgated.same('1.07.02', '1.7.2') and not promulgated.same('1.07.02', '1.07.202')
    assert promulgated.key('07-03') == promulgated.key('7.03') == '7-03'


@pytest.mark.django_db
def test_the_command_fills_only_a_law_held_without_its_dahir():
    family = Text.objects.create(akn_uri='/akn/ma/act/loi/70-03', type='law', number='70-03', title_ar='القانون رقم 70.03 بمثابة مدونة الأسرة')
    labour = Text.objects.create(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99', title_ar='القانون رقم 65.99', promulgating_dahir='1.03.194')
    other = Text.objects.create(akn_uri='/akn/ma/act/loi/31-08', type='law', number='31-08', title_ar='قانون رقم 31.08')
    v = Version.objects.create(text=other, language='ar', valid_from='2011-04-07', consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.bulk_create([Article(version=v, order=i, label=f'المادة {i}', number=str(i), eid=f'art_{i}', body=body) for i, body in enumerate(
        [FAMILY] * 5 + ['القانون رقم 65.99 المتعلق بمدونة الشغل الصادر بتنفيذه الظهير الشريف رقم 1.99.999'] * 5, start=1)])
    call_command('name_dahirs')
    family.refresh_from_db()
    assert family.promulgating_dahir == ''                                                   # a dry run writes nothing
    call_command('name_dahirs', '--write')
    family.refresh_from_db()
    labour.refresh_from_db()
    other.refresh_from_db()
    assert family.promulgating_dahir == '1.04.22'
    assert labour.promulgating_dahir == '1.03.194' and other.promulgating_dahir == ''        # what is kept is never changed
