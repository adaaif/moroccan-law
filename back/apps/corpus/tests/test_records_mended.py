"""FX7 of the mended-Bulletin review: dates and twins that cannot be right."""
from datetime import UTC, date, datetime

import pytest

from apps.corpus.models import Alias, Article, Consolidation, Text, Version
from apps.corpus.services import records
from apps.sources.models import Document, Issue

pytestmark = pytest.mark.django_db


def bo(number, day):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'h{number}', path=f'{number}.pdf',
                                  mime='application/pdf', bytes=1, language='ar', page_count=1,
                                  fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    return Issue.objects.create(edition='general_ar', number=number, date=day, document=doc, first_page_number=1)


def text(issue, k, title, bodies=(), signed=None, closing='', page=1, number=''):
    t = Text.objects.create(akn_uri=f'/akn/ma/act/arrete/{issue.date}/bo{issue.number}-{k}', type='order',
                            title_ar=title, first_published_in=issue, signed_on=signed, first_published_page=page,
                            number=number)
    v = Version.objects.create(text=t, language='ar', valid_from=issue.date, closing=closing,
                               consolidation=Consolidation.AS_PUBLISHED)
    for n, body in enumerate(bodies, 1):
        Article.objects.create(version=v, order=n, label=f'الفصل {n}', eid=f'art_{n}', body=body)
    return t


def test_a_day_after_the_issue_gives_way_to_the_day_the_closing_signs():
    issue = bo(1613, date(1943, 9, 24))
    t = text(issue, 1, 'ظهير شريف', ['يعمل به'], signed=date(1943, 11, 8),
             closing='وحرر بالرباط في 9 شعبان عام 1362 الموافق 11 غشت سنة 1943')
    fixed, left = records.dates(write=True)
    assert fixed == [(t.akn_uri, date(1943, 11, 8), date(1943, 8, 11))] and left == []
    assert Text.objects.get(pk=t.pk).signed_on == date(1943, 8, 11)


def test_a_text_cut_twice_folds_into_the_fuller_cut_but_two_appointments_stay_two():
    issue = bo(1120, date(1934, 4, 13))
    empty = text(issue, 1, 'ظهير شريف ينطبق بموجبه في الامور الجنائية ضابط فريد')
    full = text(issue, 4, 'ظهير شريف ينطبق بموجبه في الأمور الجنائية ضابط فريد', ['تطبق المسطرة الجنائية'] * 6)
    a = text(issue, 7, 'قرار وزيري في تعيين كاتب نساخ في وظيفه رسميا', ['يعين السيد محمد بن احمد كاتبا نساخا بالرباط'])
    b = text(issue, 8, 'قرار وزيري في تعيين كاتب نساخ في وظيفه رسميا', ['يعين السيد العربي الفاسي كاتبا نساخا بفاس'])
    assert records.twins(write=True) == [(empty.akn_uri, full.akn_uri)]
    assert Alias.objects.get(alias=empty.akn_uri).uri == full.akn_uri
    assert Text.objects.filter(pk__in=[a.pk, b.pk]).count() == 2


def test_on_a_cover_titles_alike_meet_on_any_page():
    cover = bo(610, date(1925, 1, 6))
    copy = bo(611, date(1925, 1, 6))
    Issue.objects.filter(pk=copy.pk).update(copy_of=cover)
    words = ['يحدث تغيير في تركيب جماعات فخذات قبيلة فرع الكارة على الوجه الآتي بيانه']
    a = text(cover, 1, 'في احداث تغيير في تركيب جماعات فخذات فبيئة فرع الكارة', words, page=5)
    b = text(cover, 4, 'قرار وزيري في احداث تغيير في تركيب جماعات فخذات قبيلة فرع الكارة', words * 2, page=1)
    assert records.twins(write=True) == [(a.akn_uri, b.akn_uri)]


def test_a_row_made_from_a_contents_line_folds_into_the_text_it_names():
    issue = bo(153, date(1916, 4, 3))
    listed = text(issue, 3, 'ظهير شريف بتخلي القائد المحجوب المهداوي عن اولاد زيان والمرايح', page=2)
    printed = text(issue, 9, 'ظهير شريف في تخلي القائد المحجوب المهداوي عن اولاد زيان والمرايح', ['يتخلى القائد'], page=7)
    assert records.twins(write=True) == [(listed.akn_uri, printed.akn_uri)]


def test_titles_that_name_two_texts_never_fold_without_words():
    same = lambda a, b: records.same_title(records._key(a), records._key(b))
    assert same('قرار وزيري في تعيين موثق اسرائلي بفاس', 'في تعيين موثق اسرائلي بفاس')
    assert same('ظهير شريف فى تعيين عضو بالمحكمة الدولية', 'ظهير شريف في تعيين عضو بالمحكمة الدولية')
    assert same('ظهير شريف بتخلي القائد عن اولاد زيان', 'ظهير شريف في تخلي القائد عن اولاد زيان')
    assert not same('قرار وزيري بتأسيس اللجنة بمدينة مكناس', 'قرار وزيري بتأسيس اللجنة بمدينة الرباط')
    assert not same('إعادة تنظيم جماعات الفخذات', 'إعادة تنظيم جماعات القبائل')
