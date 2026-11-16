"""Whether this process may spend: no paid request leaves a process whose command was not given --write
(`allow_spending`, `check_spending`), and the first allowance looks up and closes the batches dead processes left open
in the ledger (`reconcile`)."""
import socket
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import CommandError
from django.db.models import Sum

from apps.sources.models import OcrRun
from apps.sources.services.ocr.holds import _alive
from apps.sources.services.ocr.ledger import _append_unlocked, _ledger_lock, ledger_entries
from apps.sources.services.ocr.prices import PRICES, price


class SpendingNotAllowed(CommandError):
    """A paid request from a command that was not given --write: refused before anything is sent. A CommandError, so
    the command ends on this one line."""


# Whether this process may send paid requests: a command given --write says so (`allow_spending`), and the commands it
# calls in the same process may then too (fetch_new_issues --write runs process_issue).
_SPENDING = False


def allow_spending(on: bool = True, log=print) -> None:
    """The first time a process is let spend, the batches dead processes left open are looked up first (`reconcile`),
    so tonight's ceiling starts from what was really spent."""
    global _SPENDING
    if on and not _SPENDING:
        _SPENDING = True
        reconcile(log=log)


def check_spending() -> None:
    if not _SPENDING:
        raise SpendingNotAllowed('This step sends paid requests to the model: run the command again with --write.')


def _reader():
    """A client that reads batches and cancels them, which costs nothing: `reconcile` runs before any --write check."""
    import anthropic

    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=4)


# A create with no id after this long, and no batch of its size found in the API's list near its time, took nothing.
LOST_AFTER = timedelta(hours=1)


def reconcile(log=print) -> int:
    """The batches a process on this machine opened in the ledger and did not live to close: each one's cost read
    from the API and recorded (less what the process had saved as OcrRuns or ledger lines), and its open line closed;
    one still running is cancelled (nobody waits for its answers) and closed once it has ended. A create that timed
    out is looked for in the API's list by its time and size. Run under the ledger's lock, so two processes never
    close one batch twice. Returns how many were closed."""
    with _ledger_lock() as path:
        entries = ledger_entries()
        opens, closed = {}, set()
        for e in entries:
            if 'close' in e:
                closed.add(e['close'])
            elif 'open' in e:
                o = opens.setdefault(e['open'], {'batch': None})
                if 'batch' in e:
                    o['batch'] = e['batch']
                else:
                    o.update(e)
        host = socket.gethostname()
        stale = {a: o for a, o in opens.items() if a not in closed and o.get('host') == host and not _alive(o['pid'])}
        if not stale:
            return 0
        if not settings.ANTHROPIC_API_KEY.startswith('sk-ant-'):
            log(f'{len(stale)} batches left open by processes that died: no key to look them up; '
                'counted at their worst case')
            return 0
        import anthropic

        client = _reader()
        known = {e['batch'] for e in entries if e.get('batch')}
        out, done = [], 0
        try:
            if lost := [o for o in stale.values() if not o['batch']]:
                page = client.messages.batches.list(limit=100)      # the newest hundred: one page, never them all
                listed = list(getattr(page, 'data', page))
                for o in lost:
                    at = datetime.fromisoformat(o['at'])
                    found = next((b for b in listed if b.id not in known
                                  and at - timedelta(minutes=2) <= b.created_at <= at + timedelta(minutes=15)
                                  and sum(vars(b.request_counts).values()) == o['requests']), None)
                    if found:
                        o['batch'] = found.id
                        known.add(found.id)
            groups = {}
            for attempt, o in stale.items():
                groups.setdefault(o.get('reserve') or attempt, []).append((attempt, o))
            settled = []        # (group, what its batches answered): the groups whose batches have all ended
            for group in groups.values():
                paid, ended = Decimal('0'), True
                for _attempt, o in group:
                    if not o['batch']:
                        ended = ended and datetime.now(UTC) - datetime.fromisoformat(o['at']) > LOST_AFTER
                        continue
                    batch = client.messages.batches.retrieve(o['batch'])
                    if batch.processing_status != 'ended':
                        ended = False
                        if batch.processing_status == 'in_progress':
                            client.messages.batches.cancel(o['batch'])
                            log(f'{o["batch"]}: sent by a process that died, cancelled; counted once it has ended')
                        continue
                    for entry in client.messages.batches.results(o['batch']):
                        if entry.result.type == 'succeeded':
                            message = entry.result.message
                            model = message.model if message.model in PRICES else o['model']
                            paid += price(model, message.usage, batch=True)
                if ended:
                    settled.append((group, paid))
        except anthropic.APIError as exc:
            log(f'the batches left open could not all be looked up ({exc}); the rest stay counted at their worst')
        ids = {o['batch'] for group, _ in settled for _, o in group if o['batch']}
        saved = dict(OcrRun.objects.filter(batch_id__in=ids).values_list('batch_id').annotate(n=Sum('cost_usd')))
        for e in entries:
            if e.get('batch') in ids and 'request' in e:
                saved[e['batch']] = saved.get(e['batch'], Decimal('0')) + Decimal(str(e['cost_usd']))
        for group, paid in settled:
            batches = [o['batch'] for _, o in group if o['batch']]
            unrecorded = max(paid - sum((saved.get(b, Decimal('0')) for b in batches), Decimal('0')), Decimal('0'))
            out += [{'kind': o['kind'], 'close': attempt, 'batch': o['batch'], 'cost_usd': -o['cost_usd']}
                    for attempt, o in group]
            done += len(group)
            if unrecorded:
                out.append({'kind': group[0][1]['kind'], 'reconciled': batches, 'cost_usd': float(unrecorded)})
                log(f'{", ".join(batches)}: ${unrecorded} paid and not recorded by the process that sent them, '
                    'now in the ledger')
        if out:
            _append_unlocked(path, out)
        return done
