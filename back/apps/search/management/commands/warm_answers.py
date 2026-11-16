"""After a deploy, the pages readers open most are asked for before readers ask (31 Oct 2026; brought back with the
measures, 15 Nov 2026): a deploy forgets the kept answers, and the first reader of a law would otherwise wait while its
answer is built. The last 7 days' most shown addresses (the day counts' `page.path`) are asked of the site's own nginx,
one at a time, as a reader's browser asks them: the page, and for a law or an article also the text's answer the app
reads (its first window, as the page's own drawing does). Its user agent says it is a machine, so no measure counts
it. With no count yet, it warms nothing and says so.

    warm_answers [--top 200] [--base http://127.0.0.1:8041] [--host <SITE_URL's host>]"""
import time
import urllib.request
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.analytics.services import report
from apps.corpus.services.heads import WINDOW

AGENT = 'law-warm (python)'
DAYS = 7


def asked(path: str) -> list[str]:
    """What a reader's opening of `path` asks the server first: the page, and a law's or an article's text answer."""
    return [path, f'/api/corpus/at{path}/?window={WINDOW}'] if path.startswith('/ma/') else [path]


class Command(BaseCommand):
    help = 'Ask the last 7 days\' most shown pages again after a deploy, before readers do.'

    def add_arguments(self, parser):
        parser.add_argument('--top', type=int, default=200)
        parser.add_argument('--base', default='http://127.0.0.1:8041')     # nginx: the way readers' requests come
        parser.add_argument('--host', default=urlparse(settings.SITE_URL).netloc)

    def handle(self, *args, top, base, host, **opts):
        paths = report.most_shown(days=DAYS, most=top)
        if not paths:
            self.stdout.write(f'no page shown in the last {DAYS} days is counted yet: nothing to warm')
            return
        started, slow, failed, asks = time.monotonic(), [], 0, 0
        for path in paths:
            for url in asked(path):
                asks += 1
                request = urllib.request.Request(base + url, headers={
                    'Host': host, 'User-Agent': AGENT, 'Accept-Encoding': 'gzip', 'X-Forwarded-Proto': 'https'})
                t = time.monotonic()
                try:
                    urllib.request.urlopen(request, timeout=60).read()
                except Exception:       # noqa: BLE001 — an answer that fails here fails for readers too: counted, said
                    failed += 1
                    continue
                if (ms := (time.monotonic() - t) * 1000) > 1000:
                    slow.append(f'{url} {ms:.0f} ms')
        self.stdout.write(f'{len(paths)} pages warmed ({asks} answers) in {time.monotonic() - started:.0f} s, '
                          f'{failed} failed' + (f"; slowest: {', '.join(slow[:5])}" if slow else ''))
