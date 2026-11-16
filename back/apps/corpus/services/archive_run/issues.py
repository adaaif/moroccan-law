"""The plan's issues: `archive register` (each one's PDF linked and registered), `archive queue` (the issues the
coverage line counts) and `archive order` (the order they are read in, Z7 and H4)."""
import json
import re
import traceback
from collections import Counter
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError

from apps.corpus.services.archive_run.common import issue_of, plan, workdir
from apps.sources.models import Edition, Issue
from apps.sources.services import archive, witness
from apps.sources.services import issue as issue_service
from apps.sources.services.archive import LEGISLATION


_NUMBER = re.compile(r'\d+(?:[.\-/]\d+)+')


class Issues:
    """The plan's issues registered, queued and put in reading order."""

    def register(self, pdfs: str | None) -> None:
        if not pdfs:
            raise CommandError('--pdfs is needed')
        folder = Path(settings.CORPUS_DIR) / 'issues' / 'bo_ar'
        folder.mkdir(parents=True, exist_ok=True)
        have = set(Issue.objects.filter(edition=Edition.GENERAL_AR).values_list('number', 'suffix'))
        made = 0
        for item in plan()['issues']:
            number, suffix = Issue.parse_key(item['key'])
            if (number, suffix) in have:
                continue
            source = Path(pdfs) / item['path']
            if not source.exists():
                self.log(f'{item["key"]}: no PDF yet at {source}')
                continue
            link = folder / f'BO_{item["key"]}_ar.pdf'
            if not link.exists():
                link.symlink_to(source)
            try:
                issue = issue_service.register(link, edition=Edition.GENERAL_AR, number=number, suffix=suffix,
                                               day=date.fromisoformat(item['date']), url=item['url'])
            except Exception:     # noqa: BLE001 — a file pdfium cannot open (28 Oct 2026): listed, fetched again from the SGG later
                archive.mark('register', item['key'], 'error', traceback.format_exc())
                self.log(f'{item["key"]}: not registered, see state/register/{item["key"]}.error')
                continue
            doc = issue.document
            if not doc.pages.exists():      # a file whose pages failed to be read last time (a NUL in a layer)
                from apps.sources.services.ingest import read_pages
                read_pages(doc)
            doc.meta = {**doc.meta, 'archive': item['path']}
            doc.save(update_fields=['meta'])
            made += 1
            if made % 100 == 0:
                self.log(f'{made} issues registered')
        self.log(f'registered {made}; {Issue.objects.filter(edition=Edition.GENERAL_AR).count()} in all')

    def queue(self) -> None:
        """The issues the coverage line counts, oldest first: those of the plan from its `coverage_from` (1956 until
        the official section before it is read, H10 of the Bulletin-from-No.-1 review)."""
        from apps.sources.services import coverage
        path = Path(settings.CORPUS_DIR) / 'reports' / 'runs' / coverage.ARCHIVE_QUEUE
        path.parent.mkdir(parents=True, exist_ok=True)
        p = plan()
        first = p.get('coverage_from') or coverage.ARCHIVE_FROM.isoformat()
        issues = sorted((i for i in p['issues'] if i['date'] >= first), key=lambda i: (i['date'], Issue.parse_key(i['key'])))
        path.write_text(''.join(f'{i["key"]} {i["date"]} archive\n' for i in issues))
        self.log(f'{len(issues)} issues in {path}')

    def order(self, missing_path: str | None, cited_path: str | None = None) -> None:
        """Z7: the issues holding the texts the site cites and lacks first, most cited first; then those with a law,
        dahir or decree-law, then decrees, then the rest; newest first within each (C3). Before 1956 (H4 of
        the Bulletin-from-No.-1 review) a text is cited by its date, not a number: an issue printing, within 180 days after it, a
        date the site cites a dahir or an order by is cited too."""
        from apps.corpus.services.issue_structure import normalize_number
        from apps.corpus.services.works import address

        missing = json.loads(Path(missing_path).read_text()) if missing_path else {}
        by_date = self.cited_by_date(json.loads(Path(cited_path).read_text())) if cited_path else {}
        # An address from a number as the loader makes one («1.81.254» → «1-81-254»): built from the printed form,
        # 4 issues matched where 1,408 hold a text the site cites (28 Oct 2026).
        kinds = ('dahir', 'law', 'organic_law', 'decree_law', 'decree', 'order')
        rows = []
        for item in plan()['issues']:
            path = workdir(item['key']) / 'toc.json'
            toc = json.loads(path.read_text()) if path.exists() else []
            cited = 0
            for e in toc:
                for number in _NUMBER.findall(f'{e["number_as_printed"]} {e["title"]}'):
                    for kind in kinds:
                        cited = max(cited, missing.get(address(kind, normalize_number(number)), 0))
            cited = max(cited, by_date.get(item['key'], 0))
            legislation = sum(1 for e in toc if e['type'] in LEGISLATION)
            decrees = sum(1 for e in toc if e['type'] == 'decree')
            tier = 0 if cited else 1 if legislation else 2 if decrees else 3
            rows.append((tier, -cited, item['date']) + (item['key'],))
        rows.sort(key=lambda r: (r[0], r[1], [-ord(c) for c in r[2]]))
        keys = [r[3] for r in rows]
        (archive.root() / 'order.json').write_text(json.dumps(keys))
        by_key = {i['key']: i['path'] for i in plan()['issues']}
        (archive.root() / 'tess_order.txt').write_text(''.join(by_key[k] + '\n' for k in keys))
        tiers = Counter(r[0] for r in rows)
        self.log(f'order: {len(keys)} issues; cited {tiers[0]}, legislation {tiers[1]}, decrees {tiers[2]}, '
                 f'the rest {tiers[3]}')

    def cited_by_date(self, cited: dict[str, int]) -> dict[str, int]:
        """{issue key: citations} for the issues before 1956 whose own pages, as Tesseract read them, print a date
        the site cites a dahir or an order by («الموافق 12 غشت سنة 1913»), in the 180 days before the issue."""
        from datetime import timedelta
        from apps.corpus.services.issue_structure import _MONTHS
        names = {}
        for name, month in _MONTHS.items():
            names.setdefault(month, []).append(name)
        dates = sorted((date.fromisoformat(k.split(':', 1)[1]), n) for k, n in cited.items())
        out = {}
        for item in plan()['issues']:
            day = date.fromisoformat(item['date'])
            near = [(d, n) for d, n in dates if day - timedelta(days=180) <= d <= day]
            issue = issue_of(item['key']) if near and day.year < 1956 else None
            if issue is None or not witness.has(issue.document):
                continue
            text = ' '.join(line[4] for page in issue.document.pages.all() if (seen := witness.of(page))
                            for line in seen.get('lines', []))
            found = sum(n for d, n in near if re.search(
                rf'(?<!\d){d.day}\s+(?:{"|".join(names[d.month])})\s+(?:سنة\s+)?{d.year}', text))
            if found:
                out[item['key']] = found
        self.log(f'{len(out)} issues before 1956 print a date the site cites a text by')
        return out
