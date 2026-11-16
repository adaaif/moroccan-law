"""check_eval measures the check before publishing on its test set: each item one request to the model (here the
`anthropic` client's stand-in, answering by markers in the words), inside the shared budget, every answer written to a
results file with what was stopped, what was missed by rule, the cost and the model's times. The test set is private:
these tests write a small one of their own, and the public tree's case (no set) measures the demo's words alone."""
import importlib.util
import itertools
import json
import re
import statistics
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.corpus.tests import claude
from apps.discussion.management.commands import check_eval, demo_content as demo
from apps.discussion.services import check
from apps.sources.services import ocr

pytestmark = pytest.mark.django_db

WRITTEN = '''
BREAKS = {
    'privacy': [('housing', 'جاري', 'جاري فلان الفلاني ما خلصش [return:privacy]'),
                ('housing', 'جاري', 'عنوان جاري كامل [hold:privacy]')],
    'respect': [('family', 'رأي', 'رأي فيه سب خفيف'), ('family', 'رأي', 'سب وخروج على الموضوع [return:on_topic]')],
}
PASSES = [('work', 'سؤال', 'شحال الساعات فالأسبوع؟'), ('work', 'الماتش', 'الماتش البارح [return:on_topic]'),
          ('work', 'سؤال', 'سؤال آخر [boom]')]
'''
DEMO = len(dict.fromkeys(demo.QUESTIONS_49 + demo.EXPLANATIONS_49 + demo.EXPERIENCES_49
                         + [x for group in demo.OPINIONS_49.values() for x in group]
                         + [x for s in demo.SMALL.values() for x in s['questions'] + s['explanations'] + s['opinions']])) \
    + len(dict.fromkeys(demo.REPLY_AGREE + demo.REPLY_DISAGREE + demo.REPLY_ASK + demo.REPLY_THANKS))
EACH = Decimal('0.0004')     # 2,000 tokens in and 400 out at $0.10 and $0.50 a million


@pytest.fixture
def model(settings, monkeypatch, tmp_path):
    """The stand-in model, a small test set of the test's own, results under tmp_path, and the check's clock: each
    reading a step further than the last (k² seconds), so each look takes longer than the one before."""
    def answer(custom_id, params):
        words = params['messages'][0]['content']
        answer.sent.append(params)
        if '[boom]' in words:
            raise RuntimeError('the API is down')
        found = re.search(r'\[(hold|return):(\w+)\]', words)
        outcome, rule = found.groups() if found else ('publish', 'none')
        return {'outcome': outcome, 'rule': rule}

    answer.sent = []
    claude.install(monkeypatch, settings, tmp_path, answer)
    settings.LLM_MODELS_ALLOWED, settings.OCR_BUDGET_USD = 'claude-haiku-5-5', 1.0
    (tmp_path / 'written.py').write_text(WRITTEN)
    spec = importlib.util.spec_from_file_location('written', tmp_path / 'written.py')
    written = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(written)
    monkeypatch.setattr(check_eval, 'written', written)
    monkeypatch.setattr(check_eval, 'RESULTS', tmp_path / 'results')
    ticks = itertools.count()
    monkeypatch.setattr(check, 'time', SimpleNamespace(monotonic=lambda: next(ticks) ** 2))
    return answer


def results(tmp_path, only=''):
    return json.loads((tmp_path / 'results' / f'{timezone.localdate()}-{check.PROMPT_VERSION}{only}.json').read_text())


def test_without_the_private_set_only_the_demos_words_are_measured(monkeypatch, capsys):
    monkeypatch.setattr(check_eval, 'written', None)
    with pytest.raises(CommandError, match='kept in a private evaluation set'):
        call_command('check_eval')
    call_command('check_eval', only='demo')
    assert capsys.readouterr().out == (f'{DEMO} items, one request each to claude-haiku-5-5: --write sends them '
                                       f'(at most $1.0)\n')


def test_without_write_nothing_is_sent_and_without_a_key_nothing_starts(model, settings, capsys, tmp_path):
    call_command('check_eval', only='breaks', max_usd=0.5)
    assert capsys.readouterr().out.startswith('4 items, one request each') and model.sent == []
    settings.ANTHROPIC_API_KEY = ''
    with pytest.raises(CommandError, match='ANTHROPIC_API_KEY'):
        call_command('check_eval', write=True)
    assert model.sent == [] and not (tmp_path / 'results').exists()


def test_each_item_is_one_look_and_the_summary_says_what_was_stopped_missed_and_spent(model, tmp_path, capsys):
    call_command('check_eval', write=True, workers=1)
    kept = results(tmp_path)
    rows, summary = kept['rows'], kept['summary']
    n = 7 + DEMO
    assert (kept['model'], kept['prompt_version'], len(rows), len(model.sent)) == (
        'claude-haiku-5-5', check.PROMPT_VERSION, n, n)
    assert rows[0] == {'id': 'privacy-01', 'part': 'breaks', 'place': {'ar': 'السكن والكراء', 'fr': 'Logement et location'},
                       'title': 'جاري', 'body': 'جاري فلان الفلاني ما خلصش [return:privacy]', 'expect': 'privacy',
                       'outcome': 'return', 'rule': 'privacy', 'failure': '', 'ms': 1000, 'cost': '0.0004'}
    assert [r['id'] for r in rows[:7]] == ['privacy-01', 'privacy-02', 'respect-01', 'respect-02', 'pass-01', 'pass-02',
                                       'pass-03']
    assert {r['part'] for r in rows[7:]} == {'demo'} and not any('parent' in r for r in rows)
    assert rows[7]['body'] == demo.QUESTIONS_49[0] and rows[-1]['id'].startswith('reply-')
    assert (rows[7]['ms'], rows[8]['ms']) == (29000, 33000)       # the 8th and 9th looks: 15² − 14², 17² − 16²
    # A reply is read with the post above it; the model is asked with the check's own prompt and schema.
    reply = model.sent[n - 1]
    assert '<post_above>الكد والسعاية\n' in reply['messages'][0]['content']
    assert (reply['model'], reply['system'], reply['max_tokens'], reply['output_config']['format']['schema']) == (
        'claude-haiku-5-5', check.PROMPT, 256, check.SCHEMA)
    passes = n - 4
    assert summary == {
        'items': n,
        'passes': {'n': passes, 'stopped': 2, 'stopped_rate': round(2 / passes, 3),
                   'which': [['pass-02', 'return', 'on_topic'], ['pass-03', 'unavailable', '']]},
        'breaks': {'n': 4, 'caught': 3, 'caught_rate': 0.75, 'by_rule': {
            'privacy': {'n': 2, 'caught': 2, 'own_rule': 2, 'held': 1, 'missed': []},
            'respect': {'n': 2, 'caught': 1, 'own_rule': 0, 'held': 0, 'missed': ['respect-01']}}},
        'unavailable': 1,
        'cost_usd': str(EACH * (n - 1)),
        'ms_median': int(statistics.median(r['ms'] for r in rows)), 'ms_slowest': max(r['ms'] for r in rows),
    }
    assert summary['ms_median'] < summary['ms_slowest']
    # Each answered look is in the shared ledger at its cost; the one that failed cost nothing and is not.
    looks = [e for e in ocr.ledger_entries() if e.get('kind') == 'check-eval']
    assert len(looks) == n - 1 and {(e['model'], e['cost_usd'], e['input_tokens']) for e in looks} == {
        ('claude-haiku-5-5', 0.0004, 2000)}
    out = capsys.readouterr().out
    assert json.loads(out[:out.rindex('written to')]) == summary and out.rstrip().endswith('.json')


def test_the_measure_stops_at_its_dollar_cap(model, tmp_path):
    call_command('check_eval', write=True, only='breaks', workers=1, max_usd=0.0004)
    kept = results(tmp_path, '-breaks')
    # Two looks are out before the first answer reaches the cap (its cost, exactly); the third is never sent.
    assert [r['id'] for r in kept['rows']] == ['privacy-01', 'privacy-02'] and len(model.sent) == 2
    assert (kept['summary']['items'], kept['summary']['cost_usd']) == (2, '0.0008')
    assert kept['summary']['passes'] == {'n': 0, 'stopped': 0, 'stopped_rate': None, 'which': []}


def test_a_look_the_budget_refuses_is_counted_unavailable_and_never_sent(model, settings, tmp_path):
    settings.OCR_BUDGET_USD = 0.0
    call_command('check_eval', write=True, only='passes')
    kept = results(tmp_path, '-passes')
    assert {(r['outcome'], r['failure'], r['cost']) for r in kept['rows']} == {('unavailable', 'budget', '0')}
    assert model.sent == [] and not ocr.ledger_entries()
    assert (kept['summary']['breaks']['caught_rate'], kept['summary']['unavailable']) == (None, 3)
    assert (kept['summary']['ms_median'], kept['summary']['ms_slowest']) == (None, None)
