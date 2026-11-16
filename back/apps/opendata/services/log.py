"""The log of what happened to a request or an access: one `Event` an act. Every service that changes one calls
`note`, whichever door the act came by (the desk, the admin, the account's own page, the night's job), so a request's
history and the decisions' log are the same rows."""
from datetime import date, datetime

from apps.opendata.models import Event

Act = Event.Act


def _plain(value):
    """A detail as JSON holds it: a day as YYYY-MM-DD, a dict's values the same way."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def _row(act: str, by, request, access, details: dict) -> Event:
    return Event(act=act, by=by if getattr(by, 'pk', None) else None,
                 request_id=getattr(request, 'pk', request), access_id=getattr(access, 'pk', access),
                 details=_plain(details))


def note(act: str, *, by=None, request=None, access=None, **details) -> Event:
    """Keep one act. `request` and `access` are rows or their ids. `details` holds codes, numbers and dates only (a
    size, a reason, an end date, the line the staff asked): never a key, never what the account typed."""
    event = _row(act, by, request, access, details)
    event.save()
    return event


def note_each(act: str, accesses, *, by=None, **details) -> None:
    """The same act on each of `accesses`, in one write whatever their number (the night ending many at once)."""
    Event.objects.bulk_create([_row(act, by, None, a, details) for a in accesses])
