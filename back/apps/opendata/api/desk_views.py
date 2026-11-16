"""/api/access/desk/: the access desk, for an active superuser (403 (`desk`, `forbidden`) to every other account, 401
to nobody signed in). Thin views: each reads its fields, calls a service (services/desk.py reads; requests.py,
access.py and keys.py act) and answers; each acting door answers the sheet it acted on. Accepting, changing and ending
need `confirm: true`, which the web's second tap sends. Every answer is `no-store`; the limit (`access_desk`) counts
per account."""
from datetime import date

from rest_framework import exceptions
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.accounts.api.errors import RefusingView
from apps.accounts.services.refusals import Refused
from apps.opendata.services import access as accesses
from apps.opendata.services import desk, keys, requests


class Superuser(BasePermission):
    """An active superuser: the desk's one permission, checked on every call (the web only hides the link)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_superuser)


class DeskView(RefusingView):
    permission_classes = [Superuser]
    throttle_scope = 'access_desk'

    def permission_denied(self, request, message=None, code=None):
        if request.authenticators and not request.successful_authenticator:
            raise exceptions.NotAuthenticated()
        raise Refused('desk', 'forbidden', 403)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response

    @property
    def body(self):
        return self.request.data


# ── What a body says, checked before a service reads it ──────────────────────────────────────────────────────────

def _flag(data, name: str, default=None):
    value = data.get(name, default)
    if value is not None and not isinstance(value, bool):
        raise Refused(name, 'invalid')
    return value


def _number(data, name: str) -> int | None:
    value = data.get(name)
    if value in (None, ''):
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise Refused(name, 'invalid')
    return value


def _day(data, name: str) -> date | None:
    """A day written YYYY-MM-DD, or None when left out."""
    value = data.get(name)
    if value in (None, ''):
        return None
    if isinstance(value, str) and len(value) == 10:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise Refused(name, 'invalid')


def _words(data, name: str):
    value = data.get(name)
    if value is not None and not isinstance(value, str):
        raise Refused(name, 'invalid')
    return value


def _confirmed(data) -> None:
    if data.get('confirm') is not True:
        raise Refused('confirm', 'required')


def _granting(data) -> dict:
    """What accepting grants, as the body says it."""
    return {'api': bool(_flag(data, 'api', False)), 'data': bool(_flag(data, 'data', False)),
            'size': _words(data, 'size'), 'ends_on': _day(data, 'ends_on'), 'minute': _number(data, 'minute'),
            'calls': _number(data, 'calls'), 'articles': _number(data, 'articles')}


# ── Reads ──────────────────────────────────────────────────────────────────────────────────────────────────────────

class Home(DeskView):
    """GET: the programme's state, what waits, what ends soon, the figures."""

    def get(self, request):
        return Response(desk.overview())


class Requests(DeskView):
    """GET ?state=waiting|more|accepted|declined|all&q=&cursor=: a page of requests, with the counts by state."""

    def get(self, request):
        p = request.query_params
        return Response(desk.requests_page(p.get('state'), p.get('q'), p.get('cursor')))


class RequestSheet(DeskView):
    """GET: a request's sheet."""

    def get(self, request, pk):
        return Response(desk.request_sheet(pk, request.user))


class Accesses(DeskView):
    """GET ?state=live|ending|ended|unused|all&q=&cursor=: a page of accesses, with the counts by state."""

    def get(self, request):
        p = request.query_params
        return Response(desk.accesses_page(p.get('state'), p.get('q'), p.get('cursor')))


class AccessSheet(DeskView):
    """GET: an access's sheet."""

    def get(self, request, pk):
        return Response(desk.access_sheet(pk))


class Use(DeskView):
    """GET ?days=30: use across every access."""

    def get(self, request):
        return Response(desk.use(desk.days_asked(request.query_params.get('days'))))


class Editions(DeskView):
    """GET: the editions, and who took them."""

    def get(self, request):
        return Response(desk.editions_list())


class Log(DeskView):
    """GET ?cursor=: every act, the newest first."""

    def get(self, request):
        return Response(desk.log_page(request.query_params.get('cursor')))


# ── A request's answers ────────────────────────────────────────────────────────────────────────────────────────────

class Preview(DeskView):
    """POST {act: accept|ask|decline, …the act's fields}: the letter as the person would read it. Nothing is written
    or sent."""

    def post(self, request, pk):
        r = desk.the_request(pk)
        act = _words(self.body, 'act')
        if act == 'accept':
            fields = _granting(self.body)
        elif act == 'ask':
            fields = {'line': self.body.get('line')}
        elif act == 'decline':
            fields = {'reason': self.body.get('reason')}
        else:
            raise Refused('act', 'invalid')
        letter = requests.letter_of(r, request.user, act, **fields)
        return Response({'language': letter.language, 'subject': letter.subject, 'body': letter.body})


class Accept(DeskView):
    """POST {api, data, size, minute, calls, articles, ends_on, confirm: true}."""

    def post(self, request, pk):
        r = desk.the_request(pk)
        _confirmed(self.body)
        requests.accept(r, request.user, **_granting(self.body))
        return Response(desk.request_sheet(pk, request.user))


class Ask(DeskView):
    """POST {line}."""

    def post(self, request, pk):
        requests.ask(desk.the_request(pk), request.user, self.body.get('line'))
        return Response(desk.request_sheet(pk, request.user))


class Decline(DeskView):
    """POST {reason}."""

    def post(self, request, pk):
        requests.decline(desk.the_request(pk), request.user, self.body.get('reason'))
        return Response(desk.request_sheet(pk, request.user))


# ── An access's acts ───────────────────────────────────────────────────────────────────────────────────────────────

class Change(DeskView):
    """POST {api, data, size, minute, calls, articles, confirm: true}: what is left out stays."""

    def post(self, request, pk):
        a = desk.the_access(pk)
        _confirmed(self.body)
        accesses.change(a, request.user, api=_flag(self.body, 'api'), data=_flag(self.body, 'data'),
                        size=_words(self.body, 'size') or None, minute=_number(self.body, 'minute'),
                        calls=_number(self.body, 'calls'), articles=_number(self.body, 'articles'))
        return Response(desk.access_sheet(pk))


class Renew(DeskView):
    """POST {ends_on}: a year from today when left out."""

    def post(self, request, pk):
        accesses.renew(desk.the_access(pk), request.user, _day(self.body, 'ends_on'))
        return Response(desk.access_sheet(pk))


class End(DeskView):
    """POST {reason: terms|leaked|unused, confirm: true}."""

    def post(self, request, pk):
        a = desk.the_access(pk)
        _confirmed(self.body)
        accesses.end_by_staff(a, request.user, self.body.get('reason'))
        return Response(desk.access_sheet(pk))


class KeyEnd(DeskView):
    """POST: a key the staff ends (it leaked); its holder is told to make a new one."""

    def post(self, request, pk):
        key = keys.end_by_staff(desk.the_key(pk), request.user)
        return Response(desk.access_sheet(key.access_id))
