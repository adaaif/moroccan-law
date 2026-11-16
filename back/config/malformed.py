"""What a request may carry before any view reads it (OP53 of the open-source audit).

A NUL character or half of a UTF-16 pair cannot be stored in Postgres or even sent to it: a query holding one fails
in the driver, and the request answered 500. A body that is a JSON list, a number or a string where every view reads
an object made `request.data.get` fail the same way, and a JSON body of a few thousand «[» was too deep for Python's
reader. So:

- `RefuseUnstorable`, a middleware, answers 400 to an address or a query string holding a NUL, before any view;
- the API's parsers (`REST_FRAMEWORK['DEFAULT_PARSER_CLASSES']`) refuse a JSON body that is not one object, one nested
  past what Python reads, and any body whose names or values hold a NUL or a lone surrogate.

Each refusal is the one error shape, `{"errors": [{"field": "request", "code": …}]}`, with DRF's codes for the
characters (`null_characters_not_allowed`, `surrogate_characters_not_allowed`, as its serializers' fields say)."""
import re

from django.http import JsonResponse
from rest_framework import parsers
from rest_framework.exceptions import ParseError

NUL = 'null_characters_not_allowed'
SURROGATE = 'surrogate_characters_not_allowed'
_NUL_OR_SURROGATE = re.compile('[\x00\ud800-\udfff]')


def unstorable(value: str) -> str | None:
    """The code for a string Postgres cannot hold, else None."""
    found = _NUL_OR_SURROGATE.search(value)
    if found is None:
        return None
    return NUL if found.group() == '\x00' else SURROGATE


def _refused(code: str) -> ParseError:
    return ParseError(code, code=code)


def _check_strings(data) -> None:
    """Every name and string in a parsed body, read without recursion (a body may nest as deep as JSON allows)."""
    pending = [data]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            if code := unstorable(item):
                raise _refused(code)
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, (list, tuple)):
            pending.extend(item)


class JSONParser(parsers.JSONParser):
    """One JSON object, as every view of the API reads; its strings storable."""

    def parse(self, stream, media_type=None, parser_context=None):
        try:
            data = super().parse(stream, media_type, parser_context)
        except RecursionError:
            raise _refused('parse_error') from None
        if not isinstance(data, dict):
            raise _refused('parse_error')
        _check_strings(data)
        return data


class FormParser(parsers.FormParser):
    def parse(self, stream, media_type=None, parser_context=None):
        data = super().parse(stream, media_type, parser_context)
        _check_strings(list(data.lists()))
        return data


class MultiPartParser(parsers.MultiPartParser):
    """A form with files: its fields' names and values storable (the files are read by their own services)."""

    def parse(self, stream, media_type=None, parser_context=None):
        parsed = super().parse(stream, media_type, parser_context)
        _check_strings(list(parsed.data.lists()))
        return parsed


class RefuseUnstorable:
    """An address or a query string holding a NUL is refused before any view reads it: its words would reach the
    database in a lookup and fail there. (A query string is decoded with replacement characters, so it holds no lone
    surrogate.)"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        query = request.META.get('QUERY_STRING', '')
        if '\x00' in request.path or (('%00' in query or '\x00' in query) and any(
                '\x00' in key or any('\x00' in v for v in values) for key, values in request.GET.lists())):
            return JsonResponse({'errors': [{'field': 'request', 'code': NUL}]}, status=400)
        return self.get_response(request)
