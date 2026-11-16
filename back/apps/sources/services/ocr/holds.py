"""The batches out now: each process's worst case held against the budget while its batches are out (`reserve`), and
the batches this thread opened in the ledger before creating them, their ids beside them, closed when refused."""
import fcntl
import json
import os
import socket
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from django.conf import settings

from apps.sources.services.ocr.ledger import append_ledger, ledger_entries, spent
from apps.sources.services.ocr.prices import OverBudget


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@contextmanager
def _holds():
    """The batches out now, every process's ({key: {worst, pid, what}}), under a lock; a dead process's are gone."""
    path = Path(settings.CORPUS_DIR) / 'reports' / 'inflight.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix('.lock'), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        held = {k: v for k, v in (json.loads(path.read_text()) if path.exists() else {}).items() if _alive(v['pid'])}
        yield held
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(held))
        tmp.replace(path)


def in_flight() -> Decimal:
    with _holds() as held:
        return sum((Decimal(v['worst']) for v in held.values()), Decimal('0'))


# The reservation this thread is inside, and the batches it has opened in the ledger.
_CURRENT = threading.local()


@contextmanager
def reserve(what: str, worst: Decimal):
    """A batch's worst case held against the budget while it is out, its cost recorded before the hold goes.
    Every process sees what the others hold, so parallel workers cannot each fit under the budget and pass it
    together (18 Oct 2026: $0.72 over, from batches sent at once). The batches sent under it are closed in the
    ledger when it ends normally; after an error they stay open, counted, for `reconcile`."""
    key = f'{os.getpid()}-{time.time_ns()}'
    with _holds() as held:
        out = sum((Decimal(v['worst']) for v in held.values()), Decimal('0'))
        total = spent()
        if total + out + worst > Decimal(str(settings.OCR_BUDGET_USD)):
            raise OverBudget(f'{what}: worst case ${worst:.2f} on top of ${total:.2f} spent and ${out:.2f} in flight '
                             f'would pass the ${settings.OCR_BUDGET_USD:.2f} budget.', worst)
        held[key] = {'worst': str(worst), 'pid': os.getpid(), 'what': what}
    stack = getattr(_CURRENT, 'stack', [])
    frame = {'key': key, 'opened': {}}
    _CURRENT.stack = [*stack, frame]
    ended = False
    try:
        yield
        ended = True
    finally:
        _CURRENT.stack = stack
        if ended:       # a create with no id (it timed out, and was not refused) stays open for `reconcile`
            append_ledger([{'kind': o['kind'], 'close': attempt, 'batch': o['batch'], 'cost_usd': -o['worst']}
                           for attempt, o in frame['opened'].items() if o['batch']])
        with _holds() as held:
            held.pop(key, None)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec='seconds')


def open_batch(kind: str, model: str, requests: int, worst: Decimal) -> str:
    """A batch about to be created, written to the ledger at its worst case first: a process killed while it waits,
    or a create that timed out after the API took it, leaves it counted. The process's hold gives that much back, the
    ledger carrying it now."""
    attempt = f'{socket.gethostname()}:{os.getpid()}:{time.time_ns()}'
    frame = (getattr(_CURRENT, 'stack', None) or [None])[-1]
    append_ledger([{'kind': kind, 'open': attempt, 'model': model, 'requests': requests, 'host': socket.gethostname(),
                    'pid': os.getpid(), 'reserve': frame['key'] if frame else '', 'at': _now(),
                    'cost_usd': float(worst)}])
    if frame:
        frame['opened'][attempt] = {'kind': kind, 'batch': None, 'worst': float(worst)}
        with _holds() as held:
            if frame['key'] in held:
                held[frame['key']]['worst'] = str(max(Decimal(held[frame['key']]['worst']) - worst, Decimal('0')))
    return attempt


def batch_sent(attempt: str, kind: str, batch_id: str) -> None:
    """The batch's id beside its open line, before anything waits on it."""
    append_ledger([{'kind': kind, 'open': attempt, 'batch': batch_id, 'cost_usd': 0}])
    frame = (getattr(_CURRENT, 'stack', None) or [None])[-1]
    if frame and attempt in frame['opened']:
        frame['opened'][attempt]['batch'] = batch_id


def batch_refused(attempt: str, kind: str) -> None:
    """The API answered the create with a refusal: nothing was taken, the open line is closed."""
    frame = (getattr(_CURRENT, 'stack', None) or [None])[-1]
    worst = frame['opened'].pop(attempt)['worst'] if frame and attempt in frame['opened'] else None
    if worst is None:
        worst = next(e['cost_usd'] for e in ledger_entries() if e.get('open') == attempt)
    append_ledger([{'kind': kind, 'close': attempt, 'batch': None, 'cost_usd': -worst}])
