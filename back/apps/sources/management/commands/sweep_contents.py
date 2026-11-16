"""Every text a span of years published, found by its contents page (A8 of the consumer plan): the BO issues the SGG
lists, each fetched once into the archive with --fetch (two seconds apart, under the project's own name, as
robots.txt allows: apps/sources/services/fetch.py; without it, only the issues held are swept), registered, and its
first pages — the cover and the contents — read with the model in batches that carry many issues at once (one batch an
issue took half an hour on 24 Oct 2026). Then a plain search of those pages names every line that holds one of the given law numbers or words.
Nothing else is read: an issue whose line matters is read whole afterwards with `process_issue` (its first pages are
kept). Reading is paid and needs --write. The sweep stops before a group whose ceiling estimate would take its spend
past `--ceiling`; the budget's own guard (OCR_BUDGET_USD) refuses any batch past the hard cap.

    sweep_contents sources/consumer/sgg_bo_ar_list_2026-10-24.json --from 2011 --to 2018 --ceiling 3.20 \\
        --report reports/sweep/consumer_2011_2018.json --fetch --write
"""
import json
import re
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.sources.models import Edition, Issue, OcrRun
from apps.sources.services import fetch as fetch_service
from apps.sources.services import issue as issue_service
from apps.sources.services.ocr import allow_spending, ocr_readings_batch, spent
from apps.sources.services.ocr import PROMPT_VERSION
from apps.sources.services.render import is_sideways, render_columns
from apps.sources.services.compare import fold

MODEL = 'claude-haiku-5-5'
# What one page costs at most (2012–2017 scans, page and columns: $0.00096–0.00121) and a group's model overhead.
PAGE_CEILING = Decimal('0.00121')

# The consumer's texts by number, and the words that name the rest (the legal interest rate, a product's safety).
NUMBERS = ['31.08', '24.09', '28.07', '13.83', '104.12', '06.99', '25.08', '77.15', '53.05', '09.08', '17.97',
           '2.12.503', '2.12.502', '2.14.652', '2.13.852', '2.10.473', '2.15.219', '2.16.174', '787.14', '1964.06']
WORDS = ['المستهلك', 'سعر الفائدة القانونية', 'الفوائد القانونية', 'السعر القانوني', 'سلامة المنتوجات', 'الزجر عن الغش',
         'زجر الغش', 'الأسعار', 'أسعار البيع', 'التخفيض', 'المسابقات الإشهارية', 'الضمان التعاقدي', 'العنونة', 'اللصيقة']


def _key(number: str) -> str:
    return number.strip().replace(' ', '-').lower()


KEY = re.compile(r'\d+(-[a-z]+)?')     # an issue's key, as fetch_new_issues reads it: the only names a file is given


def _day(raw: str) -> date:
    ms = int(re.search(r'-?\d+', raw).group())
    return (datetime(1970, 1, 1) + timedelta(milliseconds=ms)).date()


def matches(text: str) -> list[dict]:
    """The lines of a contents page that hold one of the numbers or words, each with what it holds."""
    out = []
    folded_words = [(w, fold(w)) for w in WORDS]
    for line in text.splitlines():
        if len(line.strip()) < 8:
            continue
        nums = [n for n in NUMBERS if re.search(rf'(?<![\d.]){re.escape(n)}(?![\d])', line)]
        f = fold(line)
        words = [w for w, fw in folded_words if fw in f]
        if nums or words:
            out.append({'line': line.strip()[:400], 'numbers': nums, 'words': words})
    return out


class Command(BaseCommand):
    help = 'Read the cover and contents of every BO issue of a span of years, and list the lines that matter.'

    def add_arguments(self, parser):
        parser.add_argument('listing', help="the SGG's list of issues (JSON), under CORPUS_DIR")
        parser.add_argument('--from', dest='first', type=int, required=True)
        parser.add_argument('--to', dest='last', type=int, required=True)
        parser.add_argument('--pages', type=int, default=3)
        parser.add_argument('--chunk', type=int, default=60, help='issues a batch carries')
        parser.add_argument('--ceiling', type=Decimal, required=True, help="the sweep's own spend, in dollars")
        parser.add_argument('--report', required=True, help='where the lines found go, under CORPUS_DIR')
        parser.add_argument('--fetch', action='store_true', help='fetch the issues not held (without it: only those held)')
        parser.add_argument('--write', action='store_true', help='read the pages with the model (paid)')

    def handle(self, *args, listing, first, last, pages, chunk, ceiling, report, fetch, write, **opts):
        root = Path(settings.CORPUS_DIR)
        rows = []
        for x in json.loads((root / listing).read_text()):
            day = _day(x['BoDate'])
            if first <= day.year <= last and KEY.fullmatch(_key(x['BoNum'])):
                rows.append({'key': _key(x['BoNum']), 'date': day, 'url': x['BoUrl'].strip()})
        rows.sort(key=lambda r: (r['date'], r['key']))
        archive = root / 'issues' / 'bo_ar'
        log = self.stdout.write
        log(f'{len(rows)} issues {first}–{last}')
        fetched = 0
        for r in rows:
            path = archive / f'BO_{r["key"]}_ar.pdf'
            r['path'] = path
            if path.exists():
                continue
            if not fetch:
                r['missing'] = True
                continue
            parts = urlsplit(r['url'])
            try:
                data = fetch_service.get(urlunsplit(parts._replace(path=quote(parts.path))), timeout=120)
            except fetch_service.Refused as exc:          # the site said no: the sweep stops, nothing is tried round it
                raise CommandError(str(exc)) from exc
            except Exception as exc:                      # noqa: BLE001 — an issue the SGG does not serve: said, and passed
                log(f'  {r["key"]}: not fetched ({exc})')
                r['missing'] = True
                time.sleep(2.1)
                continue
            if data.startswith(b'%PDF'):
                path.write_bytes(data)
                fetched += 1
            else:
                r['missing'] = True
            time.sleep(2.1)
        log(f'fetched {fetched}, missing {sum(1 for r in rows if r.get("missing"))}'
            + ('' if fetch else ' (not held; --fetch fetches them)'))
        if not write:
            log('nothing read: --write reads the first pages (paid)')
            return
        allow_spending(log=self.stdout.write)
        out_path = root / report
        out_path.parent.mkdir(parents=True, exist_ok=True)
        found = json.loads(out_path.read_text()) if out_path.exists() else {}
        start = spent()
        todo = [r for r in rows if not r.get('missing') and r['path'].exists()]
        for i in range(0, len(todo), chunk):
            group = todo[i:i + chunk]
            issues, first_pages = [], []
            for r in group:
                number, suffix = Issue.parse_key(r['key'])
                issue = Issue.objects.filter(edition=Edition.GENERAL_AR, number=number, suffix=suffix).select_related('document').first()
                if issue is None:
                    issue = issue_service.register(r['path'], edition=Edition.GENERAL_AR, number=number, suffix=suffix,
                                                   day=r['date'], url=r['url'])
                issues.append((r, issue))
                first_pages += list(issue.document.pages.order_by('index')[:pages])
            unread = [p for p in first_pages if not OcrRun.objects.filter(page=p, engine=MODEL, prompt_version=PROMPT_VERSION).exists()]
            estimate = PAGE_CEILING * len(unread) + Decimal('0.01')
            if spent() - start + estimate > ceiling:
                log(f'STOP before issues {group[0]["key"]}…{group[-1]["key"]}: the sweep has spent ${spent() - start:.4f}, '
                    f'these {len(unread)} pages could take it past ${ceiling}')
                break
            if unread:
                sideways = [p for p in unread if p.layer_letters >= 200 and is_sideways(p)]
                split = [p for p in unread if render_columns(p)]
                log(f'issues {group[0]["key"]}…{group[-1]["key"]}: {len(unread)} pages ({len(split)} in two columns)')
                ocr_readings_batch(unread, sideways, split, MODEL, log=log)
                issue_service.keep_best(first_pages, MODEL)
            for r, issue in issues:
                lines = []
                for p in issue.document.pages.order_by('index')[:pages]:
                    p.refresh_from_db()
                    lines += [{**m, 'page': p.index} for m in matches(p.text or '')]
                found[r['key']] = {'date': r['date'].isoformat(), 'url': r['url'], 'lines': lines}
            out_path.write_text(json.dumps(found, ensure_ascii=False, indent=1))
            log(f'  spent by the sweep: ${spent() - start:.4f}; issues with lines: {sum(1 for v in found.values() if v["lines"])}')
        log(f'report: {out_path} ({len(found)} issues)')
