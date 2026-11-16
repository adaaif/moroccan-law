"""Morocco's time (config/settings/base.py): the zones' rules come from the pinned tzdata package, never from the
machine's own files, so every machine tells the same hour and a decree that moves the clock arrives with an update of
the packages."""
import importlib
import sys
import time
import zoneinfo
from datetime import UTC, date, datetime, timedelta

import pytest
from django.utils import timezone


def local(*moment):
    return timezone.localtime(datetime(*moment, tzinfo=UTC))


def test_the_zones_rules_are_read_from_the_pinned_package_alone():
    assert zoneinfo.TZPATH == ()
    assert zoneinfo.ZoneInfo('Africa/Casablanca').key == 'Africa/Casablanca'


def test_while_morocco_was_an_hour_ahead_half_past_midnight_was_the_next_day():
    assert local(2025, 10, 25, 23, 30).date() == date(2025, 10, 26)
    assert local(2026, 2, 25, 23, 30).date() == date(2026, 2, 25)                # Ramadan: on UTC
    assert local(2026, 9, 19, 23, 30).date() == date(2026, 9, 20)                # the last night an hour ahead


def test_since_20_september_2026_morocco_is_on_greenwichs_time_all_year():
    """Decree 2.26.530 (Bulletin 7521, p. 3768): back to the legal time on Sunday 20 September 2026 at two."""
    for moment in ((2026, 9, 20, 1, 30), (2026, 10, 25, 23, 30), (2027, 2, 20, 12, 0), (2027, 7, 1, 23, 30)):
        there = local(*moment)
        assert there.utcoffset() == timedelta(0) and there.date() == date(*moment[:3])


@pytest.mark.skipif(sys.platform != 'linux', reason='the C library is asked where the server runs: Linux')
def test_the_c_library_tells_the_same_hour_as_django():
    """`date.today()`, `datetime.now()` and the logs' hours ask the C library, not zoneinfo: it reads the same pinned
    files (TZDIR), so the two never differ by the hour a machine's own files are late."""
    for moment in ((2025, 10, 25, 23, 30), (2026, 2, 25, 23, 30), (2026, 10, 25, 23, 30), (2027, 7, 1, 23, 30)):
        stamp = datetime(*moment, tzinfo=UTC).timestamp()
        assert datetime.fromtimestamp(stamp) == local(*moment).replace(tzinfo=None)      # the naive local hour, as date.today() reads it
    assert time.localtime().tm_gmtoff == timezone.localtime().utcoffset().total_seconds()


@pytest.mark.skipif(sys.platform != 'linux', reason='the C library is asked where the server runs: Linux')
def test_reading_the_settings_again_leaves_the_c_librarys_clock_on_moroccos_time():
    """A test reloads the settings module (the letters' backend). The first way these settings told the C library its
    zone left the process on UTC after that, and whichever test read `date.today()` next in that worker was wrong."""
    import config.settings.base as base
    importlib.reload(base)
    an_hour_ahead = datetime(2025, 10, 25, 23, 30, tzinfo=UTC).timestamp()
    assert time.localtime(an_hour_ahead).tm_gmtoff == 3600
    assert time.localtime(datetime(2026, 10, 25, 23, 30, tzinfo=UTC).timestamp()).tm_gmtoff == 0
