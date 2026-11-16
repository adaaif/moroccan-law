"""An Adala file into the corpus (F2 of the family plan): with --fetch, fetched from the Ministry of Justice's portal
(under the project's own name, as robots.txt allows: apps/sources/services/fetch.py), kept under
CORPUS_DIR/sources/adala/ with its hash, and registered with its pages read, ready for `load_adala`. Without --fetch it
says what it would fetch and where.

    fetch_adala "https://adala.justice.gov.ma/api/uploads/2025/03/21/…15.01…pdf" --name kafala_15_01 --fetch
    fetch_adala "<its url>" --kept sources/road/adala_2_10_420_ar_2026.pdf   # a file already fetched, with its hash
"""
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit, urlunsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.sources.models import DocumentKind, Source
from apps.sources.services import fetch as fetch_service
from apps.sources.services.ingest import ingest_file


class Command(BaseCommand):
    help = 'Fetch an Adala PDF into CORPUS_DIR/sources/adala/ and register it.'

    def add_arguments(self, parser):
        parser.add_argument('url')
        parser.add_argument('--name', help='the file name, without .pdf')
        parser.add_argument('--kept', help='a file already fetched from that address, under CORPUS_DIR: registered as it is')
        parser.add_argument('--language', default='ar', choices=['ar', 'fr'])
        parser.add_argument('--fetch', action='store_true', help='fetch the file (without it: say what would be fetched)')

    def handle(self, *args, url, name=None, kept=None, language='ar', fetch=False, **opts):
        if urlsplit(url).netloc != 'adala.justice.gov.ma':
            raise CommandError('only adala.justice.gov.ma')
        root = Path(settings.CORPUS_DIR)
        if kept:
            # Checked by its own parts, never by resolving links: the corpus's folders are links to another disk
            # (ingest.corpus_path checks a document's path the same way).
            parts = PurePosixPath(kept)
            if parts.is_absolute() or '..' in parts.parts:
                raise CommandError(f'{kept}: not under CORPUS_DIR')
            path = root / parts
            if not path.read_bytes().startswith(b'%PDF'):
                raise CommandError(f'{kept}: not a PDF')
            doc = ingest_file(path, source=Source.ADALA, kind=DocumentKind.TEXT, language=language, url=url)
            self.stdout.write(f'{doc.path}: {doc.page_count} pages, sha256 {doc.sha256[:12]}…')
            return
        if not name:
            raise CommandError('--name or --kept')
        try:
            path = root / 'sources' / 'adala' / fetch_service.safe_name(f'{name}.pdf')
        except fetch_service.Outside as exc:
            raise CommandError(str(exc)) from exc
        if not fetch:
            self.stdout.write(f'would fetch {url} into {path.relative_to(root)}: --fetch fetches it')
            return
        parts = urlsplit(url)
        safe = urlunsplit(parts._replace(path=quote(parts.path)))
        try:
            data = fetch_service.get(safe, timeout=60)
        except (fetch_service.Refused, fetch_service.Outside) as exc:
            raise CommandError(str(exc)) from exc
        if not data.startswith(b'%PDF'):
            raise CommandError(f'{url}: not a PDF')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        doc = ingest_file(path, source=Source.ADALA, kind=DocumentKind.TEXT, language=language, url=url)
        self.stdout.write(f'{doc.path}: {doc.page_count} pages, sha256 {doc.sha256[:12]}…')
