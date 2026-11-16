"""Measures the check before publishing on its test set (29 Oct 2026): posts written to break each rule
(checkset/written.py), posts that must pass though they look close, and the demo's own words, which must pass. Paid:
each item is one request to CHECK_MODEL; --max-usd stops it (one dollar by default). Writes checkset/results/
<day>-<prompt version>.json with every answer, and says:

- the passes held or returned (wrongly stopped), and which;
- the breaks published (missed), by rule, and how many were caught under their own rule;
- what it cost, and how long the model took (median, slowest).

    python manage.py check_eval                        # the items and the worst case, nothing sent
    python manage.py check_eval --write                # everything
    python manage.py check_eval --only breaks --write  # one part: breaks, passes, demo
"""
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.discussion.management.commands import demo_content as demo
from apps.discussion.models import Check
from apps.discussion.services import check, places
from apps.sources.services import ocr

try:
    # The written posts are a private evaluation set: the public tree has the demo's words alone.
    from apps.discussion.checkset import written
except ImportError:
    written = None
RESULTS = Path(__file__).resolve().parents[2] / 'checkset' / 'results'
NO_SET = ('the test set (apps/discussion/checkset/) is not in this copy: it is kept in a private evaluation set. '
          '`--only demo` measures the check on the demo\'s own words.')


def items(only: str = '') -> list[dict]:
    if written is None and only != 'demo':
        raise CommandError(NO_SET)
    names = {p.slug: p.name for p in places.all_places()}
    out = []
    for rule, rows in (written.BREAKS.items() if written else ()):
        for i, (place, title, body) in enumerate(rows):
            out.append({'id': f'{rule}-{i + 1:02d}', 'part': 'breaks', 'place': names[place], 'title': title,
                        'body': body, 'expect': rule})
    for i, (place, title, body) in enumerate(written.PASSES if written else ()):
        out.append({'id': f'pass-{i + 1:02d}', 'part': 'passes', 'place': names[place], 'title': title, 'body': body,
                    'expect': 'publish'})
    family = names['family']
    texts = (demo.QUESTIONS_49 + demo.EXPLANATIONS_49 + demo.EXPERIENCES_49
             + [x for group in demo.OPINIONS_49.values() for x in group]
             + [x for s in demo.SMALL.values() for x in s['questions'] + s['explanations'] + s['opinions']])
    for i, body in enumerate(dict.fromkeys(texts)):
        out.append({'id': f'demo-{i + 1:03d}', 'part': 'demo', 'place': family, 'title': '', 'body': body,
                    'expect': 'publish'})
    replies = demo.REPLY_AGREE + demo.REPLY_DISAGREE + demo.REPLY_ASK + demo.REPLY_THANKS
    for i, body in enumerate(dict.fromkeys(replies)):
        out.append({'id': f'reply-{i + 1:02d}', 'part': 'demo', 'place': family, 'title': '', 'body': body,
                    'parent': ('الكد والسعاية', demo.QUESTIONS_49[i % len(demo.QUESTIONS_49)]), 'expect': 'publish'})
    return [x for x in out if not only or x['part'] == only]


def ask(text: str) -> check.Asked:
    """One look by the model, inside the shared budget like every paid request: its worst case held while it is out,
    its cost in the ledger when it answers. A look the budget refuses is counted as unavailable («budget»)."""
    worst = ocr.call_worst(settings.CHECK_MODEL, len(check.PROMPT) + len(text), 256)
    try:
        with ocr.reserve('check-eval', worst):
            found = check.ask(text)
            if found.tokens_in or found.tokens_out:
                ocr.record_call('check-eval', settings.CHECK_MODEL, cost=found.cost, input_tokens=found.tokens_in,
                                output_tokens=found.tokens_out)
    except ocr.OverBudget:
        return check.Asked(Check.Outcome.UNAVAILABLE, '', 'budget')
    return found


def _text(item: dict) -> str:
    class Parent:
        title, body = item['parent'] if item.get('parent') else ('', '')
    return check.message(place=item['place'], title=item['title'], body=item['body'],
                         parent=Parent if item.get('parent') else None)


class Command(BaseCommand):
    help = 'Measure the check before publishing on its test set (paid).'

    def add_arguments(self, parser):
        parser.add_argument('--only', choices=['breaks', 'passes', 'demo'], default='')
        parser.add_argument('--max-usd', type=float, default=1.0)
        parser.add_argument('--workers', type=int, default=4)
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')

    def handle(self, *args, only='', max_usd=1.0, workers=4, write=False, **options):
        todo = items(only)
        if not write:
            self.stdout.write(f'{len(todo)} items, one request each to {settings.CHECK_MODEL}: --write sends them '
                              f'(at most ${max_usd})')
            return
        if not settings.ANTHROPIC_API_KEY:
            raise CommandError('Set ANTHROPIC_API_KEY.')
        ocr.allow_spending(log=self.stdout.write)
        spent, answers = Decimal('0'), {}
        cap = Decimal(str(max_usd))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            running = {}
            queue = iter(todo)
            for item in queue:
                if spent >= cap:
                    break
                running[pool.submit(ask, _text(item))] = item
                if len(running) >= workers * 2:
                    done = next(as_completed(running))
                    found, it = done.result(), running.pop(done)
                    spent += found.cost
                    answers[it['id']] = found
            for done in as_completed(running):
                found, it = done.result(), running[done]
                spent += found.cost
                answers[it['id']] = found
        rows = []
        for it in todo:
            if it['id'] in answers:
                a = answers[it['id']]
                rows.append({**{k: v for k, v in it.items() if k != 'parent'}, 'outcome': a.outcome, 'rule': a.rule,
                             'failure': a.failure, 'ms': a.ms, 'cost': str(a.cost)})
        summary = self.summarise(rows, spent)
        RESULTS.mkdir(parents=True, exist_ok=True)
        out = RESULTS / f'{timezone.localdate()}-{check.PROMPT_VERSION}{"-" + only if only else ""}.json'
        out.write_text(json.dumps({'model': settings.CHECK_MODEL, 'prompt_version': check.PROMPT_VERSION,
                                   'summary': summary, 'rows': rows}, ensure_ascii=False, indent=1) + '\n')
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=1))
        self.stdout.write(f'written to {out}')

    @staticmethod
    def summarise(rows: list[dict], spent: Decimal) -> dict:
        passes = [r for r in rows if r['expect'] == 'publish']
        breaks = [r for r in rows if r['expect'] != 'publish']
        stopped = [r for r in passes if r['outcome'] != 'publish']
        by_rule = {}
        for rule in sorted({r['expect'] for r in breaks}):
            mine = [r for r in breaks if r['expect'] == rule]
            by_rule[rule] = {'n': len(mine), 'caught': sum(r['outcome'] != 'publish' for r in mine),
                             'own_rule': sum(r['rule'] == rule for r in mine),
                             'held': sum(r['outcome'] == 'hold' for r in mine),
                             'missed': [r['id'] for r in mine if r['outcome'] == 'publish']}
        ms = [r['ms'] for r in rows if r['ms']]
        return {
            'items': len(rows),
            'passes': {'n': len(passes), 'stopped': len(stopped),
                       'stopped_rate': round(len(stopped) / len(passes), 3) if passes else None,
                       'which': [(r['id'], r['outcome'], r['rule']) for r in stopped]},
            'breaks': {'n': len(breaks), 'caught': sum(v['caught'] for v in by_rule.values()),
                       'caught_rate': round(sum(v['caught'] for v in by_rule.values()) / len(breaks), 3) if breaks else None,
                       'by_rule': by_rule},
            'unavailable': sum(r['outcome'] == 'unavailable' for r in rows),
            'cost_usd': str(spent),
            'ms_median': int(statistics.median(ms)) if ms else None, 'ms_slowest': max(ms) if ms else None,
        }
