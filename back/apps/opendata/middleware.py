"""A request that carries a key (X-Api-Key) to the site's own API and pages.

Held here, in front of every view, rather than in the public rate: a key is read on more doors than the views that
count the public rate (the day of reading counts a law's page drawn by Django, a Word file, a printed page), and a door
added tomorrow is held without being told. A request without a key passes untouched: the site's readers see no
change.

For a keyed request:
- a key that opens nothing: 401 (`key`, `invalid` | `ended` | `expired`);
- any key while the database and the keyed API are closed (`gate.position()`): 403 (`access`, `closed`);
- a key whose access does not include the API: 403 (`access`, `no_api`);
- otherwise one call counted on the access's minute and day (door `site`) in place of the address's public rate, or
  429 (`key`, `minute` | `calls`) with Retry-After past a limit. The articles are counted by the day of reading, on the
  access (apps/corpus/services/reading.py).
Every answer to a key that opens something carries RateLimit-Policy and RateLimit; config/caching.py marks it private.

The doors with rules of their own are left to themselves: an account's own access and keys (/api/access/, read with
the site's sign-in), the versioned API (/api/v1/, where a key is required), the edition (/api/open/, which asks for the
database, not the API) and the admin."""
from django.http import JsonResponse

from apps.opendata.services import gate, keys, usage

OWN_RULES = ('/api/access/', '/api/v1/', '/api/open/', '/admin/')
_CHARGED = '_access_charged'


def refusal(field: str, code: str, status: int, retry: int | None = None) -> JsonResponse:
    """A refusal in the one error shape; never kept by a cache."""
    response = JsonResponse({'errors': [{'field': field, 'code': code}]}, status=status)
    response['Cache-Control'] = 'no-store'
    if retry is not None:
        response['Retry-After'] = str(retry)
    return response


def charged(request) -> bool:
    """Whether this request's call was counted on its key's access (the public rate then counts nothing more)."""
    return bool(getattr(getattr(request, '_request', request), _CHARGED, False))


class Keys:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not keys.sent(request) or request.path.startswith(OWN_RULES):
            return self.get_response(request)
        try:
            holder = keys.holder(request)
        except keys.Refused as refused:
            return refusal('key', refused.code, 401)
        if gate.position() == gate.CLOSED:
            return refusal('access', 'closed', 403)
        if not holder.api:
            return refusal('access', 'no_api', 403)
        try:
            usage.charge(holder, 'site')
        except usage.Limit as limit:
            response = refusal('key', limit.code, 429, limit.retry)
        else:
            setattr(request, _CHARGED, True)
            response = self.get_response(request)
        for name, value in usage.headers(holder).items():
            response[name] = value
        return response
