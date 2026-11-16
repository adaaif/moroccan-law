"""The bills as filed with the Chamber of Representatives, for the laws in the corpus (row 11): the Chamber's search
finds the bill's page, the page gives the bill as filed («النص كما أودع», not the committee's report); each file
fetched politely (two seconds apart, under the project's own name, as robots.txt allows: apps/sources/services/
fetch.py), kept under CORPUS_DIR/sources/parliament/ with its hash and registered. Without --fetch it names the laws
it would look for and asks the Chamber nothing.

    fetch_bills                         # the laws whose bill is not held
    fetch_bills --fetch --only 013-26
    fetch_bills --fetch                 # every law and organic law the corpus holds
"""
import time
import urllib.error

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.corpus.models import Text, TextType
from apps.parliament.services.memoranda import bill_file, bill_page, search_urls
from apps.sources.models import Document, DocumentKind, Source
from apps.sources.services import fetch as fetch_service
from apps.sources.services.ingest import ingest_file


def get(url: str) -> str:
    time.sleep(2)
    return fetch_service.get(url, timeout=120).decode('utf-8', 'replace')


class Command(BaseCommand):
    help = 'Fetch the bills as filed for the laws in the corpus.'

    def add_arguments(self, parser):
        parser.add_argument('--only', nargs='*', default=[])
        parser.add_argument('--fetch', action='store_true', help="search the Chamber's site and fetch each bill found")

    def handle(self, *args, only, fetch, **opts):
        try:
            self._run(only, fetch)
        except fetch_service.Refused as exc:
            raise CommandError(str(exc)) from exc

    def _run(self, only, fetch):
        folder = settings.CORPUS_DIR / 'sources' / 'parliament'
        laws = Text.objects.filter(type__in=[TextType.LAW, TextType.ORGANIC_LAW], versions__isnull=False).distinct()
        if only:
            laws = laws.filter(number__in=only)
        held = set(Document.objects.filter(source=Source.PARLIAMENT).values_list('meta__text_uri', flat=True))
        laws = [law for law in laws.order_by('-number') if law.akn_uri not in held]
        if not fetch:
            for law in laws:
                self.stdout.write(f'{law.number.replace("-", "."):>8}  {law.title_ar[:70]}')
            self.stdout.write(f'{len(laws)} laws whose bill is not held: --fetch searches the Chamber\'s site for them')
            return
        folder.mkdir(parents=True, exist_ok=True)
        found = missing = 0
        for law in laws:
            printed = law.number.replace('-', '.')
            try:
                page = next((found for found in (bill_page(get(u), printed) for u in search_urls(printed, law.title_ar))
                             if found), None)
                url = bill_file(get(page)) if page else None
            except (urllib.error.URLError, fetch_service.Outside):     # no answer, or a result on another host
                url = None
            if not url:
                missing += 1
                self.stdout.write(f'{printed:>8}  not found')
                continue
            path = folder / fetch_service.safe_name(f'bill_{printed}.pdf')
            if not path.exists():
                time.sleep(2)
                try:
                    data = fetch_service.get(url, timeout=120)
                except fetch_service.Outside as exc:      # a link the page gives to another host: said, left
                    missing += 1
                    self.stderr.write(str(exc))
                    continue
                if not data.startswith(b'%PDF'):
                    missing += 1
                    continue
                path.write_bytes(data)
            doc = ingest_file(path, source=Source.PARLIAMENT, kind=DocumentKind.PARLIAMENT, language='ar', url=url,
                              title=f'مشروع قانون رقم {printed} — النص كما أودع',
                              meta={'text_uri': law.akn_uri, 'bill': printed, 'page': page})
            if doc.meta.get('text_uri') != law.akn_uri:      # registered before, as a sample
                doc.meta = {**doc.meta, 'text_uri': law.akn_uri, 'bill': printed, 'page': page}
                doc.url = doc.url or url
                doc.save(update_fields=['meta', 'url'])
            found += 1
            self.stdout.write(f'{printed:>8}  {url}')
        self.stdout.write(f'{found} bills fetched, {missing} not found on the Chamber\'s site')
