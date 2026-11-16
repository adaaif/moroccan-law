import datetime

import pytest
from django.db import IntegrityError

from apps.corpus.models import Article, Consolidation, Text, TextType, Version
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db


def law_2_00():
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=4796, date=datetime.date(2000, 5, 18))
    return Text.objects.create(
        akn_uri='/akn/ma/act/loi/2-00', type=TextType.LAW, number='2-00', number_as_printed='2.00',
        title_ar='القانون رقم 2.00 المتعلق بحقوق المؤلف والحقوق المجاورة', signed_on=datetime.date(2000, 2, 15),
        signed_on_hijri='9 ذي القعدة 1420', first_published_in=issue, first_published_page=1112,
    )


def test_a_text_has_dated_versions_whose_articles_are_whole():
    text = law_2_00()
    original = Version.objects.create(text=text, language='ar', valid_from=datetime.date(2000, 5, 18),
                                      valid_to=datetime.date(2006, 2, 20), consolidation=Consolidation.AS_PUBLISHED)
    current = Version.objects.create(text=text, language='ar', valid_from=datetime.date(2026, 8, 10),
                                     consolidation=Consolidation.CHECKED)
    for version in (original, current):
        Article.objects.create(version=version, order=8, label='المادة 8', number='8', eid='art_8',
                               body='لا تشمل الحماية المنصوص عليها في هذا القانون ما يلي:')
    assert text.versions.get(valid_to__isnull=True) == current
    assert Article.objects.filter(version__text=text, number='8').count() == 2


def test_a_work_address_is_unique():
    law_2_00()
    with pytest.raises(IntegrityError):
        Text.objects.create(akn_uri='/akn/ma/act/loi/2-00', type=TextType.LAW)
