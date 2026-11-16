"""The Bulletin's international conventions edition in Arabic (PL6 of the places review, 1 Nov 2026): since
decree 2.18.576 (2018) the dahirs that publish treaties appear there, not in the general edition. The SGG's list
(module 3110) is kept as fetched, with its hash; each issue the site does not hold is fetched once, checked to be a PDF,
written under CORPUS_DIR/issues/eci_ar/ECI_<n>_ar.pdf with its line in the folder's MANIFEST.tsv, then read end to end
by process_issue --edition conventions_ar (Haiku). Spending stops at --per-run dollars and at OCR_BUDGET_USD. Without
--fetch nothing is fetched; without --write nothing is read (reading is paid).

    fetch_conventions                                 # what it would fetch
    fetch_conventions --fetch                         # the files, no reading
    fetch_conventions --fetch --write --per-run 5     # fetch and read
    fetch_conventions --kept --write --per-run 5      # read the files held, from the list kept last time"""
import hashlib
import json
import time
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.sources.management.commands.fetch_bo_french import PAUSE, SITE, address, day, sgg_list
from apps.sources.models import Edition
from apps.sources.services import fetch as fetch_service

MODULE, TAB = 3110, 847


def index(via) -> bytes:
    return sgg_list(via, f'{SITE}/arabe/BulletinOfficiel.aspx', [(MODULE, TAB)])[0]


def read_issues() -> set[int]:
    """Conventions issues whose texts are loaded."""
    from apps.corpus.models import Text
    return set(Text.objects.filter(first_published_in__edition=Edition.CONVENTIONS_AR)
               .values_list('first_published_in__number', flat=True).distinct())


class Command(BaseCommand):
    help = "Fetch and read the Arabic conventions edition's issues the SGG lists and the site has not read."

    def add_arguments(self, parser):
        parser.add_argument('--list', action='store_true', dest='only_list',
                            help='say what is not read, fetch nothing (what it does without --fetch or --write)')
        parser.add_argument('--fetch', action='store_true', help='fetch the issues not held')
        parser.add_argument('--write', action='store_true', help='read the issues held with the model (paid)')
        parser.add_argument('--per-run', type=float, default=1.0, help='dollars at most this run')
        parser.add_argument('--kept', action='store_true',
                            help='work from the newest list kept under sources/sgg_bo, without asking the SGG again: '
                                 'read the issues held, fetch nothing')

    def handle(self, *args, only_list, fetch, write, per_run, kept, **opts):
        try:
            self._run(only_list or not (fetch or write), fetch and not kept, write, per_run, kept)
        except fetch_service.Refused as exc:
            raise CommandError(str(exc)) from exc

    def _run(self, only_list, fetch, write, per_run, kept):
        from apps.sources.services.ocr import OverBudget, allow_spending, spent

        root = Path(settings.CORPUS_DIR)
        via = fetch_service.opener()
        lists = root / 'sources' / 'sgg_bo'
        if kept:
            body = sorted(lists.glob(f'index_ar_{MODULE}_*.json'))[-1].read_bytes()
        else:
            body = index(via)
            stamp = datetime.now(UTC).strftime('%Y-%m-%dT%H%M%SZ')
            lists.mkdir(parents=True, exist_ok=True)
            (lists / f'index_ar_{MODULE}_{stamp}.json').write_bytes(body)
        rows = sorted(json.loads(body), key=lambda r: int(r['BoNum']))
        done = read_issues()
        todo = [r for r in rows if int(r['BoNum']) not in done]
        self.stdout.write(f'list: {len(rows)} issues (sha256 {hashlib.sha256(body).hexdigest()[:16]}…); not read: '
                          f'{", ".join(r["BoNum"] for r in todo) or "none"}')
        if only_list or not todo:
            return
        folder = root / 'issues' / 'eci_ar'
        folder.mkdir(parents=True, exist_ok=True)
        for r in todo:
            key, url = str(int(r['BoNum'])), address(r)
            path = folder / f'ECI_{key}_ar.pdf'
            if path.exists() or not fetch:
                continue
            time.sleep(PAUSE)
            try:
                data = fetch_service.get(url, via=via, timeout=300)
            except (urllib.error.URLError, ConnectionError, TimeoutError, ValueError) as exc:
                self.stderr.write(f'{key}: {exc} ({url})')
                continue
            if not data.startswith(b'%PDF'):
                self.stderr.write(f'{key}: not a PDF ({len(data)} bytes)')
                continue
            part = path.with_suffix('.part')
            part.write_bytes(data)
            part.replace(path)
            with open(folder / 'MANIFEST.tsv', 'a') as manifest:
                manifest.write('\t'.join([path.name, url, hashlib.sha256(data).hexdigest(), str(len(data)),
                                          datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'), key, day(r)]) + '\n')
            self.stdout.write(f'{key}: {len(data)} bytes')
        if not write:
            return
        allow_spending(log=self.stdout.write)
        settings.OCR_BUDGET_USD = min(float(settings.OCR_BUDGET_USD), float(spent()) + per_run)
        for r in todo:
            key = str(int(r['BoNum']))
            if not (folder / f'ECI_{key}_ar.pdf').exists():
                continue
            try:
                call_command('process_issue', key, date=day(r), url=address(r), edition=Edition.CONVENTIONS_AR, engine='haiku',
                             stdout=self.stdout, stderr=self.stderr)
            except OverBudget as exc:
                self.stdout.write(f'{key}: the budget is reached ({exc}); read again on a later run')
                break
        self.stdout.write(f'spent {spent():.4f} (ceiling {settings.OCR_BUDGET_USD:.2f})')
