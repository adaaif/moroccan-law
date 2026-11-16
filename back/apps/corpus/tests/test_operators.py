"""The network operator of an address, for the day of reading's READING_OPERATOR_CEILING: read from DB-IP's ASN
database in GEOIP_DIR (apps/corpus/services/operators.py), which `fetch_geoip` fetches. The database here is a real one
in MaxMind's format, two operators split by the first bit of an IPv4 address, written by `database`."""
import gzip
import io
import urllib.error
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from rest_framework.test import APIClient

from apps.corpus.services import operators
from apps.corpus.tests.test_reading_budget import code  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db
U16, U32, U64 = 5, 6, 9          # MaxMind DB's type numbers for the unsigned integers
LOW, HIGH = 36925, 6713          # the operators of 0.0.0.0–127.255.255.255 and of 128.0.0.0–255.255.255.255


def _control(kind: int, size: int) -> bytes:
    low, extra = (size, b'') if size < 29 else (29, bytes([size - 29]))
    return (bytes([(kind << 5) | low]) if kind <= 7 else bytes([low, kind - 7])) + extra


def _encoded(value) -> bytes:
    if isinstance(value, tuple):                 # (type, number): an unsigned integer of that type
        kind, n = value
        size = (n.bit_length() + 7) // 8
        return _control(kind, size) + n.to_bytes(size, 'big')
    if isinstance(value, str):
        return _control(2, len(value.encode())) + value.encode()
    if isinstance(value, dict):
        return _control(7, len(value)) + b''.join(_encoded(k) + _encoded(v) for k, v in value.items())
    return _control(11, len(value)) + b''.join(_encoded(v) for v in value)      # a list


def database(low: int = LOW, high: int = HIGH) -> bytes:
    """An IPv4 ASN database of one node: an address whose first bit is 0 belongs to `low`, the others to `high`."""
    first = _encoded({'autonomous_system_number': (U32, low)})
    second = _encoded({'autonomous_system_number': (U32, high)})

    def record(offset: int) -> bytes:            # a pointer into the data section, past the node and the 16 zeros
        return (1 + 16 + offset).to_bytes(3, 'big')
    meta = {'binary_format_major_version': (U16, 2), 'binary_format_minor_version': (U16, 0), 'build_epoch': (U64, 1),
            'database_type': 'DBIP-ASN-Lite', 'description': {'en': 'test'}, 'ip_version': (U16, 4),
            'languages': ['en'], 'node_count': (U32, 1), 'record_size': (U16, 24)}
    return record(0) + record(len(first)) + bytes(16) + first + second + b'\xab\xcd\xefMaxMind.com' + _encoded(meta)


@pytest.fixture
def geo(settings, tmp_path, monkeypatch) -> Path:
    """An empty GEOIP_DIR, and no database opened yet in this process."""
    settings.GEOIP_DIR = str(tmp_path / 'geo')
    monkeypatch.setattr(operators, '_readers', {})
    cache.clear()
    return tmp_path / 'geo'


def test_an_addresss_operator_is_read_from_the_asn_database(geo):
    assert operators.operator('41.92.10.7') is None                  # no database yet
    geo.mkdir()
    (geo / operators.ASN).write_bytes(database())
    assert operators.operator('41.92.10.7') == LOW                    # looked for again, and found
    assert operators.operator('196.200.1.7') == HIGH
    assert operators.operator('not an address') is None
    assert operators.operator('2001:db8::1') is None                  # an IPv6 address in an IPv4 database


@override_settings(READING_BUDGET=1000, READING_OPERATOR_CEILING=100)
def test_the_ceiling_holds_one_operators_browsers_together_and_no_other(geo, code):
    geo.mkdir()
    (geo / operators.ASN).write_bytes(database())

    def asked(ip: str) -> int:
        return APIClient().get('/api/corpus/at/ma/loi/70-03/?window=40', HTTP_CF_CONNECTING_IP=ip,
                               HTTP_X_FORWARDED_FOR=f'{ip}, 127.0.0.1').status_code
    # Four addresses of one operator, each a browser of its own: together past the operator's 100 articles.
    assert [asked(f'41.92.10.{k}') for k in range(1, 5)] == [200, 200, 200, 429]
    assert asked('196.200.1.7') == 200                                # another operator
    assert asked('not an address') == 200                             # no operator known: its address's day alone


def _months() -> tuple[str, str]:
    today = date.today()
    return today.strftime('%Y-%m'), (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')


def _url(month: str) -> str:
    return f'https://download.db-ip.com/free/dbip-asn-lite-{month}.mmdb.gz'


def test_fetch_geoip_keeps_the_newest_month_that_answers_and_the_asn_database_alone(geo, monkeypatch):
    this, last = _months()
    asked = []

    def urlopen(request, timeout):
        asked.append((request.full_url, request.get_header('User-agent')))
        if this in request.full_url:                                  # this month's is not out yet
            raise urllib.error.HTTPError(request.full_url, 404, 'Not Found', {}, None)
        return io.BytesIO(gzip.compress(database()))

    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    out, err = StringIO(), StringIO()
    call_command('fetch_geoip', stdout=out, stderr=err)
    assert asked == [(_url(this), settings.FETCH_USER_AGENT), (_url(last), settings.FETCH_USER_AGENT)]
    assert out.getvalue() == f'asn: {last}, 0 MB\n' and err.getvalue() == f'{_url(this)}: HTTP Error 404: Not Found\n'
    assert sorted(p.name for p in geo.iterdir()) == [f'dbip-asn-lite-{last}.mmdb', operators.ASN]
    assert operators.operator('41.92.10.7') == LOW
    # The next run asks again for this month alone: last month's file is kept.
    asked.clear()
    call_command('fetch_geoip', stdout=StringIO(), stderr=StringIO())
    assert [url for url, _ in asked] == [_url(this)]


def test_fetch_geoip_says_so_when_no_month_answers(geo, monkeypatch):
    def urlopen(request, timeout):
        raise urllib.error.URLError('no route to host')

    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    with pytest.raises(CommandError, match=r'^no asn database could be fetched$'):
        call_command('fetch_geoip', stdout=StringIO(), stderr=StringIO())
    assert list(geo.iterdir()) == [] and operators.operator('41.92.10.7') is None
