"""The Message Batches API: the paid client, a batch created once (OutOfCredit when the key is spent), the batches
waited for and cancelled when the queue sits on them, and requests sent as batches under BATCH_BYTES (`_send`)."""
import os
import time
from decimal import Decimal

from django.conf import settings

from apps.sources.services.ocr.guard import check_spending
from apps.sources.services.ocr.holds import batch_refused, batch_sent, open_batch
from apps.sources.services.ocr.prices import _worst_case, check_model


class OutOfCredit(RuntimeError):
    """The API refused a batch for want of credit: this key is spent (31 Oct 2026, the month's last credit read until
    it ran out). Other keys, or next month's credit, take the work on; nothing is marked done or failed."""


# Answers that say the API took nothing (rate limit, overload, server error): the create is tried again.
REFUSED_NOTHING_TAKEN = {429, 500, 502, 503, 504, 529}


def create_batch(client, requests: list[dict]):
    """A Message Batch; the API's «credit balance is too low» raised as OutOfCredit. The create goes once, with no
    retry by the client: a create that timed out may still have been taken, and sending it again would pay twice (its
    open line in the ledger keeps it counted until `reconcile` finds it). An answer that says nothing was taken is
    tried again, at most four times."""
    import anthropic

    once = client.with_options(max_retries=0) if hasattr(client, 'with_options') else client
    for attempt in range(4):
        try:
            return once.messages.batches.create(requests=requests)
        except anthropic.APIStatusError as exc:
            if 'credit balance' in str(exc).lower():
                raise OutOfCredit(str(exc)) from exc
            if exc.status_code not in REFUSED_NOTHING_TAKEN or attempt == 3:
                raise
            wait = exc.response.headers.get('retry-after', '') if exc.response is not None else ''
            time.sleep(min(float(wait) if wait.replace('.', '', 1).isdigit() else 15 * 2 ** attempt, 300))


def _client():
    import anthropic

    check_spending()
    if not settings.ANTHROPIC_API_KEY.startswith('sk-ant-'):
        raise RuntimeError('Set ANTHROPIC_API_KEY in the environment.')
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=4)


# A request carries its image in base64. The images of one batch stay under 64 MB (a page is about 0.2 MB, a
# column 0.35 MB), far under the API's 256 MB; a bigger set goes as several batches sent together.
BATCH_BYTES = int(os.environ.get('OCR_BATCH_BYTES', 64_000_000))   # smaller batches when the queue is slow (24 Oct 2026: one of 198 page images waited an hour)
# A batch still out after this is cancelled and what it had not answered sent once more (29 Oct 2026: one sat 4 h 40
# with none of its 126 pages begun, and its worker with it). A cancelled request costs nothing.
BATCH_WAIT_S = int(os.environ.get('BATCH_WAIT_S', 3600))


def wait_batches(client, batches: list[str], *, poll_s: int, log, what: str) -> bool:
    """Until every batch has ended; those still out after BATCH_WAIT_S are cancelled (their answers stay). True
    when one was."""
    started, pending, cancelled = time.monotonic(), set(batches), False
    while pending:
        time.sleep(poll_s)
        pending = {bid for bid in pending if client.messages.batches.retrieve(bid).processing_status != 'ended'}
        if pending and not cancelled and time.monotonic() - started > BATCH_WAIT_S:
            for bid in pending:
                client.messages.batches.cancel(bid)
            cancelled = True
            log(f'{what}: {", ".join(sorted(pending))} still out after {BATCH_WAIT_S} s, cancelled')
    return cancelled


def _send(requests: list[tuple[str, dict, int]], model: str, *, log=print, poll_s: int = 30,
          again: bool = True) -> dict:
    """The requests as one Message Batch, or several created together when their images pass BATCH_BYTES; waits
    for all of them, sending once more those a cancelled batch left. {custom_id: (message, batch id)} for the
    requests that succeeded."""
    for _, params, _ in requests:
        check_model(params.get('model', model))
    chunks, size = [[]], 0
    for request in requests:
        if chunks[-1] and size + request[2] > BATCH_BYTES:
            chunks.append([])
            size = 0
        chunks[-1].append(request)
        size += request[2]
    import anthropic

    client = _client()
    batches = []
    for chunk in chunks:
        worst = sum((_worst_case(params.get('model', model), 1, params.get('max_tokens', 8000), batch=True)
                     for _, params, _ in chunk), Decimal('0'))
        attempt = open_batch(f'ocr:{model}', model, len(chunk), worst)
        try:
            batch = create_batch(client, [{'custom_id': cid, 'params': params} for cid, params, _ in chunk])
        except OutOfCredit:
            batch_refused(attempt, f'ocr:{model}')
            if not batches:
                raise
            log(f'{model}: out of credit, the batches already sent answered, the rest left unread')
            break
        except anthropic.APIStatusError:
            batch_refused(attempt, f'ocr:{model}')
            raise
        batch_sent(attempt, f'ocr:{model}', batch.id)
        log(f'{model}: batch {batch.id} with {len(chunk)} requests sent')
        batches.append(batch.id)
    started = time.monotonic()
    cancelled = wait_batches(client, batches, poll_s=poll_s, log=log, what=model)
    log(f'{model}: {len(batches)} batch{"es" if len(batches) > 1 else ""} ended after '
        f'{time.monotonic() - started:.0f} s')
    results = {}
    for bid in batches:
        for entry in client.messages.batches.results(bid):
            if entry.result.type == 'succeeded':
                results[entry.custom_id] = (entry.result.message, bid)
            else:
                log(f'  {entry.custom_id}: {entry.result.type}')
    if cancelled and again and (left := [r for r in requests if r[0] not in results]):
        log(f'{model}: {len(left)} requests sent again')
        results |= _send(left, model, log=log, poll_s=poll_s, again=False)
    return results
