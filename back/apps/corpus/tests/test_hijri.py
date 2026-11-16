"""The Hijri calendar as the Bulletin's own double dates give it (W4 of the library-search review)."""
from datetime import date

from apps.corpus.services import hijri


def test_a_hijri_date_is_read_in_the_spellings_the_bulletin_uses():
    assert hijri.parse('ظهير 9 رمضان 1331')[:3] == (9, 9, 1331)
    assert hijri.parse('14 من رجب 1424')[:3] == (14, 7, 1424)
    assert hijri.parse('فاتح محرم 1405')[:3] == (1, 1, 1405)
    assert hijri.parse('ثالث وعشري قعدة عام 1340') is None            # a day in words is not read: no guess
    assert hijri.parse('18 جمادى الاولى 1448')[:3] == (18, 5, 1448)
    assert hijri.parse('3 جمادى الأولى 1378')[:3] == (3, 5, 1378)
    assert hijri.parse('25 ذي الحجة 1345')[:3] == (25, 12, 1345)
    assert hijri.parse('2 أكتوبر 1984') is None


def test_the_months_the_bulletin_fixes_give_its_own_days():
    # The DOC's day, the associations dahir's, the road-accident compensation dahir's: as their texts print them.
    assert hijri.to_gregorian(9, 9, 1331) == (date(1913, 8, 12), True)
    assert hijri.to_gregorian(3, 5, 1378) == (date(1958, 11, 15), True)
    assert hijri.to_gregorian(6, 1, 1405) == (date(1984, 10, 2), True)
    assert hijri.from_gregorian(date(1984, 10, 2)) == (6, 1, 1405)
    assert hijri.said(6, 1, 1405) == '6 محرم 1405'


def test_a_month_no_date_fixes_is_counted_from_the_nearest_and_said_so():
    day, sure = hijri.to_gregorian(1, 1, 1500)
    assert sure is False and 2076 <= day.year <= 2077
    assert hijri.from_gregorian(date(1800, 1, 1)) is None


def test_the_table_takes_the_day_most_pairs_give():
    pairs = [(date(1913, 8, 12), '9 رمضان 1331'), (date(1913, 8, 30), '27 رمضان 1331'), (date(1913, 8, 31), '29 رمضان 1331'),
             (date(1958, 11, 15), '3 جمادى الاولى 1378'),                       # one pair alone settles nothing
             (None, '1 محرم 1400'), (date(1980, 1, 1), 'بلا تاريخ')]
    table, counted = hijri.tabulate(pairs)
    assert table == {'1331-9': '1913-08-04'}
    assert counted == {'pairs': 4, 'months': 1, 'unsettled': 1, 'set_aside': 0}


def test_a_pair_far_from_the_arithmetic_calendar_does_not_vote():
    """«محرم 1331» printed where 1332 was meant put Muharram 1331 in November 1913, and Ramadan 1337 stood three weeks
    late: a misprint's pair, a year or weeks away, is set aside, and the month's own pairs settle it."""
    assert hijri.tabular(1331, 9) == date(1913, 8, 4) and hijri.tabular(1446, 1) == date(2024, 7, 8)
    wrong_year = [(date(1913, 12, 4), '5 محرم 1331'), (date(1913, 12, 9), '10 محرم 1331'), (date(1913, 12, 2), '3 محرم 1331')]
    table, counted = hijri.tabulate(wrong_year)
    assert table == {} and counted['set_aside'] == 3 and counted['unsettled'] == 1
    table, counted = hijri.tabulate(wrong_year + [(date(1912, 12, 15), '5 محرم 1331'), (date(1912, 12, 20), '10 محرم 1331')])
    assert table == {'1331-1': '1912-12-11'} and counted['set_aside'] == 3
    # The kept file holds no month further than the fence from the arithmetic calendar.
    import json
    kept = json.loads(hijri.FILE.read_text())
    assert len(kept) > 1300
    assert all(abs((date.fromisoformat(v) - hijri.tabular(*map(int, k.split('-')))).days) <= hijri.FAR for k, v in kept.items())
