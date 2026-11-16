"""The public API's limits: 240 requests a minute from an address (120 until HM17 of the hard-moment review). Every
public view uses it (apps/*/api/views.py PublicView). A request from the machine itself with no proxy in
between (the prerender, the open-data jobs) is not counted: the public always comes through nginx, which
sets X-Forwarded-For. A request with a key (X-Api-Key) is counted on its access's own limits instead, by the key's
middleware in front of the views (apps/opendata/middleware.py, apps/opendata/services/usage.py).

Every limit counts a request by the same address (`ident`): the one nginx appended, which is Cloudflare's view of the
reader, an IPv4 address whole and an IPv6 one by its /64. A line or a phone is given a whole /64 and may use any of its
2^64 addresses, so counting an IPv6 address whole gave a fresh allowance to each of them. The DRF throttles (`ByNetwork`:
the scoped ones, this one, the topics' own), the sign-in brake (apps/accounts/services/brake.py) and the MCP's direct
callers count by it; the day of reading counts wider, by /56 (apps/corpus/services/reading.py), from Cloudflare's view
of the reader (`address`)."""
import ipaddress

from django.conf import settings
from rest_framework.throttling import BaseThrottle, ScopedRateThrottle, SimpleRateThrottle

from config.caching import counters


LOOPBACK = {'127.0.0.1', '::1'}


def bucket(ip: str, v6: int = 64) -> str:
    """The key an address is counted by: an IPv4 address as itself, an IPv6 one by its network of `v6` bits (a /64 is
    one line or one phone)."""
    try:
        address = ipaddress.ip_address((ip or '').strip())
    except ValueError:
        return ip or '-'
    if address.version == 6:
        if address.ipv4_mapped:                 # ::ffff:a.b.c.d is that IPv4 address
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f'{address}/{v6}', strict=False))
    return str(address)


def ident(request) -> str:
    """The address the limits count a request by: the one nginx appended to X-Forwarded-For (NUM_PROXIES), never one a
    client wrote there itself, folded by `bucket`."""
    return bucket(BaseThrottle().get_ident(request) or '')


def address(request) -> str:
    """Cloudflare's view of the reader, else the last address nginx appended (as the public API counts it): the day of
    reading (apps/corpus/services/reading.py) and the crawlers' check (apps/seo/services/crawlers.py) read it."""
    meta = request.META
    return (meta.get('HTTP_CF_CONNECTING_IP') or meta.get('HTTP_X_FORWARDED_FOR', '').split(',')[-1].strip()
            or meta.get('REMOTE_ADDR', '')).strip()


class ByNetwork:
    """A DRF throttle that counts by `ident`, in the store of counts that never evicts (config/caching.py)."""

    @property
    def cache(self):
        return counters

    def get_ident(self, request):
        return ident(request)


class ScopedRate(ByNetwork, ScopedRateThrottle):
    """DRF's scoped limits (`throttle_scope`: sign-in, reports, the beacon, the discussion…), by `ident`."""


class PublicRate(ByNetwork, SimpleRateThrottle):
    scope = 'public'

    def allow_request(self, request, view):
        if request.META.get('REMOTE_ADDR') in LOOPBACK and 'HTTP_X_FORWARDED_FOR' not in request.META:
            return True
        # A search engine's crawler from its published addresses renders the law's pages with these answers (IX10 of
        # the search-engines review); its own pace is the server's answer time and the 429/503 it is given when it is busy.
        from apps.seo.services import crawlers
        if crawlers.of(request):
            return True
        # A call the key's middleware counted already, on its access's minute and day.
        from apps.opendata.middleware import charged
        if charged(request):
            return True
        return super().allow_request(request, view)

    def get_rate(self):
        return settings.PUBLIC_API_RATES['anonymous']

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class OpenRate(PublicRate):
    """The public rate, counted apart from the law's own doors (the corpus, the search, the topics): the discussion,
    the explanations, the follows, the media, the budget and the corrections. One page of a law asks several of these
    beside the law itself, and a mobile operator puts thousands of readers behind one address: in one count with the
    law's answers, these doors would spend the readers' allowance for the law."""
    scope = 'open'


# The limits of a door anyone may open without signing in, outside the law's own: that rate by address, and
# the view's own scope beside it when it has one (the checks, the reports). Setting `throttle_classes` replaces the
# default list, so the scoped limit is named again.
OPEN = [OpenRate, ScopedRate]
