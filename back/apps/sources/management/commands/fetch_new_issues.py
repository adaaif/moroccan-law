"""The Arabic general edition's new issues, each night (UX2 of the phone-test review, 30 Oct 2026), so the site
keeps up with the SGG's list without a person starting it. The SGG's Arabic list is kept as fetched,
with its hash; every issue it lists from 2019 on that the site does not hold is fetched once, checked to be a PDF, written
under CORPUS_DIR/issues/bo_ar/BO_<key>_ar.pdf and added to the folder's MANIFEST.tsv; then read end to end by
process_issue (Haiku), oldest first, its texts and those their changes reach indexed for search and the coverage line
refreshed. A long issue is read in as many batches as the night's ceiling holds, and one the budget stops half way is
read on from there on a later night (reports/fetch_new_issues.json keeps the ones begun and finished); one with a step
no night's ceiling could hold is said each night and passed, never the end of the issues after it; one the SGG lists
without a file (7410: no Arabic file at all) is tried three nights, then left and said each night. Spending stops at
--per-run dollars a night and at OCR_BUDGET_USD in all, whichever comes first. The site runs without a key: the
nightly unit gives this command its own (deploy/fetch.sh). Without --fetch it only asks the SGG for its list and says
what is new; without --write it reads nothing (reading is paid).

    fetch_new_issues                                # what a run would fetch
    fetch_new_issues --fetch                        # the files, read nothing
    fetch_new_issues --fetch --write --per-run 1    # the night's run"""
import hashlib
import http.client
import json
import re
import time
import traceback
import urllib.error
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.sources.management.commands.fetch_bo_french import PAUSE, SITE, address, day, sgg_list
from apps.sources.models import Edition, Issue
from apps.sources.services import fetch as fetch_service

PAGE_AR = f'{SITE}/arabe/BulletinOfficiel.aspx'
MODULE, TAB = 3111, 847         # the Arabic general edition's table (3110 is the conventions')
SINCE = date(2019, 1, 1)        # before, the archive's waves read the Bulletin
KEY = re.compile(r'\d+(-[a-z]+)?')
TRIES = 3                       # nights an issue whose file the SGG does not serve is tried before it is left


def key_of(row: dict) -> str:
    """The list's number as the site's key: «7555-bis». It writes four of 2013 the other way round («bis-6168»)."""
    n = row['BoNum'].strip().replace(' ', '').lower()
    m = re.fullmatch(r'bis-(\d+)', n)
    return f'{m.group(1)}-bis' if m else n


def missing(rows: list[dict], held: set[str], since: date = SINCE) -> list[dict]:
    """The issues the list names from `since` on that the site does not hold, oldest first."""
    out = [r for r in rows if KEY.fullmatch(key_of(r)) and key_of(r) not in held and date.fromisoformat(day(r)) >= since]
    return sorted(out, key=lambda r: (day(r), Issue.parse_key(key_of(r))))


def index_ar(via) -> bytes:
    """The Arabic list as the SGG's endpoint answers it (fetch_bo_french.sgg_list)."""
    return sgg_list(via, PAGE_AR, [(MODULE, TAB)])[0]


def index_texts(keys: list[str]) -> int:
    """The issues' texts, and those their changes reach, indexed for search; the coverage line counts them."""
    from apps.consolidation.models import Change
    from apps.corpus.models import Text
    from apps.search.services.index import rebuild
    from apps.sources.services import coverage

    issues = [i for i in Issue.objects.filter(edition=Edition.GENERAL_AR, number__in={Issue.parse_key(k)[0] for k in keys})
              if i.key in keys]
    loaded = list(Text.objects.filter(first_published_in__in=issues))
    reached = list(Text.objects.filter(akn_uri__in=Change.objects.filter(by_uri__in=[t.akn_uri for t in loaded])
                                       .values('text_uri')))
    coverage.refresh([i.key for i in issues])
    return rebuild(sorted({t.pk: t for t in [*loaded, *reached]}.values(), key=lambda t: t.pk))


class Command(BaseCommand):
    help = "Fetch and read the Arabic Bulletin's issues the SGG lists and the site does not hold yet."

    def add_arguments(self, parser):
        parser.add_argument('--list', action='store_true', dest='only_list',
                            help='say what is new, fetch nothing (what it does without --fetch)')
        parser.add_argument('--fetch', action='store_true', help='fetch the new issues')
        parser.add_argument('--write', action='store_true', help='read them with the model (paid) into the corpus')
        parser.add_argument('--per-run', type=float, default=1.0, help='dollars at most this run')
        parser.add_argument('--limit', type=int, default=6, help='issues at most this run')

    def handle(self, *args, only_list, fetch, write, per_run, limit, **opts):
        try:
            self._run(only_list or not (fetch or write), fetch, write, per_run, limit)
        except fetch_service.Refused as exc:
            raise CommandError(str(exc)) from exc

    def _run(self, only_list, fetch, write, per_run, limit):
        from apps.sources.services.ocr import OverBudget, allow_spending, spent

        root = Path(settings.CORPUS_DIR)
        via = fetch_service.opener()
        body = index_ar(via)
        stamp = datetime.now(UTC).strftime('%Y-%m-%dT%H%M%SZ')
        kept = root / 'sources' / 'sgg_bo'
        kept.mkdir(parents=True, exist_ok=True)
        (kept / f'index_ar_{MODULE}_{stamp}.json').write_bytes(body)
        rows = json.loads(body)
        state_path = root / 'reports' / 'fetch_new_issues.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else {'begun': {}, 'finished': {}}
        state.setdefault('failed', {})
        # When the SGG was last asked and the newest issue its list named: the library says it (W9 of
        # the library-search review), so a reader can tell a late site from a quiet Bulletin.
        listed = [r for r in rows if KEY.fullmatch(key_of(r))]
        newest = max(listed, key=lambda r: (day(r), Issue.parse_key(key_of(r))), default=None)
        state['asked'] = {'at': datetime.now(UTC).isoformat(timespec='seconds'), 'listed': len(listed),
                          'newest': key_of(newest) if newest else '', 'newest_date': day(newest) if newest else ''}
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=1))
        unfinished = set(state['begun']) - set(state['finished'])
        given_up = {k for k, n in state['failed'].items() if n >= TRIES}
        held = {f'{n}-{s}' if s else str(n) for n, s in
                Issue.objects.filter(edition=Edition.GENERAL_AR, date__gte=SINCE).values_list('number', 'suffix')}
        todo = [r for r in missing(rows, held - unfinished) if key_of(r) not in given_up]
        self.stdout.write(f'list: {len(rows)} issues (sha256 {hashlib.sha256(body).hexdigest()[:16]}…); {len(todo)} not '
                          f'held since {SINCE}' + (': ' + ', '.join(key_of(r) for r in todo[:20]) if todo else ''))
        if given_up:
            self.stdout.write(f'left after {TRIES} failed nights: {", ".join(sorted(given_up))}')
        if only_list or not todo:
            return
        if write:
            allow_spending(log=self.stdout.write)
            # Tonight's ceiling: OCR_BUDGET_USD in all, and no more than --per-run on top of what is spent now.
            settings.OCR_BUDGET_USD = min(float(settings.OCR_BUDGET_USD), float(spent()) + per_run)
        folder = root / 'issues' / 'bo_ar'
        folder.mkdir(parents=True, exist_ok=True)
        done = []
        for row in todo[:limit]:
            key, url = key_of(row), address(row)
            path = folder / f'BO_{key}_ar.pdf'
            if not path.exists() and not fetch:
                self.stdout.write(f'{key}: not held; --fetch fetches it')
                continue
            if not path.exists():
                time.sleep(PAUSE)
                try:
                    data = fetch_service.get(url, via=via, timeout=300)
                except (urllib.error.URLError, http.client.HTTPException, ValueError, TimeoutError, ConnectionError) as exc:
                    data, why = b'', str(exc)
                else:
                    why = '' if data.startswith(b'%PDF') else f'not a PDF ({len(data)} bytes)'
                if why:
                    state['failed'][key] = state['failed'].get(key, 0) + 1
                    state_path.write_text(json.dumps(state, indent=1))
                    self.stderr.write(f'{key}: {why} ({url}); night {state["failed"][key]} of {TRIES}')
                    continue
                part = path.with_suffix('.part')
                part.write_bytes(data)
                part.replace(path)
                with open(folder / 'MANIFEST.tsv', 'a') as manifest:
                    manifest.write('\t'.join([path.name, url, hashlib.sha256(data).hexdigest(), str(len(data)),
                                              datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'), key, day(row)]) + '\n')
            if not write:
                self.stdout.write(f'{key}: held, not read; --write reads it')
                continue
            state['begun'][key] = stamp
            state_path.write_text(json.dumps(state, indent=1))
            try:
                call_command('process_issue', key, date=day(row), url=url, engine='haiku',
                             stdout=self.stdout, stderr=self.stderr)
            except OverBudget as exc:
                if exc.worst > Decimal(str(per_run)):
                    # Never in one night at this ceiling: said plainly, and the issues after it are read.
                    state.setdefault('too_big', {})[key] = str(exc.worst)
                    state_path.write_text(json.dumps(state, indent=1))
                    self.stderr.write(f'{key}: one of its steps could cost ${exc.worst:.2f}, more than a night\'s '
                                      f'${per_run:.2f}: it needs a higher --per-run, by a person ({exc})')
                    continue
                self.stdout.write(f'{key}: the night\'s budget is reached ({exc}); read on from there on a later night')
                break
            except Exception:  # noqa: BLE001 — one issue that fails is said and passed, never the end of the night
                self.stderr.write(f'{key} failed:\n{traceback.format_exc()}')
                continue
            state['finished'][key] = datetime.now(UTC).strftime('%Y-%m-%dT%H%M%SZ')
            state_path.write_text(json.dumps(state, indent=1))
            done.append(key)
        if done:
            self.stdout.write(f'read {", ".join(done)}; {index_texts(done)} search entries written')
        if write:
            self.stdout.write(f'spent {spent():.4f} (ceiling tonight {settings.OCR_BUDGET_USD:.2f})')
