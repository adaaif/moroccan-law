"""B2 of the search plan: Haiku grades what today's search shows for each question (and the articles the sets expect),
0 to 3, kept in CORPUS_DIR/derived/search_grades.jsonl; then nDCG@10, MRR and recall@20, and the judge's provisional
checks. Without --write, the pairs and the worst case only.

    manage.py grade_answers --tuning --negatives 100 --write
    manage.py grade_answers --test --write"""
from django.core.management.base import BaseCommand, CommandError

from apps.corpus.services.llm import _worst_case, run_batch
from apps.search.services import judge
from apps.search.services.goldset import TEST, evaluate, sets
from apps.sources.services.ocr import allow_spending


class Command(BaseCommand):
    help = 'Grade search answers with Haiku (B2).'

    def add_arguments(self, parser):
        parser.add_argument('--tuning', action='store_true', help='the tuning sets (tune and dev)')
        parser.add_argument('--test', action='store_true', help='the test set (its totals only)')
        parser.add_argument('--negatives', type=int, default=0, help='questions that get two unrelated articles too')
        parser.add_argument('--write', action='store_true', help='send the batch and keep the grades')

    def handle(self, *args, tuning, test, negatives, write, **opts):
        if not (tuning or test):
            raise CommandError('--tuning or --test')
        paths = ([TEST] if test else []) + (sets() if tuning else [])
        rows = []
        for path in paths:
            for r in evaluate(path)['rows']:
                r['set'] = path.stem
                rows.append(r)
        known = judge.load()
        extra = judge.negatives(rows, negatives) if negatives and write else {}
        pool = judge.pools(rows, extra)
        reqs, meta = judge.requests(pool, known)
        pairs = sum(len(v[1]) for v in meta.values())
        self.stdout.write(f'{len(rows)} questions, {pairs} pairs to grade in {len(reqs)} requests; '
                          f'worst case ${_worst_case(reqs) if reqs else 0}')
        if write and reqs:
            allow_spending(log=self.stdout.write)
            results = run_batch('search-grades', reqs, log=self.stdout.write)
            graded = judge.collect(results, meta)
            judge.save(graded)
            self.stdout.write(f'{len(graded)} of {pairs} pairs graded')
            known = judge.load()
        self.stdout.write(f'graded measures: {judge.measure(rows, known)}')
        self.stdout.write(f'judge checks (provisional, until lawyers calibrate it): {judge.checks(rows, known)}')
