"""IndexNow (IX14 of the search-engines review): Bing, Yandex, Seznam, Naver and the others it tells hear of a text the day it
changes instead of on their next pass. Google does not read it; the sitemaps' lastmod tells Google (sitemaps.py).
Nothing is sent while INDEXING is not 'open'. The key is published at /indexnow.txt (apps.seo.views)."""
import hashlib
import hmac
import json
import logging
import urllib.request
from urllib.parse import urlparse

from django.conf import settings

log = logging.getLogger(__name__)

ENDPOINT = 'https://api.indexnow.org/indexnow'
MOST = 10_000           # addresses per request, IndexNow's limit


def key() -> str:
    return settings.INDEXNOW_KEY or hmac.new(settings.SECRET_KEY.encode(), b'indexnow', hashlib.sha256).hexdigest()[:32]


def submit(paths: list[str]) -> int:
    """Tell IndexNow these addresses changed; the number told. Nothing while the site is closed to search engines."""
    if settings.INDEXING != 'open' or not paths:
        return 0
    site = settings.SITE_URL.rstrip('/')
    told = 0
    for start in range(0, len(paths), MOST):
        batch = paths[start:start + MOST]
        body = json.dumps({'host': urlparse(site).hostname, 'key': key(), 'keyLocation': f'{site}/indexnow.txt',
                           'urlList': [site + p for p in batch]}).encode()
        request = urllib.request.Request(ENDPOINT, data=body, headers={'Content-Type': 'application/json; charset=utf-8'})
        try:
            with urllib.request.urlopen(request, timeout=30) as answer:
                if answer.status in (200, 202):
                    told += len(batch)
        except OSError as exc:
            log.warning('indexnow: %s addresses not told (%s)', len(batch), exc)
    return told
