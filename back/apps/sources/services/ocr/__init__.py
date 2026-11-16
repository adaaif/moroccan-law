"""OCR of page images: Claude (Message Batches API, half price) and Tesseract (free, local).

Every Claude run is priced from the usage the API reports and saved as an OcrRun. A batch whose
worst case (every request writing max_tokens) would push the total past the budget, counting what
the other processes have in flight, is refused before it is sent (`reserve`). No paid request leaves a
process whose command was not given --write (`allow_spending`), whatever key the environment holds.

The API charges a batch when it runs it, whether or not the process that sent it lives to save the answers. So each
batch is written to the ledger (settings.LLM_LEDGER) at its worst case before it is created, with its id once the API
has it, and closed when its costs are saved. A batch left open by a process that died is looked up at the next start
of a paid command (`reconcile`): what it cost is recorded, and one still running is cancelled. Until then it counts at
its worst case.

Its parts, every name importable from here as before (the spending guard's `_SPENDING` aside: it lives in `guard`,
and a copy here would never change):

- `prices`: the models allowed, their prices, a request's worst case, OverBudget and ModelNotAllowed;
- `ledger`: the ledger's file, appended under a lock, its total, a call written to it, `spent`;
- `holds`: the batches out now, held against the budget (`reserve`), opened and closed in the ledger;
- `guard`: nothing paid without --write (`allow_spending`), and what dead processes left open (`reconcile`);
- `batches`: the paid client and the Message Batches API (`create_batch`, `wait_batches`, `_send`);
- `pages`: pages read whole, turned, by columns or in strips, an issue's readings, Tesseract.
"""
from apps.sources.services.render import OCR_WIDTH, render_columns, render_page, render_strips, render_turned
from apps.sources.services.ocr.prices import (PRICES, ModelNotAllowed, OverBudget, _worst_case, call_worst, check_model,
                                              price)
from apps.sources.services.ocr.ledger import (_LEDGER_READ, _append_unlocked, _ledger_lock, append_ledger, ledger_entries,
                                              ledger_path, ledger_total, record_call, spent)
from apps.sources.services.ocr.holds import (_CURRENT, _alive, _holds, _now, batch_refused, batch_sent, in_flight,
                                             open_batch, reserve)
from apps.sources.services.ocr.guard import (LOST_AFTER, SpendingNotAllowed, _reader, allow_spending, check_spending,
                                             reconcile)
from apps.sources.services.ocr.batches import (BATCH_BYTES, BATCH_WAIT_S, REFUSED_NOTHING_TAKEN, OutOfCredit, _client,
                                               _send, create_batch, wait_batches)
from apps.sources.services.ocr.pages import (
    COLUMN_ASK, PROMPT_VERSION, STRIP_ASK, SYSTEM, _column_requests, _params, _requests, _save_columns, _save_page,
    _text_of, ocr_claude_batch, ocr_claude_now, ocr_columns_batch, ocr_readings_batch, ocr_strips_batch, ocr_tesseract,
    readings_in_parts)
