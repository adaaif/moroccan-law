"""The budget counts what was sent, not what a process lived to record: a batch is in the ledger at its worst case
before anything waits on it, and the next paid start records what a dead process left. The model is never called:
fake clients stand for the API."""
import io
import json
import os
import socket
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace as NS

import pytest

from apps.sources.services import ocr

pytestmark = pytest.mark.django_db       # the budget reads the readings' costs

HAIKU = 'claude-haiku-5-5'
ONE = ocr._worst_case(HAIKU, 1, 8000, batch=True)


def D(x) -> Decimal:
    """An amount as the ledger keeps it (a JSON number)."""
    return Decimal(str(float(x)))


@pytest.fixture
def ledger(settings, tmp_path, monkeypatch):
    settings.CORPUS_DIR = tmp_path
    settings.LLM_LEDGER = 'reports/llm_ledger.jsonl'
    settings.OCR_BUDGET_USD = 10.0
    settings.ANTHROPIC_API_KEY = 'sk-ant-not-a-key'
    ocr._LEDGER_READ.clear()
    monkeypatch.setattr(ocr.batches.time, 'sleep', lambda s: None)
    yield tmp_path / 'reports' / 'llm_ledger.jsonl'
    ocr._LEDGER_READ.clear()


def usage(i=1000, o=500):
    return NS(input_tokens=i, output_tokens=o, cache_creation_input_tokens=0)


def answered(cid, i=1000, o=500):
    return NS(custom_id=cid, result=NS(type='succeeded', message=NS(model=HAIKU, usage=usage(i, o))))


class Batches:
    """The API's batches: `create` hands out b1, b2…; each ends at once unless told otherwise."""

    def __init__(self, on_wait=None, running=()):
        self.created, self.cancelled, self.on_wait, self.running = [], [], on_wait, set(running)
        self.listed = []

    def create(self, requests):
        self.created.append([r['custom_id'] for r in requests])
        return NS(id=f'b{len(self.created)}')

    def retrieve(self, bid):
        if self.on_wait:
            self.on_wait(bid)
        status = 'in_progress' if bid in self.running and bid not in self.cancelled else 'ended'
        return NS(processing_status=status)

    def cancel(self, bid):
        self.cancelled.append(bid)

    def results(self, bid):
        yield answered(f'{bid}-1')
        yield answered(f'{bid}-2')

    def list(self, limit=20):
        return self.listed


def test_a_batch_is_in_the_ledger_at_its_worst_case_before_anything_waits_on_it(ledger, monkeypatch):
    seen = []
    batches = Batches(on_wait=lambda bid: seen.append(ocr.ledger_total()))
    monkeypatch.setattr(ocr.batches, '_client', lambda: NS(messages=NS(batches=batches)))
    with ocr.reserve('readings', 2 * ONE):
        assert ocr.in_flight() == 2 * ONE
        ocr._send([('p1', {'model': HAIKU, 'max_tokens': 8000}, 1), ('p2', {'model': HAIKU, 'max_tokens': 8000}, 1)],
                  HAIKU, log=lambda m: None, poll_s=0)
        assert ocr.in_flight() == 0            # the ledger carries it now: not counted twice
    assert seen and seen[0] == D(2 * ONE)
    lines = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [('open' in e, e.get('batch')) for e in lines[:2]] == [(True, None), (True, 'b1')]
    assert ocr.ledger_total() == 0             # closed once the reservation ended: the readings carry the cost


def test_a_batch_left_open_by_an_error_stays_counted(ledger, monkeypatch):
    def broken(bid):
        raise RuntimeError('the save failed')
    monkeypatch.setattr(ocr.batches, '_client', lambda: NS(messages=NS(batches=Batches(on_wait=broken))))
    with pytest.raises(RuntimeError):
        with ocr.reserve('readings', ONE):
            ocr._send([('p1', {'model': HAIKU, 'max_tokens': 8000}, 1)], HAIKU, log=lambda m: None, poll_s=0)
    assert ocr.ledger_total() == D(ONE)


def dead(ledger, *lines):
    """The ledger as a process that died left it."""
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open('a') as f:
        for line in lines:
            f.write(json.dumps(line) + '\n')


def opened(attempt, worst, *, requests=2, pid=999_999_999, at=None, reserve='r1'):
    return {'kind': 'ocr:haiku', 'open': attempt, 'model': HAIKU, 'requests': requests, 'host': socket.gethostname(),
            'pid': pid, 'reserve': reserve, 'at': (at or datetime.now(UTC)).isoformat(), 'cost_usd': float(worst)}


def test_the_next_paid_start_records_what_a_dead_process_paid_and_did_not_save(ledger, monkeypatch):
    batches = Batches()
    monkeypatch.setattr(ocr.guard, '_reader', lambda: NS(messages=NS(batches=batches)))
    dead(ledger, opened('a1', 2 * ONE), {'kind': 'ocr:haiku', 'open': 'a1', 'batch': 'b9', 'cost_usd': 0},
         # one of its two answers was saved before it died
         {'kind': 'texts:1', 'batch': 'b9', 'request': 'b9-1', 'model': HAIKU, 'cost_usd': float(ocr.price(HAIKU, usage(), batch=True))})
    assert ocr.ledger_total() == D(2 * ONE) + ocr.price(HAIKU, usage(), batch=True)
    assert ocr.reconcile(log=lambda m: None) == 1
    assert ocr.ledger_total() == 2 * ocr.price(HAIKU, usage(), batch=True)     # both answers paid, each counted once
    assert ocr.reconcile(log=lambda m: None) == 0                               # closed once only


def test_a_dead_process_s_batch_still_running_is_cancelled_and_stays_counted(ledger, monkeypatch):
    batches = Batches(running={'b9'})
    monkeypatch.setattr(ocr.guard, '_reader', lambda: NS(messages=NS(batches=batches)))
    dead(ledger, opened('a1', ONE), {'kind': 'ocr:haiku', 'open': 'a1', 'batch': 'b9', 'cost_usd': 0})
    assert ocr.reconcile(log=lambda m: None) == 0
    assert batches.cancelled == ['b9'] and ocr.ledger_total() == D(ONE)
    assert ocr.reconcile(log=lambda m: None) == 1           # ended once cancelled: what it answered is counted
    assert ocr.ledger_total() == 2 * ocr.price(HAIKU, usage(), batch=True)


def test_a_create_that_timed_out_is_found_by_its_time_and_size(ledger, monkeypatch):
    at = datetime.now(UTC) - timedelta(minutes=5)
    batches = Batches()
    batches.listed = [NS(id='b7', created_at=at + timedelta(seconds=40),
                         request_counts=NS(processing=0, succeeded=2, errored=0, canceled=0, expired=0)),
                      NS(id='b6', created_at=at + timedelta(seconds=40),
                         request_counts=NS(processing=0, succeeded=5, errored=0, canceled=0, expired=0))]
    monkeypatch.setattr(ocr.guard, '_reader', lambda: NS(messages=NS(batches=batches)))
    dead(ledger, opened('a1', ONE, at=at))
    assert ocr.reconcile(log=lambda m: None) == 1
    closing = next(e for e in map(json.loads, ledger.read_text().splitlines()) if e.get('close') == 'a1')
    assert closing['batch'] == 'b7' and ocr.ledger_total() == 2 * ocr.price(HAIKU, usage(), batch=True)


def test_a_live_process_s_batch_and_another_machine_s_are_left_alone(ledger, monkeypatch):
    monkeypatch.setattr(ocr.guard, '_reader', lambda: pytest.fail('nothing to look up'))
    other = {**opened('a2', ONE), 'host': 'elsewhere'}
    dead(ledger, opened('a1', ONE, pid=os.getpid()), other)
    assert ocr.reconcile(log=lambda m: None) == 0
    assert ocr.ledger_total() == 2 * D(ONE)


def test_being_let_spend_reconciles_first(ledger, monkeypatch):
    batches = Batches()
    monkeypatch.setattr(ocr.guard, '_reader', lambda: NS(messages=NS(batches=batches)))
    monkeypatch.setattr(ocr.guard, '_SPENDING', False)
    dead(ledger, opened('a1', ONE), {'kind': 'ocr:haiku', 'open': 'a1', 'batch': 'b9', 'cost_usd': 0})
    ocr.allow_spending(log=lambda m: None)
    assert ocr.ledger_total() == 2 * ocr.price(HAIKU, usage(), batch=True)


# ── a create is sent once ────────────────────────────────────────────────────────────────────────────────────────────

def status_error(cls, code, message='no'):
    import anthropic
    import httpx2 as httpx
    response = httpx.Response(code, request=httpx.Request('POST', 'https://api.anthropic.com/v1/messages/batches'))
    return getattr(anthropic, cls)(message, response=response, body=None)


def test_a_create_that_timed_out_is_never_sent_again_and_its_line_stays_open(ledger, monkeypatch):
    import anthropic
    import httpx2 as httpx
    calls = []

    class Once:
        def create(self, requests):
            calls.append(1)
            raise anthropic.APITimeoutError(request=httpx.Request('POST', 'https://api.anthropic.com/v1/messages/batches'))

    retries = []
    client = NS(messages=NS(batches=Once()), with_options=lambda **kw: retries.append(kw) or NS(messages=NS(batches=Once())))
    monkeypatch.setattr(ocr.batches, '_client', lambda: client)
    with pytest.raises(anthropic.APITimeoutError):
        with ocr.reserve('readings', ONE):
            ocr._send([('p1', {'model': HAIKU, 'max_tokens': 8000}, 1)], HAIKU, log=lambda m: None)
    assert calls == [1] and retries == [{'max_retries': 0}]
    assert ocr.ledger_total() == D(ONE)           # counted until `reconcile` finds out


def test_a_create_the_api_refused_took_nothing_and_is_tried_again(ledger, monkeypatch):
    answers = [status_error('InternalServerError', 529), status_error('RateLimitError', 429)]
    created = []

    class Busy:
        def create(self, requests):
            if answers:
                raise answers.pop(0)
            created.append(1)
            return NS(id='b1')

        def retrieve(self, bid):
            return NS(processing_status='ended')

        def results(self, bid):
            return iter([])

    monkeypatch.setattr(ocr.batches, '_client', lambda: NS(messages=NS(batches=Busy())))
    with ocr.reserve('readings', ONE):
        ocr._send([('p1', {'model': HAIKU, 'max_tokens': 8000}, 1)], HAIKU, log=lambda m: None, poll_s=0)
    assert created == [1] and ocr.ledger_total() == 0


def test_a_create_refused_for_good_closes_its_line(ledger, monkeypatch):
    class No:
        def create(self, requests):
            raise status_error('BadRequestError', 400, 'invalid request')

    monkeypatch.setattr(ocr.batches, '_client', lambda: NS(messages=NS(batches=No())))
    with pytest.raises(Exception, match='invalid'):
        with ocr.reserve('readings', ONE):
            ocr._send([('p1', {'model': HAIKU, 'max_tokens': 8000}, 1)], HAIKU, log=lambda m: None)
    assert ocr.ledger_total() == 0


# ── the commands that spent outside the ledger ───────────────────────────────────────────────────────────────────────

class Messages:
    def __init__(self, text='{"texts": []}'):
        self.sent, self.text = [], text

    def create(self, **params):
        self.sent.append(params)
        return NS(usage=usage(2000, 300), content=[NS(type='text', text=self.text)], stop_reason='end_turn',
                  model=params.get('model'))


def test_the_structure_reading_is_held_against_the_budget_and_written_to_the_ledger(ledger, settings, monkeypatch):
    from apps.corpus.services import structure
    messages = Messages()
    monkeypatch.setattr(ocr, '_client', lambda: NS(messages=messages))      # structure calls ocr._client()
    _data, _cost = structure.extract('نص', model=HAIKU)
    entry = json.loads(ledger.read_text().splitlines()[-1])
    assert entry['kind'] == 'structure' and Decimal(str(entry['cost_usd'])) == ocr.price(HAIKU, usage(2000, 300), batch=False)
    settings.OCR_BUDGET_USD = float(ocr.spent())      # nothing left
    with pytest.raises(ocr.OverBudget):
        structure.extract('نص', model=HAIKU)
    assert len(messages.sent) == 1


def test_the_check_s_measure_is_written_to_the_ledger(ledger, settings, monkeypatch):
    from apps.discussion.management.commands import check_eval
    from apps.discussion.services import check
    settings.CHECK_MODEL = HAIKU
    monkeypatch.setattr(check, 'ask', lambda text: check.Asked('publish', '', '', 900, 20, Decimal('0.0001'), 5))
    found = check_eval.ask('كلمات')
    assert found.outcome == 'publish'
    entry = json.loads(ledger.read_text().splitlines()[-1])
    assert entry['kind'] == 'check-eval' and entry['cost_usd'] == 0.0001
    settings.OCR_BUDGET_USD = float(ocr.spent())
    assert check_eval.ask('كلمات').failure == 'budget'


def test_the_mcp_measure_is_written_to_the_ledger(ledger, monkeypatch):
    from apps.mcp.management.commands.measure_mcp import Command
    import threading
    command = Command(stdout=io.StringIO())
    messages = Messages(text='جواب')
    command.api, command.cap, command.spent, command.counting = NS(messages=messages), 2.0, 0.0, threading.Lock()
    command._ask(max_tokens=1500, messages=[{'role': 'user', 'content': 'سؤال'}], system='s')
    entry = json.loads(ledger.read_text().splitlines()[-1])
    assert entry['kind'] == 'mcp-measure' and command.spent == entry['cost_usd'] > 0


# ── a long issue read in parts ───────────────────────────────────────────────────────────────────────────────────────

def test_a_long_issue_is_read_in_parts_the_budget_holds_and_a_later_run_reads_on(settings, monkeypatch):
    pages = [NS(pk=i, index=i) for i in range(12)]
    sent = []
    monkeypatch.setattr(ocr.pages, 'ocr_readings_batch', lambda whole, turned, split, model, **kw: sent.append([p.pk for p in whole]))
    monkeypatch.setattr(ocr.pages, 'in_flight', lambda: Decimal('0'))
    monkeypatch.setattr(ocr.pages, 'spent', lambda: Decimal('0'))
    settings.OCR_BUDGET_USD = float(5 * ONE + ONE / 2)                 # five pages at once
    ocr.readings_in_parts(pages, [], [], HAIKU, log=lambda m: None)
    assert sent == [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9], [10, 11]]
    # The money runs out after the first part: the pages read stay read, the rest wait for a later run.
    sent.clear()
    spending = iter([Decimal('0'), 5 * ONE])
    monkeypatch.setattr(ocr.pages, 'spent', lambda: next(spending))
    with pytest.raises(ocr.OverBudget) as refused:
        ocr.readings_in_parts(pages, [], [], HAIKU, log=lambda m: None)
    assert sent == [[0, 1, 2, 3, 4]] and refused.value.worst == ONE


def test_an_issue_that_fits_is_still_read_in_one_batch(settings, monkeypatch):
    pages = [NS(pk=i, index=i) for i in range(3)]
    sent = []
    monkeypatch.setattr(ocr.pages, 'ocr_readings_batch',
                        lambda whole, turned, split, model, **kw: sent.append(([p.pk for p in whole], [p.pk for p in turned],
                                                                                [p.pk for p in split])))
    monkeypatch.setattr(ocr.pages, 'in_flight', lambda: Decimal('0'))
    monkeypatch.setattr(ocr.pages, 'spent', lambda: Decimal('0'))
    ocr.readings_in_parts(pages, pages[2:], pages[:2], HAIKU, log=lambda m: None)
    assert sent == [([0, 1, 2], [2], [0, 1])]
