"""Structured Claude requests through the Message Batches API, priced and kept inside the shared budget.

The budget is the same one OCR spends: OcrRun prices plus this ledger (CORPUS_DIR/settings.LLM_LEDGER).
"""
import json
import os
from decimal import Decimal

from django.conf import settings

from apps.sources.services.ocr import (PRICES, OutOfCredit, append_ledger, batch_refused, batch_sent, check_model,
                                       check_spending, create_batch, ledger_entries, open_batch, reserve, spent,
                                       wait_batches)

# Requests a batch carries at most (0: all in one). On 24 Oct 2026 a batch of 28 waited untouched while small ones
# came back in minutes; the groups go out together, as OCR's do past its byte cap.
BATCH_REQUESTS = int(os.environ.get('LLM_BATCH_REQUESTS', 0))


ledger = ledger_entries
_append_to_ledger = append_ledger     # the ledger's own lock and format live in sources.services.ocr


def total_spent() -> Decimal:
    return spent()      # OCR runs and this ledger together (sources.services.ocr.spent)


def _client():
    import anthropic

    check_spending()
    if not settings.ANTHROPIC_API_KEY.startswith('sk-ant-'):
        raise RuntimeError('Set ANTHROPIC_API_KEY in the environment.')
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=4)


def request(custom_id: str, *, model: str, system: str, content: str, schema: dict, max_tokens: int,
            think: bool = True) -> dict:
    """`think=False` for writing that needs no reasoning: thinking was 56% of B9's output tokens."""
    params = {'model': model, 'max_tokens': max_tokens, 'system': system,
              'output_config': {'effort': 'low', 'format': {'type': 'json_schema', 'schema': schema}},
              'messages': [{'role': 'user', 'content': content}]}
    if not think:
        params['thinking'] = {'type': 'disabled'}
    return {'custom_id': custom_id, 'params': params}


def _worst_case(requests: list[dict]) -> Decimal:
    total = 0.0
    for r in requests:
        check_model(r['params']['model'])
        rate_in, rate_out = PRICES[r['params']['model']]
        # A token per character at most: Arabic runs nearer two characters a token, so this is a true ceiling.
        chars = len(r['params']['system']) + len(r['params']['messages'][0]['content'])
        total += (chars * rate_in + r['params']['max_tokens'] * rate_out) * 0.5 / 1e6
    return Decimal(str(round(total, 4)))


def run_batch(kind: str, requests: list[dict], *, poll_s: int = 20, log=print) -> dict[str, dict]:
    """Send, wait, price; returns {custom_id: {'data', 'stop', 'error'}}."""
    with reserve(kind, _worst_case(requests)):
        return _run(kind, requests, poll_s=poll_s, log=log)


def _run(kind: str, requests: list[dict], *, poll_s: int, log, again: bool = True) -> dict[str, dict]:
    import anthropic

    worst = _worst_case(requests)
    client = _client()
    size = BATCH_REQUESTS or len(requests) or 1
    batches = []
    for i in range(0, len(requests), size):
        group = requests[i:i + size]
        attempt = open_batch(kind, group[0]['params']['model'], len(group), _worst_case(group))
        try:
            batches.append(create_batch(client, group))
        except OutOfCredit:
            batch_refused(attempt, kind)
            if not batches:
                raise
            log(f'{kind}: out of credit, the batches already sent answered, the rest left unanswered')
            break
        except anthropic.APIStatusError:
            batch_refused(attempt, kind)
            raise
        batch_sent(attempt, kind, batches[-1].id)
        log(f'{kind}: batch {batches[-1].id}, {len(group)} requests'
            + (f' (worst case ${worst})' if len(batches) == 1 else ''))
    cancelled = wait_batches(client, [b.id for b in batches], poll_s=poll_s, log=log, what=kind)
    out, entries = {}, []
    for entry, bid in ((e, b.id) for b in batches for e in client.messages.batches.results(b.id)):
        if entry.result.type != 'succeeded':
            out[entry.custom_id] = {'data': None, 'stop': entry.result.type, 'error': entry.result.type}
            continue
        message = entry.result.message
        model = message.model if message.model in PRICES else requests[0]['params']['model']
        rate_in, rate_out = PRICES[model]
        cost = (message.usage.input_tokens * rate_in + message.usage.output_tokens * rate_out) * 0.5 / 1e6
        entries.append({'kind': kind, 'batch': bid, 'request': entry.custom_id, 'model': model,
                        'input_tokens': message.usage.input_tokens, 'output_tokens': message.usage.output_tokens,
                        'cost_usd': round(cost, 6)})
        body = ''.join(b.text for b in message.content if getattr(b, 'type', '') == 'text')
        try:
            data, error = json.loads(body), ''
        except json.JSONDecodeError as exc:
            data, error = None, f'not JSON: {exc}'
        out[entry.custom_id] = {'data': data, 'stop': message.stop_reason or '', 'error': error}
    append_ledger(entries)
    unanswered = ('canceled', 'errored', 'expired', None)
    if cancelled and again and (left := [r for r in requests if out.get(r['custom_id'], {}).get('error') in unanswered]):
        log(f'{kind}: {len(left)} requests sent again')
        out |= _run(kind, left, poll_s=poll_s, log=log, again=False)
    log(f'{kind}: done, total spent ${total_spent():.4f}')
    return out
