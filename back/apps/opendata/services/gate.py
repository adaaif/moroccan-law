"""Where the database and the keyed API stand: `closed` for everyone, `request` (given to a person the staff
accepted) or `open` to all. One setting, `OPEN_DATA`."""
from django.conf import settings

CLOSED, REQUEST, OPEN = 'closed', 'request', 'open'


def position() -> str:
    """The setting's position. It was a yes or a no before it had three: True reads `open`, False `closed`."""
    value = settings.OPEN_DATA
    if value is True:
        return OPEN
    if not value:
        return CLOSED
    value = str(value).strip().lower()
    if value in ('true', '1', 'yes', 'on'):
        return OPEN
    return value if value in (REQUEST, OPEN) else CLOSED
