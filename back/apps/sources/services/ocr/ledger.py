"""The ledger (settings.LLM_LEDGER), the one record of what every process spent: appended under a lock, its total read
on from where this process last stopped, a request outside a batch written to it, and everything spent in all."""
import fcntl
import json
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db.models import Sum

from apps.sources.models import OcrRun
from apps.sources.services.ocr.prices import price


def ledger_path() -> Path:
    return Path(settings.CORPUS_DIR) / settings.LLM_LEDGER


def ledger_entries() -> list[dict]:
    path = ledger_path()
    if not path.exists():
        return []
    if path.suffix == '.jsonl':
        # The last piece is '' or a line another process is still writing.
        return [json.loads(line) for line in path.read_text().split('\n')[:-1] if line.strip()]
    return json.loads(path.read_text())


@contextmanager
def _ledger_lock():
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix('.lock'), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield path


def _append_unlocked(path: Path, entries: list[dict]) -> None:
    if path.suffix == '.jsonl':
        with open(path, 'a', encoding='utf-8') as f:
            f.write(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in entries))
        return
    current = json.loads(path.read_text()) if path.exists() else []
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(current + entries, ensure_ascii=False, indent=1))
    tmp.replace(path)


def append_ledger(entries: list[dict]) -> None:
    """Several processes spend at once: the ledger is appended under a lock (a `.json` one re-read and replaced in one
    move), so no process overwrites another's costs. A `.jsonl` ledger only gains lines."""
    if entries:
        with _ledger_lock() as path:
            _append_unlocked(path, entries)


_LEDGER_READ: dict[Path, tuple[int, Decimal]] = {}


def ledger_total() -> Decimal:
    """What the structuring ledger records. A `.jsonl` ledger is read on from where this process last stopped, so
    a dozen workers checking the budget before every batch never parse the whole file again."""
    path = ledger_path()
    if not path.exists():
        return Decimal('0')
    if path.suffix != '.jsonl':
        return sum((Decimal(str(e['cost_usd'])) for e in json.loads(path.read_text())), Decimal('0'))
    offset, total = _LEDGER_READ.get(path, (0, Decimal('0')))
    if path.stat().st_size < offset:        # the file was replaced: read it again from its start
        offset, total = 0, Decimal('0')
    with open(path, 'rb') as f:
        f.seek(offset)
        for line in f:
            if not line.endswith(b'\n'):    # a line another process is still writing
                break
            total += Decimal(str(json.loads(line)['cost_usd']))
            offset += len(line)
    _LEDGER_READ[path] = (offset, total)
    return total


def spent() -> Decimal:
    """Everything spent on the API: OCR runs, and the structuring ledger the corpus keeps (settings.LLM_LEDGER).
    The budget caps the total."""
    ocr = OcrRun.objects.aggregate(total=Sum('cost_usd'))['total'] or Decimal('0')
    return ocr + ledger_total()


def record_call(kind: str, model: str, usage=None, *, cost: Decimal | None = None, **meta) -> Decimal:
    """A request sent outside a batch, written to the ledger as soon as it has answered (inside `reserve`, which held
    its worst case while it was out). `cost` when the caller has priced it already."""
    cost = Decimal(str(cost)) if cost is not None else price(model, usage, batch=False)
    tokens = {'input_tokens': getattr(usage, 'input_tokens', 0) or 0,
              'output_tokens': getattr(usage, 'output_tokens', 0) or 0} if usage is not None else {}
    append_ledger([{'kind': kind, 'model': model, 'call': True, **tokens, **meta, 'cost_usd': float(cost)}])
    return cost
