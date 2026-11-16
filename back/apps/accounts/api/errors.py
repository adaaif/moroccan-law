"""One error shape for the whole API: {"errors": [{"field": ..., "code": ...}]}."""
import re

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status, views
from rest_framework.exceptions import UnsupportedMediaType
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.services.accounts import AccountError
from apps.accounts.services.refusals import Refused
from config.malformed import JSONParser


def errors_response(pairs, http_status=status.HTTP_400_BAD_REQUEST):
    """`pairs` are (field, code) or (field, code, extra): extra is data for the sentence (a suggestion, minutes)."""
    return Response({'errors': [{'field': p[0], 'code': p[1], **(p[2] if len(p) > 2 else {})} for p in pairs]},
                    status=http_status)


def serializer_errors_response(serializer):
    pairs = [(field, detail.code)
             for field, details in serializer.errors.items()
             for detail in details]
    return errors_response(pairs)


def _first_code(codes) -> str:
    """A nested serializer's codes come as lists and dicts: the first one."""
    while isinstance(codes, (list, dict)):
        codes = next(iter(codes.values() if isinstance(codes, dict) else codes), 'invalid')
    return str(codes)


def exception_handler(exc, context):
    """DRF's own refusals in the one shape (REST_FRAMEWORK['EXCEPTION_HANDLER']): a limit's 429, 401, 403, 404, 405, 415, a
    body that does not parse. Their status and headers (Retry-After, WWW-Authenticate) are DRF's; their sentence becomes a
    code: {"errors": [{"field": "request", "code": "throttled"}]}. A validation error keeps its fields."""
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()
    response = views.exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, exceptions.ValidationError) and isinstance(exc.detail, dict):
        pairs = [(field, code) for field, codes in exc.get_codes().items()
                 for code in (codes if isinstance(codes, list) and all(isinstance(c, str) for c in codes)
                              else [_first_code(codes)])]
    elif isinstance(exc, exceptions.ValidationError):
        pairs = [('request', _first_code(exc.get_codes()))]
    else:
        codes = exc.get_codes()
        pairs = [('request', codes if isinstance(codes, str) else exc.default_code)]
    response.data = {'errors': [{'field': field, 'code': code} for field, code in pairs]}
    return response


_UUID = re.compile(r'[0-9a-fA-F]{8}-?(?:[0-9a-fA-F]{4}-?){3}[0-9a-fA-F]{12}')
MOST_ID = 2**63 - 1


def _is_id(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0 <= value <= MOST_ID
    return isinstance(value, str) and value.isdecimal() and len(value) <= 18


def require_types(data, *, words=(), ids=(), uuids=(), lists=()) -> None:
    """The fields of a body a service will read, each of its kind: `words` strings, `ids` a row's number (a whole number
    or its digits), `uuids` a voice's or a picture's id (one, a list of them, or a comma-separated string), `lists` a
    list of strings or one string. A field missing, null or '' passes, as the services read it. The first field of
    another kind is refused, 400 `<field>.invalid`, before a service reads a list as words or a word as a number: that
    answered 500."""
    for name in words:
        if (value := data.get(name)) is not None and not isinstance(value, str):
            raise Refused(name, 'invalid')
    for name in ids:
        if (value := data.get(name)) not in (None, '') and not _is_id(value):
            raise Refused(name, 'invalid')
    for name in uuids:
        value = data.get(name)
        items = value if isinstance(value, list) else value.split(',') if isinstance(value, str) else [value]
        if value not in (None, '') and not all(isinstance(v, str) and (not v or _UUID.fullmatch(v)) for v in items):
            raise Refused(name, 'invalid')
    for name in lists:
        value = data.get(name)
        if value is not None and not isinstance(value, str) and not (
                isinstance(value, list) and all(isinstance(v, str) for v in value)):
            raise Refused(name, 'invalid')


class RefusingView(APIView):
    """A view whose services refuse by raising: Refused and AccountError answer in the one error shape."""

    def handle_exception(self, exc):
        if isinstance(exc, Refused):
            return errors_response([(exc.field, exc.code, exc.extra)], exc.status)
        if isinstance(exc, AccountError):
            return errors_response(exc.errors)
        return super().handle_exception(exc)


class JsonOnly:
    """The doors anyone may knock on without signing in read JSON alone. A form on another site can post its visitors
    to a form-encoded or multipart door with no warning from their browser (a JSON body from another site needs the
    browser to ask first, and CORS answers no): they would sign in, sign up or ask for reset letters in someone else's
    name, and the limits would count the visitors. Anything else is 415 `body.unsupported_media_type`."""

    parser_classes = [JSONParser]

    def handle_exception(self, exc):
        if isinstance(exc, UnsupportedMediaType):
            return errors_response([('body', exc.default_code)], status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        return super().handle_exception(exc)
