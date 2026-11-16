"""B1 of the search plan: draft the test set with Haiku. Without --write, the sample and the worst case only; with
it, one batch inside the budget guard, and goldset/test.json written (new questions only, marked owner-provisional).

    manage.py draft_test_questions --n 1300 --seed 26 --write"""
import json
from collections import Counter
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.corpus.services.llm import _worst_case, run_batch
from apps.search.services import testset
from apps.search.services.goldset import TEST
from apps.sources.services.ocr import allow_spending


class Command(BaseCommand):
    help = 'Draft the search test set with Haiku (B1).'

    def add_arguments(self, parser):
        parser.add_argument('--n', type=int, default=1300, help='articles to draw (about a quarter fall out)')
        parser.add_argument('--seed', type=int, default=26)
        parser.add_argument('--write', action='store_true', help='send the batch and write goldset/test.json')
        parser.add_argument('--show', type=int, default=0, help='print this many prompts')

    def handle(self, *args, n, seed, write, show, **opts):
        items = testset.sample(n, seed)
        reqs = testset.requests(items)
        self.stdout.write(f"{len(items)} articles: " + ', '.join(f'{k} {v}' for k, v in Counter(i['text'].type for i in items).most_common())
                          + '\nregisters: ' + ', '.join(f'{k} {v}' for k, v in Counter(i['register'] for i in items).items())
                          + f'\nworst case ${_worst_case(reqs)} (every request at its token ceiling)')
        for item, req in list(zip(items, reqs))[:show]:
            self.stdout.write(f"\n--- {item['id']} {item['path']}\n{req['params']['messages'][0]['content'][:1200]}")
        if not write:
            return
        if TEST.exists():
            raise CommandError(f'{TEST.name} exists: the test set is drafted once (move it aside to draft again).')
        allow_spending(log=self.stdout.write)
        results = run_batch('search-testset', reqs, log=self.stdout.write)
        questions, dropped = testset.questions(items, results)
        TEST.write_text(json.dumps({
            'about': ('Test questions (B1 of the search plan, 24 Oct 2026): written by Haiku 5.5 from articles drawn at random '
                      f'from the whole corpus (seed {seed}; half laws and codes, three in ten decrees, two in ten orders and '
                      'decisions), one a register in turn: MSA, Darija in Arabic letters, Darija in Latin letters, French, '
                      'English, a professional\'s query. New questions only: never tuned on, only their totals are shown '
                      '(search_eval --test). «checked: owner-provisional»: the editors\' provisional check until lawyers '
                      're-verify them.'),
            'date': date.today().isoformat(), 'questions': questions}, ensure_ascii=False, indent=1))
        self.stdout.write(f'{len(questions)} questions written to {TEST}; fell out: {dropped}')
