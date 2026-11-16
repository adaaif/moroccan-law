"""Where is the finance bill for a year? (the finance-bill review, P18.) The Chamber of Representatives files
the finance bill in its own dossier (/ar/DossierPLF<year>), not in its feed of bills, so the watcher reads both:

    watch_finance_bill --year 2027 [--fetch]

It prints the feed's listing, the dossier's agenda lines and its files, and with `--fetch` keeps each file not kept yet
under CORPUS_DIR/sources/parliament/plf<year>/ with a MANIFEST.tsv line (file, address, sha256, bytes, time), two
seconds apart, under the project's own name, as robots.txt allows (apps/sources/services/fetch.py); the dossier page itself is kept whenever it changes. The bill must be filed by 20 October (organic law
130.13, art. 48). What a new file is (the text as a chamber voted it) is for a person to read: `load_bill … --stage`.

With `--press` it also reads a few outlets' feeds and lists the articles about the bill that the tax topic's press page
(pages/bill-press) does not hold yet, for a person to read and add (the bill-story review, Y12): no model writes an
item, and nothing is kept until a person adds it.
"""
import hashlib
import html
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote, urljoin

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.sources.services import fetch as fetch_service

FEED = 'https://www.chambredesrepresentants.ma/ar/legislation/loi-discussion-assemblee/rss'
SITE = 'https://www.chambredesrepresentants.ma'
DOSSIER = SITE + '/ar/DossierPLF{year}'
# Outlets whose feeds the watcher reads (26 Oct 2026; Le360's and Médi1's offer none it could).
FEEDS = ['https://www.hespress.com/feed', 'https://fr.hespress.com/feed', 'https://medias24.com/feed/',
         'https://www.telquel.ma/feed', 'https://www.leseco.ma/feed/']
ABOUT = r'(?:مشروع\s+)?قانون\s+المالية\s+(?:لسنة\s+)?{year}|مالية\s+{year}|PLF\s*{year}|loi\s+de\s+finances\s+(?:pour\s+)?{year}'


def press_candidates(feeds: dict[str, str], year: int, known: set[str]) -> list[dict]:
    """The feeds' items whose title names the year's finance bill and whose link the press page does not hold."""
    about = re.compile(ABOUT.format(year=year), re.I)
    out = []
    for feed, body in feeds.items():
        for item in re.findall(r'<item>(.*?)</item>', body, re.S):
            title = re.search(r'<title>(.*?)</title>', item, re.S)
            link = re.search(r'<link>(.*?)</link>', item, re.S)
            date = re.search(r'<pubDate>(.*?)</pubDate>', item, re.S)
            words = html.unescape(re.sub(r'<!\[CDATA\[|\]\]>', '', title.group(1) if title else '')).strip()
            url = html.unescape(re.sub(r'<!\[CDATA\[|\]\]>', '', link.group(1) if link else '')).strip()
            if words and about.search(words) and url not in known:
                out.append({'feed': feed, 'title': words, 'url': url, 'date': date.group(1).strip() if date else ''})
    return out


def bills(feed: str) -> list[dict]:
    """The feed's items: title, the bill's page (the feed escapes its links as HTML), date."""
    out = []
    for item in re.findall(r'<item>(.*?)</item>', feed, re.S):
        title = re.search(r'<title>(.*?)</title>', item, re.S)
        link = re.search(r'<link>(.*?)</link>', item, re.S)
        date = re.search(r'<pubDate>(.*?)</pubDate>', item, re.S)
        href = re.search(r'href="([^"]+)"', unquote(unquote(html.unescape(link.group(1))))) if link else None
        out.append({'title': re.sub(r'<[^>]+>', '', html.unescape(title.group(1) if title else '')).strip(),
                    'page': SITE + href.group(1) if href else '', 'date': date.group(1).strip() if date else ''})
    return out


def dossier(page: str) -> dict:
    """The dossier page's files (each PDF link with its words) and its agenda: the lines that name a day of the week."""
    files = []
    for href, words in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', page, re.S | re.I):
        files.append({'url': urljoin(SITE, href), 'name': re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html.unescape(words))).strip()})
    text = html.unescape(re.sub(r'<[^>]+>', '\n', re.sub(r'<(script|style).*?</\1>', '', page, flags=re.S)))
    agenda = [ln.strip() for ln in text.splitlines()
              if re.match(r'^(الإثنين|الاثنين|الثلاثاء|الأربعاء|الخميس|الجمعة|السبت|الأحد)\s+\d{1,2}', ln.strip())]
    return {'files': files, 'agenda': agenda}


def get(url: str, timeout: float = 120) -> bytes:
    return fetch_service.get(quote(url, safe=':/%?=&'), timeout=timeout)


class Command(BaseCommand):
    help = 'Report where the finance bill for a year stands: the feed, the dossier\'s agenda and files.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, required=True)
        parser.add_argument('--fetch', action='store_true', help='keep the dossier\'s files not kept yet')
        parser.add_argument('--press', action='store_true', help='list the outlets\' articles about the bill not on the press page')

    def handle(self, *args, **opts):
        try:
            fetch_service.agent()       # no name, no run: the press feeds below would each pass the refusal by
            self._run(opts)
        except fetch_service.Refused as exc:
            raise CommandError(str(exc)) from exc

    def _run(self, opts):
        year = opts['year']
        if opts['press']:
            from apps.topics.services import kit
            page = (kit.load('tax') or {}).get('pages', {}).get('bill-press') or {}
            known = {i['url'] for i in page.get('items') or []}
            feeds = {}
            for feed in FEEDS:
                try:
                    feeds[feed] = get(feed, timeout=60).decode('utf-8', 'replace')
                except (OSError, fetch_service.Refused, fetch_service.Outside) as e:     # said and passed
                    self.stdout.write(f'press: {feed} did not answer ({e})')
            found = press_candidates(feeds, year, known)
            for c in found:
                self.stdout.write(f'PRESS {c["date"]}  {c["title"]}\n  {c["url"]}')
            self.stdout.write(f'press: {len(found)} new item(s) for a person to read (pages/bill-press holds {len(known)})')
        feed = get(FEED).decode('utf-8', 'replace')
        found = [b for b in bills(feed) if 'قانون المالية' in b['title'] and str(year) in b['title']
                 and 'التصفية' not in b['title']]
        for bill in found:
            self.stdout.write(f'LISTED in the feed: {bill["title"]}\n  {bill["page"]}\n  {bill["date"]}')
        if not found:
            self.stdout.write(f'feed: not listed ({len(bills(feed))} bills in it)')

        raw = get(DOSSIER.format(year=year))
        folder = Path(settings.CORPUS_DIR) / 'sources' / 'parliament' / f'plf{year}'
        folder.mkdir(parents=True, exist_ok=True)
        manifest = folder / 'MANIFEST.tsv'
        kept = {}
        if manifest.exists():
            for line in manifest.read_text().splitlines()[1:]:
                cols = line.split('\t')
                kept[cols[1]] = cols
        else:
            manifest.write_text('file\tsource\tsha256\tbytes\ttime\n')
        stamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

        def keep(name: str, url: str, body: bytes) -> None:
            digest = hashlib.sha256(body).hexdigest()
            (folder / name).write_bytes(body)
            with manifest.open('a') as m:
                m.write(f'{name}\t{url}\t{digest}\t{len(body)}\t{stamp}\n')

        # The dossier page itself, when it changed since it was last kept.
        digest = hashlib.sha256(raw).hexdigest()
        pages = [c for c in kept.values() if c[0].startswith('dossier-')]
        if not pages or pages[-1][2] != digest:
            keep(f'dossier-{stamp[:10]}-{digest[:8]}.html', DOSSIER.format(year=year), raw)
            self.stdout.write(f'dossier: changed, kept ({digest[:12]})')
        d = dossier(raw.decode('utf-8', 'replace'))
        for line in d['agenda']:
            self.stdout.write(f'agenda: {line}')
        for f in d['files']:
            new = f['url'] not in kept
            self.stdout.write(f'{"NEW " if new else "kept"} {f["name"]}  {f["url"]}')
            if new and opts['fetch']:
                try:
                    body = get(f['url'])
                except (OSError, fetch_service.Outside) as e:
                    # A dead link in the dossier is said and passed (28 Oct 2026: the bill's own file answered 404).
                    self.stdout.write(f'  did not answer ({e}); not kept')
                    time.sleep(2)
                    continue
                # The site may answer a file's link with a page of its own (26 Oct 2026): never kept.
                if not body.startswith(b'%PDF'):
                    self.stdout.write('  not a PDF: the site answered with a page; not kept')
                else:
                    # The name comes from the link: kept only as a plain file name in this folder.
                    try:
                        name = fetch_service.safe_name(unquote(f['url'].rsplit('/', 1)[-1]).replace(' ', '_'))
                        keep(name, f['url'], body)
                    except fetch_service.Outside as e:
                        self.stdout.write(f'  {e}; not kept')
                time.sleep(2)
