"""B9 of the search plan: Haiku reads the shelf's articles once, for the index (services/surrogates.py). Without
--write, the requests and the worst case only; with it, one batch inside the budget guard, the rows appended to
derived/search_surrogates.jsonl. An article already read with this prompt and version is skipped.

    manage.py draft_surrogates --limit 20 --write     (a trial)
    manage.py draft_surrogates --write                (the shelf)"""
from collections import Counter

from django.core.management.base import BaseCommand

from apps.corpus.services.llm import _worst_case, run_batch
from apps.search.models import SearchEntry
from apps.search.services import surrogates
from apps.search.services.search.bm25 import _shelf_paths
from apps.sources.services.ocr import allow_spending


class Command(BaseCommand):
    help = 'Draft the index material of the shelf\'s articles with Haiku (B9).'

    def add_arguments(self, parser):
        parser.add_argument('--text', action='append', help='a text\'s address instead of the shelf (repeatable)')
        parser.add_argument('--limit', type=int, default=0, help='articles at most (a trial)')
        parser.add_argument('--write', action='store_true')
        parser.add_argument('--show', type=int, default=0, help='print this many requests')

    def handle(self, *args, text, limit, write, show, **opts):
        texts = text or _shelf_paths()
        rows = surrogates.todo(text_paths=texts)
        if limit:
            rows = rows[:limit]
        names = {r.text_path: r.name.get('ar') or r.title[:160]
                 for r in SearchEntry.objects.filter(kind=SearchEntry.Kind.TEXT, text_path__in=texts).only('text_path', 'name', 'title')}
        reqs, meta = surrogates.requests(surrogates.groups(rows), names)
        self.stdout.write(f'{len(rows)} articles of {len({r.text_path for r in rows})} texts in {len(reqs)} requests; '
                          f'worst case ${_worst_case(reqs)}')
        for req in reqs[:show]:
            self.stdout.write('\n---\n' + req['params']['messages'][0]['content'][:2000])
        if not write or not reqs:
            return
        allow_spending(log=self.stdout.write)
        results = run_batch('search-surrogates', reqs, log=self.stdout.write)
        kept, dropped, missing = surrogates.rows_from(meta, results)
        surrogates.save(kept)
        roles = Counter(r['role'] for r in kept)
        self.stdout.write(f'{len(kept)} articles read, {sum(len(r["searches"]) for r in kept)} searches kept, {dropped} '
                          f'dropped by the rules, {missing} articles without an answer; roles: '
                          + ', '.join(f'{k} {v}' for k, v in roles.most_common()))
