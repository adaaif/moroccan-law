"""The SGG's consolidated texts (row 19): its list page names about 67 texts, each a PDF it keeps up to date. With
--fetch, every PDF not held is fetched once, politely (one at a time, two seconds apart, under the project's own name,
as robots.txt allows: apps/sources/services/fetch.py), kept under CORPUS_DIR/sources/sgg_consolidated/ with its hash,
and every text registered as a Document with its pages' text layer. Without it, the list and what --fetch would do:

    fetch_sgg_consolidated                         # the list: held, or to fetch
    fetch_sgg_consolidated --fetch                 # fetch what is missing, register everything
    fetch_sgg_consolidated --fetch --only 2_00 52_05

The text layer is not shown to readers (its lam-alef ligatures come out reversed: «األمانة»); the consolidation
check reads it through a fold that does not mind the order of a word's letters."""
import html
import re
import time
from urllib.parse import urljoin

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.sources.models import DocumentKind, Source
from apps.sources.services import fetch as fetch_service
from apps.sources.services.ingest import ingest_file

LIST = 'https://www.sgg.gov.ma/arabe/textesconsolides.aspx'


def get(url: str) -> bytes:
    return fetch_service.get(url, timeout=120)


def listing(page: str) -> list[dict]:
    """[{url, stem, title}] in the list's order; the stem is the file's name («52_05», «1_58_376»), kept only when it
    is a plain one."""
    out = []
    for href, label in re.findall(r'href="([^"]*textesconsolides/[^"]+\.pdf)"[^>]*>(.*?)</a>', page, re.I | re.S):
        try:
            stem = fetch_service.safe_name(href.rsplit('/', 1)[1][:-4])
        except fetch_service.Outside:
            continue
        title = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', label))).strip()
        out.append({'url': urljoin(LIST, href), 'stem': stem, 'title': title})
    return out


class Command(BaseCommand):
    help = "Fetch and register the SGG's consolidated texts (with --fetch; without it, the list)."

    def add_arguments(self, parser):
        parser.add_argument('--fetch', action='store_true', help='fetch the texts not held and register every one')
        parser.add_argument('--only', nargs='*', default=[], help='stems to fetch, e.g. 2_00 52_05')

    def handle(self, *args, fetch, only, **opts):
        folder = settings.CORPUS_DIR / 'sources' / 'sgg_consolidated'
        try:
            items = listing(get(LIST).decode('utf-8', 'replace'))
        except fetch_service.Refused as exc:
            raise CommandError(str(exc)) from exc
        if only:
            items = [i for i in items if i['stem'] in only]
        if not fetch:
            missing = [i for i in items if not (folder / f'{i["stem"]}.pdf').exists()]
            for item in items:
                self.stdout.write(f'{item["stem"]:>12}  {"to fetch" if item in missing else "held":>8}  {item["title"][:60]}')
            self.stdout.write(f'{len(items)} texts, {len(missing)} not held: --fetch fetches them and registers every text')
            return
        folder.mkdir(parents=True, exist_ok=True)
        fetched = 0
        for i, item in enumerate(items, 1):
            path = folder / f'{item["stem"]}.pdf'
            if not path.exists():
                time.sleep(2)
                try:
                    data = get(item['url'])
                except fetch_service.Refused as exc:
                    raise CommandError(str(exc)) from exc
                except fetch_service.Outside as exc:          # a link to another host: said, left
                    self.stderr.write(str(exc))
                    continue
                if not data.startswith(b'%PDF'):
                    self.stderr.write(f'{item["stem"]}: not a PDF ({len(data)} bytes)')
                    continue
                path.write_bytes(data)
                fetched += 1
            doc = ingest_file(path, source=Source.SGG_CONSOLIDATED, kind=DocumentKind.CONSOLIDATED_TEXT,
                              language='ar', url=item['url'], title=item['title'],
                              meta={'stem': item['stem'], 'list_order': i})
            self.stdout.write(f'{item["stem"]:>12}  {doc.page_count or 0:>4} pages  {item["title"][:60]}')
        self.stdout.write(f'{len(items)} texts, {fetched} fetched now')
