"""The French edition of the Bulletin Officiel, every issue the SGG lists (25 Oct 2026: kept beside the Arabic). The
SGG's page fills its table from an endpoint it asks with the page's own token; the list it returns (4,897
issues, 1912 → today, and 21 of the international conventions' edition) is kept as fetched, with its hash. Then each
issue is fetched once, politely (one at a time, two seconds apart, under the project's own name, as robots.txt
allows: apps/sources/services/fetch.py), checked to be a PDF, written whole or not at all under
CORPUS_DIR/issues/bo_fr/BO_<n>_fr.pdf (the conventions' under issues/eci_fr/), and added to the folder's MANIFEST.tsv:
file, address, sha256, bytes, fetched at, number, date. No database: `process_issue --edition translation_fr --date …
--url …` registers an issue from it when its turn comes. Without --fetch it only says what a run would fetch; a rerun
fetches only what is missing.

    fetch_bo_french                       # the list, and what --fetch would fetch
    fetch_bo_french --fetch --limit 20    # a trial
    fetch_bo_french --fetch --before 2019 # the issues dated before 2019"""
import hashlib
import json
import re
import time
import http.client
import urllib.error
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.sources.services import fetch as fetch_service

SITE = 'https://www.sgg.gov.ma'
PAGE = f'{SITE}/BulletinOfficiel.aspx'
ENDPOINT = f'{SITE}/DesktopModules/MVC/TableListBO/BO/AjaxMethod'
# The page's two tables: the French edition, and the international conventions' edition in French.
TABLES = {'bo_fr': (2873, 775, 'BO_{n}_fr.pdf'), 'eci_fr': (3076, 797, 'ECI_{n}_fr.pdf')}
PAUSE = 2.0


def sgg_list(via, page: str, tables: list[tuple[int, int]]) -> list[bytes]:
    """The lists the SGG's Bulletin page shows, as its endpoint answers them: the page's own script asks the endpoint
    for each table with the page's token and cookie, and so do we, under our own name, once a run."""
    body = fetch_service.get(page, via=via, timeout=60)
    token = re.search(rb'name="__RequestVerificationToken"[^>]*value="([^"]+)"', body)
    return [fetch_service.get(ENDPOINT, via=via, timeout=120, headers={
        'ModuleId': str(module), 'TabId': str(tab), 'X-Requested-With': 'XMLHttpRequest',
        'RequestVerificationToken': token.group(1).decode() if token else ''}) for module, tab in tables]


def index(via) -> dict[str, list[dict]]:
    """{table: rows as the endpoint gives them}."""
    bodies = sgg_list(via, PAGE, [(module, tab) for module, tab, _ in TABLES.values()])
    return {table: json.loads(body) for table, body in zip(TABLES, bodies)}


def day(row: dict) -> str:
    """«/Date(-1804032000000)/» as 1912-11-01."""
    ms = int(re.search(r'-?\d+', row['BoDate']).group())
    return (datetime(1970, 1, 1) + timedelta(milliseconds=ms)).date().isoformat()


def address(row: dict) -> str:
    """The issue's address, escaped: the list writes some with a space («bo_5722_ fr.pdf»)."""
    url = row['BoUrl'].strip()
    url = url if url.startswith('http') else SITE + '/' + url.lstrip('/')
    return urllib.parse.quote(url, safe=':/?=&%')


class Command(BaseCommand):
    help = "Fetch the SGG's French edition of the Bulletin Officiel, with a manifest of hashes."

    def add_arguments(self, parser):
        parser.add_argument('--fetch', action='store_true', help='fetch the issues missing (without it: say which)')
        parser.add_argument('--before', type=int, help='only the issues dated before this year')
        parser.add_argument('--limit', type=int, default=0, help='issues at most (a trial)')
        parser.add_argument('--pause', type=float, default=PAUSE)

    def handle(self, *args, fetch: bool, before, limit, pause, **opts):
        try:
            self._run(fetch, before, limit, pause)
        except fetch_service.Refused as exc:
            raise CommandError(str(exc)) from exc

    def _run(self, fetch, before, limit, pause):
        root = Path(settings.CORPUS_DIR)
        via = fetch_service.opener()
        tables = index(via)
        stamp = datetime.now(UTC).strftime('%Y-%m-%dT%H%M%SZ')
        kept = root / 'sources' / 'sgg_bo'
        kept.mkdir(parents=True, exist_ok=True)
        body = json.dumps(tables, ensure_ascii=False, indent=1).encode()
        (kept / f'index_fr_{stamp}.json').write_bytes(body)
        self.stdout.write(f'index: {", ".join(f"{t} {len(r)}" for t, r in tables.items())} issues; kept as '
                          f'index_fr_{stamp}.json (sha256 {hashlib.sha256(body).hexdigest()[:16]}…)')
        todo = []
        for table, rows in tables.items():
            folder = root / 'issues' / table
            folder.mkdir(parents=True, exist_ok=True)
            for row in sorted(rows, key=day):
                if before and int(day(row)[:4]) >= before:
                    continue
                try:
                    path = folder / fetch_service.safe_name(TABLES[table][2].format(n=row['BoNum'].strip()))
                except fetch_service.Outside as exc:          # a number the list writes oddly: said, left
                    self.stderr.write(str(exc))
                    continue
                if not path.exists():
                    todo.append((folder, path, row))
        self.stdout.write(f'{len(todo)} issues to fetch' + (f' (dated before {before})' if before else ''))
        if not fetch:
            return
        if limit:
            todo = todo[:limit]
        fetched = failed = 0
        started = time.time()
        for k, (folder, path, row) in enumerate(todo, 1):
            url = address(row)
            time.sleep(pause)
            try:
                data = fetch_service.get(url, via=via, timeout=300)
            except (urllib.error.URLError, http.client.HTTPException, ValueError, TimeoutError, ConnectionError) as exc:
                # One issue the list names badly is said and left for a rerun, never the end of the run.
                failed += 1
                self.stderr.write(f'{path.name}: {exc} ({url})')
                continue
            if not data.startswith(b'%PDF'):
                failed += 1
                self.stderr.write(f'{path.name}: not a PDF ({len(data)} bytes, {url})')
                continue
            tmp = path.with_suffix('.part')
            tmp.write_bytes(data)
            tmp.replace(path)
            with open(folder / 'MANIFEST.tsv', 'a') as manifest:
                manifest.write('\t'.join([path.name, url, hashlib.sha256(data).hexdigest(), str(len(data)),
                                          datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                          row['BoNum'].strip(), day(row)]) + '\n')
            fetched += 1
            if k % 50 == 0 or k == len(todo):
                self.stdout.write(f'{k} of {len(todo)}: {fetched} fetched, {failed} failed, '
                                  f'{(time.time() - started) / k:.1f} s an issue')
        self.stdout.write(f'done: {fetched} fetched, {failed} failed of {len(todo)}')
