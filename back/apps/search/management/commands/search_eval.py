"""Measure the search on a question set (default: the seed set) and say which questions it missed.

`--all` runs every tuning set; `--split tune|dev` keeps one split of them (B1 of the search plan); `--by register,intent`
adds the totals by segment. `--test` runs the test set (goldset/test.json): only its totals are shown, never a
question, so nothing gets tuned on it."""
import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.search.services import judge
from apps.search.services.goldset import DIR, SEED, TEST, by_segment, evaluate, sets


class Command(BaseCommand):
    help = 'Measure the search on a question set.'

    def add_arguments(self, parser):
        parser.add_argument('--set', default=str(SEED), help='a set\'s name (road) or a JSON file of {"questions": [{q, expect}]}')
        parser.add_argument('--all', action='store_true', help='every tuning set')
        parser.add_argument('--split', choices=['tune', 'dev'], help='only this split of the tuning sets')
        parser.add_argument('--test', action='store_true', help='the test set, totals only')
        parser.add_argument('--by', default='', help='segments to total by, comma-separated: register, intent, set, split')
        parser.add_argument('--min', type=float, default=0.0, help='fail below this share (0.8 before launch)')

    def handle(self, *args, set, all, split, test, by, min, **opts):
        if test:
            paths = [TEST]
            if not TEST.exists():
                raise CommandError('No test set yet: draft_test_questions writes it.')
        elif all:
            paths = sets()
        else:
            named = DIR / f'{set}.json'
            paths = [named if named.exists() else Path(set)]
            if not paths[0].is_file():
                # One tuning set is kept out of the public tree (its questions' sources were not recorded).
                raise CommandError(f'No set named {set} here: the sets are {", ".join(p.stem for p in sets())}.')
        rows = []
        for path in paths:
            result = evaluate(path, split=None if test else split)
            for r in result['rows']:
                r['set'] = path.stem
            rows += result['rows']
        if not test:
            for r in rows:
                mark = 'MISS' if not r['hit'] else 'ok d' if r.get('by_door') else 'ok 1' if r['first'] else 'ok  '
                self.stdout.write(f"{mark} {r['q']}  →  {r['expect']}  ({r['understood_as']}, {r['register']}, {r['intent']})"
                                  f"{'  ' + r['note'] if r.get('note') else ''}")
        hits, firsts, doors = (sum(r[k] for r in rows) for k in ('hit', 'first', 'by_door'))
        n = len(rows) or 1
        self.stdout.write(f"\n{hits} of {len(rows)} in the top 3: {hits / n:.0%}; {firsts} first; "
                          f"{doors} of them by a door the question names")
        for key in [k.strip() for k in by.split(',') if k.strip()]:
            self.stdout.write(f'\nby {key}:')
            for seg, s in by_segment(rows, key).items():
                q = s['questions']
                self.stdout.write(f"  {seg:14} {s['hits']:4} of {q:4} ({s['hits'] / q:.0%}), {s['first']} first, {s['by_door']} by a door")
        # Graded measures (B2), where the judge has graded this search's answers.
        known = judge.load()
        graded = judge.measure(rows, known) if known else None
        if graded and graded['questions']:
            self.stdout.write(f"\ngraded ({graded['questions']} questions): nDCG@10 {graded['ndcg10']}, MRR {graded['mrr']}, "
                              f"recall@20 {graded['recall20']}")
            for key in [k.strip() for k in by.split(',') if k.strip()]:
                segs = {}
                for r in rows:
                    segs.setdefault(r.get(key) or '-', []).append(r)
                for seg, part in sorted(segs.items()):
                    m = judge.measure(part, known)
                    if m['questions']:
                        self.stdout.write(f"  {key} {seg:14} nDCG@10 {m['ndcg10']}, MRR {m['mrr']}, recall@20 {m['recall20']} ({m['questions']})")
        name = 'test' if test else 'all' if all else paths[0].stem
        out = Path(settings.CORPUS_DIR) / 'reports' / f'search_eval_{name}{"_" + split if split else ""}_{date.today()}.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        # The test set's file keeps its totals only.
        kept = {'questions': len(rows), 'hits': hits, 'first': firsts, 'by_door': doors, 'graded': graded,
                'segments': {k: by_segment(rows, k) for k in ('register', 'intent', 'set', 'split')}}
        if not test:
            kept['rows'] = rows
        out.write_text(json.dumps(kept, ensure_ascii=False, indent=1))
        if hits / n < min:
            raise CommandError(f"{hits / n:.0%} is under the bar of {min:.0%}")
