"""The reads of v1 that will go, and the one place their answers say so.

Inside v1 a read is never changed under a program's feet: a field is added, never renamed or removed. A read that will
go is announced at least 90 days ahead, in a letter to the holders of the keys that used it and on each of its answers:
`Deprecation: @<unix time>` (RFC 9745), the moment it stopped being the way to do it, and `Sunset: <HTTP date>`
(RFC 8594), the day it stops answering. Empty while no read is going."""
from datetime import UTC, date, datetime, time

from django.utils.http import http_date

# {the read's route name (v1/urls.py): (the day it is deprecated, the day it stops answering)}
ROUTES: dict[str, tuple[date, date]] = {}


def _moment(day: date) -> int:
    return int(datetime.combine(day, time(), tzinfo=UTC).timestamp())


def mark(route: str | None, response):
    """`response` with the two headers when its read is going; untouched otherwise."""
    when = ROUTES.get(route or '')
    if when:
        deprecated_on, sunset_on = when
        response['Deprecation'] = f'@{_moment(deprecated_on)}'
        response['Sunset'] = http_date(_moment(sunset_on))
    return response
