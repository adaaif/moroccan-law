"""An issue's Hijri date from its masthead (U13 of the Moroccan-design review)."""
from datetime import date

from apps.sources.services.hijri import read

MASTHEAD = 'السنة الرابعة عشرة بعد المائة - عدد 7465 مكرر 25 جمادى الآخرة 1447 (16 ديسمبر 2025)\nISSN 0851 - 1195'


def test_the_hijri_date_is_kept_as_printed_when_the_bracket_is_the_issues_own_date():
    assert read(MASTHEAD, date(2025, 12, 16)) == '25 جمادى الآخرة 1447'
    assert read(MASTHEAD, date(2025, 12, 17)) == ''          # a misread masthead never dates an issue
    assert read('عدد 7300 فاتح ذو القعدة 1445 (فاتح ماي 2024)', date(2024, 5, 1)) == 'فاتح ذو القعدة 1445'
    assert read('عدد 6838 17 ربيع الآخر 1441 (14 دجنبر 2019)', date(2019, 12, 14)) == '17 ربيع الآخر 1441'


def test_an_old_masthead_gives_the_hijri_day_before_its_gregorian_one():
    """The Bulletin-from-No.-1 review: before 1956 the masthead prints the Hijri day, then «الموافق» and the Gregorian, with no
    brackets, the months spelled the protectorate's way."""
    old = 'عدد 2000\nالرباط في 16 جمادى الاولى عام 1370\nالموافق 23 يبراير سنة 1951\nالقسم الرسمي'
    assert read(old, date(1951, 2, 23)) == '16 جمادى الاولى 1370'
    assert read(old, date(1951, 2, 24)) == ''
    assert read('الرباط في 14 رجب عام 1352 الموافق 3 نونبر سنة 1933', date(1933, 11, 3)) == '14 رجب 1352'
