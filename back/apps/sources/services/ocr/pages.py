"""Pages read: the transcription's instructions, a page read whole, turned upright, by its columns or in strips, alone
or many in a batch, an issue's readings in one batch or in the parts the budget holds, and Tesseract as the free
witness. Every Claude reading is saved as an OcrRun priced from the usage the API reports."""
import base64
import subprocess
import time
from decimal import Decimal

from django.conf import settings

from apps.sources.models import Language, OcrRun, Page
from apps.sources.services.ocr.batches import _client, _send
from apps.sources.services.ocr.holds import in_flight, reserve
from apps.sources.services.ocr.ledger import spent
from apps.sources.services.ocr.prices import OverBudget, _worst_case, price
from apps.sources.services.render import OCR_WIDTH, render_columns, render_page, render_strips, render_turned


PROMPT_VERSION = 'v1'


SYSTEM = (
    'You transcribe one page of the Moroccan Bulletin Officiel, or a related official document, '
    'exactly as printed. Output only the transcription, with no comment before or after it.\n'
    'Rules:\n'
    '- Follow the reading order of the page. Arabic pages: columns from right to left, each column '
    'top to bottom. French pages: columns from left to right.\n'
    '- Copy every word, number and punctuation mark as printed. Do not correct spelling, do not '
    'modernise, translate, summarise or complete anything.\n'
    '- Keep digits as printed (Western or Arabic-Indic).\n'
    '- Put each title, heading and article label (الفصل, المادة, Article) on its own line. '
    'Keep paragraphs; join the lines of a paragraph.\n'
    '- Tables: Markdown tables.\n'
    '- The running header (issue number, date, page number) is the first line.\n'
    '- A word you cannot read: [؟] on an Arabic page, [?] on a French page. Never guess.'
)


def _params(page: Page, model: str, max_tokens: int, image=None, ask: str = '') -> tuple[dict, str]:
    image = image or render_page(page)
    data = base64.standard_b64encode(image.read_bytes()).decode()
    lang = 'Arabic' if page.document.language == Language.ARABIC else 'French'
    params = {
        'model': model,
        'max_tokens': max_tokens,
        'system': SYSTEM,
        'output_config': {'effort': 'low'},
        'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': data}},
            {'type': 'text', 'text': ask or f'Transcribe this {lang} page.'},
        ]}],
    }
    return params, image.name


def _text_of(message) -> str:
    return ''.join(block.text for block in message.content if getattr(block, 'type', '') == 'text').strip()


def ocr_claude_now(page: Page, model: str, *, max_tokens: int = 8000) -> OcrRun:
    """One page, one request, standard price: for trying a prompt."""
    with reserve(f'{model} x1', _worst_case(model, 1, max_tokens, batch=False)):
        params, _ = _params(page, model, max_tokens)
        started = time.monotonic()
        message = _client().messages.create(**params)
        return OcrRun.objects.create(
            page=page, engine=model, variant=f'page-{OCR_WIDTH}', prompt_version=PROMPT_VERSION,
            image_px=f'{OCR_WIDTH}w', input_tokens=message.usage.input_tokens, output_tokens=message.usage.output_tokens,
            cost_usd=price(model, message.usage, batch=False), stop_reason=message.stop_reason or '',
            seconds=round(time.monotonic() - started, 1), text=_text_of(message),
        )


def _requests(pages: list[Page], model: str, max_tokens: int, *, turned: bool = False, ask: str = '',
              prefix: str = 'p') -> list[tuple[str, dict, int]]:
    """One request a page: (custom_id, params, image bytes)."""
    out = []
    for page in pages:
        image = render_turned(page) if turned else render_page(page)
        out.append((f'{prefix}{page.pk}', _params(page, model, max_tokens, image=image, ask=ask)[0],
                    image.stat().st_size))
    return out


def _column_requests(pages: list[Page], model: str, max_tokens: int,
                     width: int = 2 * OCR_WIDTH) -> list[tuple[str, dict, int]]:
    """Two requests a page, its columns in reading order (`p<pk>c0`, `p<pk>c1`)."""
    out = []
    for page in pages:
        lang = 'Arabic' if page.document.language == Language.ARABIC else 'French'
        for i, crop in enumerate(render_columns(page, width) or []):
            params, _ = _params(page, model, max_tokens, image=crop, ask=COLUMN_ASK.format(lang=lang))
            out.append((f'p{page.pk}c{i}', params, crop.stat().st_size))
    return out


def _save_page(page: Page, model: str, variant: str, message, batch_id: str) -> OcrRun:
    return OcrRun.objects.create(
        page=page, engine=model, variant=variant, prompt_version=PROMPT_VERSION,
        image_px=f'{OCR_WIDTH}w', input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens, cost_usd=price(model, message.usage, batch=True),
        batch_id=batch_id, stop_reason=message.stop_reason or '', text=_text_of(message),
    )


def _headers(pages: list[Page], model: str) -> dict[int, str]:
    """Each page's running header, by its key: the first line of its newest whole-page run by `model`, read for all the
    pages in one query (one a page before)."""
    newest: dict[int, OcrRun] = {}
    for run in (OcrRun.objects.filter(page__in=pages, engine=model, variant=f'page-{OCR_WIDTH}').order_by('-created_at')
                .only('page_id', 'text')) if pages else []:
        newest.setdefault(run.page_id, run)
    return {pk: run.text.strip().splitlines()[0] if run.text.strip() else '' for pk, run in newest.items()}


def _save_columns(pages: list[Page], model: str, results: dict, width: int = 2 * OCR_WIDTH) -> list[OcrRun]:
    """One OcrRun a page (variant `columns`): the whole-page run's header line, then the columns in reading order.
    Saved after the page runs of the same batch, which carry the header; the pages' headers read together, their runs
    written in one insert."""
    runs = []
    answered = [page for page in pages if None not in [results.get(f'p{page.pk}c{i}') for i in (0, 1)]]
    headers = _headers(answered, model)
    for page in answered:
        parts = [results.get(f'p{page.pk}c{i}') for i in (0, 1)]
        messages = [message for message, _ in parts]
        header = headers.get(page.pk, '')
        runs.append(OcrRun(
            page=page, engine=model, variant=f'columns-{width}', prompt_version=PROMPT_VERSION,
            image_px=f'{width}w/2', input_tokens=sum(m.usage.input_tokens for m in messages),
            output_tokens=sum(m.usage.output_tokens for m in messages),
            cost_usd=sum((price(model, m.usage, batch=True) for m in messages), Decimal('0')), batch_id=parts[0][1],
            stop_reason=','.join(m.stop_reason or '' for m in messages),
            text='\n\n'.join([header] + [_text_of(m) for m in messages]).strip(),
        ))
    return OcrRun.objects.bulk_create(runs)


def ocr_claude_batch(pages: list[Page], model: str, *, max_tokens: int = 8000, poll_s: int = 30,
                     turned: bool = False, variant: str = '', ask: str = '', log=print) -> list[OcrRun]:
    """Many pages in one Message Batch (half price); waits for it and saves one OcrRun per page.
    `turned`: sideways pages, sent turned upright (variant `turned`)."""
    variant = variant or (f'turned-{OCR_WIDTH}' if turned else f'page-{OCR_WIDTH}')
    with reserve(f'{model} x{len(pages)}', _worst_case(model, len(pages), max_tokens, batch=True)):
        results = _send(_requests(pages, model, max_tokens, turned=turned, ask=ask), model, log=log, poll_s=poll_s)
        return [_save_page(page, model, variant, *results[f'p{page.pk}']) for page in pages if f'p{page.pk}' in results]


COLUMN_ASK = ('This image is one column of an {lang} page, cut below its running header. '
              'Transcribe the whole column, top to bottom.')
STRIP_ASK = ('This image is the {half} half of {what} of an {lang} page, cut between two lines. Transcribe every '
             'line on it, top to bottom, even when it starts or ends in the middle of a sentence.')


def ocr_strips_batch(items: list[tuple[Page, bool]], model: str, *, width: int, max_tokens: int = 6000,
                     log=print) -> list[OcrRun]:
    """Pages a reading left short, read again in halves of their columns (`columns` True) or of the page (Z16 of
    the second-archive-run review): one OcrRun a page, variant `strips-<width>`, its parts joined in reading order, after
    the whole-page run's header when the columns left it out."""
    requests, parts = [], {}
    for page, columns in items:
        crops = render_strips(page, width, columns=columns)
        if not crops:
            continue
        lang = 'Arabic' if page.document.language == Language.ARABIC else 'French'
        what = 'one column' if columns else 'a page'
        for i, crop in enumerate(crops):
            ask = STRIP_ASK.format(half='upper' if i % 2 == 0 else 'lower', what=what, lang=lang)
            params, _ = _params(page, model, max_tokens, image=crop, ask=ask)
            requests.append((f'p{page.pk}s{i}', params, crop.stat().st_size))
        parts[page.pk] = (page, columns, len(crops))
    if not requests:
        return []
    with reserve(f'{model} strips x{len(requests)}', _worst_case(model, len(requests), max_tokens, batch=True)):
        results = _send(requests, model, log=log)
        runs = []
        answered = [(page, columns, n) for page, columns, n in parts.values()
                    if None not in [results.get(f'p{page.pk}s{i}') for i in range(n)]]
        headers = _headers([page for page, columns, _ in answered if columns], model)
        for page, columns, n in answered:
            got = [results.get(f'p{page.pk}s{i}') for i in range(n)]
            messages = [message for message, _ in got]
            header = headers.get(page.pk, '') if columns else ''
            runs.append(OcrRun(
                page=page, engine=model, variant=f'strips-{width}', prompt_version=PROMPT_VERSION,
                image_px=f'{width}w/{n}', input_tokens=sum(m.usage.input_tokens for m in messages),
                output_tokens=sum(m.usage.output_tokens for m in messages),
                cost_usd=sum((price(model, m.usage, batch=True) for m in messages), Decimal('0')), batch_id=got[0][1],
                stop_reason=','.join(m.stop_reason or '' for m in messages),
                text='\n'.join([header] + [_text_of(m) for m in messages]).strip(),
            ))
        return OcrRun.objects.bulk_create(runs)


def ocr_columns_batch(pages: list[Page], model: str, *, max_tokens: int = 8000, width: int = 2 * OCR_WIDTH,
                      log=print) -> list[OcrRun]:
    """The pages a whole-page reading left short: each column read on its own, in one batch."""
    pages = [page for page in pages if render_columns(page, width)]
    if not pages:
        return []
    with reserve(f'{model} columns x{len(pages)}', _worst_case(model, 2 * len(pages), max_tokens, batch=True)):
        return _save_columns(pages, model, _send(_column_requests(pages, model, max_tokens, width), model, log=log),
                             width)


def ocr_readings_batch(pages: list[Page], sideways: list[Page], split: list[Page], model: str, *,
                       width: int = 2 * OCR_WIDTH, log=print) -> None:
    """An issue's three readings at once: every page in `pages` read whole, the `sideways` ones turned upright,
    the `split` ones column by column. Which page is sideways or in two columns is known from the PDF and its
    image before any reading, so one batch carries them all instead of three in turn."""
    worst = (_worst_case(model, len(pages), 8000, batch=True) + _worst_case(model, len(sideways), 16000, batch=True)
             + _worst_case(model, 2 * len(split), 8000, batch=True))
    if not (pages or sideways or split):
        return
    with reserve(f'{model} readings x{len(pages)}', worst):
        requests = (_requests(pages, model, 8000) + _requests(sideways, model, 16000, turned=True, prefix='t')
                    + _column_requests(split, model, 8000, width))
        if not requests:
            return
        results = _send(requests, model, log=log)
        for page in pages:          # the page runs first: a column run takes its header line from one
            if f'p{page.pk}' in results:
                _save_page(page, model, f'page-{OCR_WIDTH}', *results[f'p{page.pk}'])
        for page in sideways:
            if f't{page.pk}' in results:
                _save_page(page, model, f'turned-{OCR_WIDTH}', *results[f't{page.pk}'])
        _save_columns(split, model, results, width)


def readings_in_parts(pages: list[Page], sideways: list[Page], split: list[Page], model: str, *,
                      width: int = 2 * OCR_WIDTH, log=print) -> None:
    """An issue's readings (`ocr_readings_batch`) in as few batches as the budget lets: all in one when their worst
    case fits what is left of it, else the pages in order, as many as fit, batch after batch. When not one more page
    fits, OverBudget, with the pages read so far kept: a later run reads on from the first page left. (A long issue
    asked for whole was refused every night under the nightly ceiling, about 147 pages, and stopped the issues after
    it.)"""
    whole, turned, columns = {p.pk for p in pages}, {p.pk for p in sideways}, {p.pk for p in split}
    order = sorted({p.pk: p for p in [*pages, *sideways, *split]}.values(), key=lambda p: p.index)
    if not order:
        return
    one, upright, two = (_worst_case(model, 1, 8000, batch=True), _worst_case(model, 1, 16000, batch=True),
                         _worst_case(model, 2, 8000, batch=True))
    cost = {p.pk: (one if p.pk in whole else 0) + (upright if p.pk in turned else 0) + (two if p.pk in columns else 0)
            for p in order}
    while order:
        room = Decimal(str(settings.OCR_BUDGET_USD)) - spent() - in_flight()
        part, worst = [], Decimal('0')
        for page in order:
            if worst + cost[page.pk] > room:
                break
            part.append(page)
            worst += cost[page.pk]
        if not part:
            first = cost[order[0].pk]
            raise OverBudget(f'page {order[0].index + 1}: worst case ${first:.4f}, ${max(room, 0):.4f} left of the '
                             f'budget; {len(order)} pages left for a later run', first)
        if len(part) < len(order):
            log(f'{len(part)} of {len(order)} pages in this batch: what is left of the budget holds no more at once')
        ocr_readings_batch([p for p in part if p.pk in whole], [p for p in part if p.pk in turned],
                           [p for p in part if p.pk in columns], model, width=width, log=log)
        order = order[len(part):]


def ocr_tesseract(page: Page) -> OcrRun:
    """Tesseract 5, the free baseline (auto page segmentation)."""
    image = render_page(page)
    lang = 'ara' if page.document.language == Language.ARABIC else 'fra'
    started = time.monotonic()
    result = subprocess.run(['tesseract', str(image), 'stdout', '-l', lang, '--psm', '3'],
                            capture_output=True, text=True, check=True)
    return OcrRun.objects.create(
        page=page, engine='tesseract-5', variant=f'page-{OCR_WIDTH}', image_px=f'{OCR_WIDTH}w',
        seconds=round(time.monotonic() - started, 1), text=result.stdout.strip(),
    )
