"""RD4 of the readers review: a signing day that cannot be is put right from what the text prints."""
from datetime import date

import pytest

from apps.quality.management.commands.mend_dates import right_day


def test_a_century_read_wrong_takes_the_issues_year():
    assert right_day(date(2032, 1, 12), date(1932, 2, 26), 'ظهير شريف في الاذن بان يبيع') == date(1932, 1, 12)
    assert right_day(date(2935, 2, 11), date(1935, 3, 8), 'ظهير شريف في الاذن ببيع') == date(1935, 2, 11)
    # A text of December printed in January is of the year before.
    assert right_day(date(2045, 12, 20), date(1946, 1, 11), '') == date(1945, 12, 20)


def test_a_hijri_year_gives_way_to_the_titles_own_day():
    title = 'قرار لوزير الداخلية والاعلام رقم 1347.93 صادر في 15 من ذي الحجة 1413 (6 يونيو 1993) بتحديد'
    assert right_day(date(1413, 6, 6), date(1993, 7, 28), title) == date(1993, 6, 6)


def test_a_day_nothing_dates_is_left():
    assert right_day(date(1907, 1, 1), date(1939, 10, 20), 'قرار وزيري في التصريح بانه من المصلحة العمومية') is None
    assert right_day(date(2032, 1, 12), None, '') is None
    # 29 February in a year that has none is no day: the year before is tried, too far from the issue.
    assert right_day(date(2932, 2, 29), date(1933, 1, 10), '') is None


@pytest.mark.django_db
def test_the_command_lists_what_it_would_mend_and_writes_it_when_asked(capsys):
    from django.core.management import call_command

    from apps.corpus.models import Text
    from apps.sources.models import Issue

    def text(uri, signed, title='', issued=None, number=None):
        issue = Issue.objects.create(edition='general_ar', number=number, date=issued) if issued else None
        return Text.objects.create(akn_uri=uri, type='dahir', title_ar=title, signed_on=signed, first_published_in=issue)

    hijri = text('/akn/ma/act/arrete/1347-93', date(1413, 6, 6), issued=date(1993, 7, 28), number=4213,
                 title='قرار لوزير الداخلية رقم 1347.93 صادر في 15 من ذي الحجة 1413 (6 يونيو 1993) بتحديد')
    future = text('/akn/ma/act/dahir/1935-03-08/bo1171-2', date(2935, 2, 11), issued=date(1935, 3, 8), number=1171)
    alone = text('/akn/ma/act/dahir/x', date(1907, 1, 1))                   # no issue to date it by
    fine = text('/akn/ma/act/dahir/1-60-138', date(1960, 12, 7))
    call_command('mend_dates')
    assert capsys.readouterr().out.splitlines() == [
        '/akn/ma/act/arrete/1347-93: 1413-06-06 -> 1993-06-06 (printed 1993-07-28)',
        '/akn/ma/act/dahir/x: 1907-01-01 (printed None): nothing dates it, left',
        '/akn/ma/act/dahir/1935-03-08/bo1171-2: 2935-02-11 -> 1935-02-11 (printed 1935-03-08)',
        '2 days to put right (not written), 1 left']
    assert Text.objects.get(pk=future.pk).signed_on == date(2935, 2, 11)
    call_command('mend_dates', '--write')
    assert capsys.readouterr().out.splitlines()[-1] == '2 days put right, 1 left'
    assert {t.pk: t.signed_on for t in Text.objects.all()} == {
        hijri.pk: date(1993, 6, 6), future.pk: date(1935, 2, 11), alone.pk: date(1907, 1, 1), fine.pk: date(1960, 12, 7)}
