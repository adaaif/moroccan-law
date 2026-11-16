"""Rows the access tests share: an account with an accepted request and its access, and a key of it."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.discussion.tests.conftest import make_user
from apps.opendata.models import Access, ApiKey, Request


def asked(user=None, **fields) -> Request:
    """A request as an account sent it, waiting for an answer."""
    name = fields.pop('username', 'asker')
    user = user or make_user(name)
    given = {'name': 'A research group', 'kind': Request.Kind.SCHOOL, 'purpose': 'How a code changed over time.',
             'wants_api': True, 'wants_data': False, 'volume': Request.Volume.SMALL, 'terms': settings.ACCESS_TERMS}
    return Request.objects.create(user=user, **{**given, **fields})


def accepted(user=None, *, api=True, data=False, size=Access.Size.APP, days=365, **fields) -> Access:
    """An account's live access, with the accepted request behind it."""
    request = asked(user, wants_api=api, wants_data=data, state=Request.State.ACCEPTED,
                    username=fields.pop('username', 'holder'))
    return Access.objects.create(user=request.user, request=request, api=api, data=data, size=size,
                                 ends_on=timezone.localdate() + timedelta(days=days), **fields)


def keyed(access=None, **fields) -> tuple[Access, str]:
    """An access and a live key of it, as its holder would send it in `X-Api-Key`."""
    access = access or accepted(**fields)
    return access, ApiKey.issue(access, 'tests')[1]
