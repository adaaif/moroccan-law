"""Saving a batch's readings costs the same for a few pages as for ten times as many (no query inside a loop): the
whole-page runs whose header a page's columns or strips take are read for the batch, and its runs written in one
insert. Each page's run says what it said when the pages were saved one by one. No model is asked: the answers are
made here."""
import hashlib
from decimal import Decimal
from types import SimpleNamespace as NS

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.sources.models import Document, OcrRun, Page, PageKind
from apps.sources.services import ocr
from apps.sources.services.ocr import pages as reading

pytestmark = pytest.mark.django_db
HAIKU = 'claude-haiku-5-5'


def made(n: int, start: int = 0) -> list[Page]:
    """`n` pages of one issue, each but every fourth with its whole-page reading (two for every third: the newer
    counts), which starts with the page's running header."""
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=hashlib.sha256(str(start).encode()).hexdigest(),
                                  path=f'issues/bo_ar/{start}.pdf', mime='application/pdf', language='ar', bytes=1,
                                  fetched_at=timezone.now(), page_count=n)
    pages = [Page.objects.create(document=doc, index=i, kind=PageKind.SCAN, layer_letters=0) for i in range(n)]
    for i, page in enumerate(pages):
        if i % 4 == 3:
            continue
        OcrRun.objects.create(page=page, engine=HAIKU, variant=f'page-{ocr.OCR_WIDTH}', text=f'رأس قديم {i}\nنص')
        if i % 3 == 0:
            OcrRun.objects.create(page=page, engine=HAIKU, variant=f'page-{ocr.OCR_WIDTH}', text=f'الجريدة الرسمية {i}\nنص')
    return pages


def answer(text: str, batch: str = 'b1'):
    usage = NS(input_tokens=1000, output_tokens=400, cache_creation_input_tokens=0)
    return NS(usage=usage, content=[NS(type='text', text=text)], stop_reason='end_turn'), batch


def runs(saved) -> list[tuple]:
    return [(r.page.index, r.variant, r.text, r.image_px, r.input_tokens, r.output_tokens, r.cost_usd, r.batch_id,
             r.stop_reason, bool(r.pk)) for r in saved]


def test_a_batchs_columns_are_saved_at_one_cost(settings):
    costs, saved = [], []
    for n in (3, 30):
        pages = made(n, start=n)
        results = {f'p{p.pk}c{i}': answer(f'عمود {i} من الصفحة {p.index}') for p in pages for i in (0, 1)
                   if not (p.index == 1 and i == 1)}            # a column the batch did not answer: no run
        with CaptureQueriesContext(connection) as queries:
            out = reading._save_columns(pages, HAIKU, results)
        costs.append(len(queries))
        saved.append(runs(out))
    assert saved[0] == [(0, 'columns-3192', 'الجريدة الرسمية 0\n\nعمود 0 من الصفحة 0\n\nعمود 1 من الصفحة 0', '3192w/2', 2000,
                         800, Decimal('0.000300'), 'b1', 'end_turn,end_turn', True),
                        (2, 'columns-3192', 'رأس قديم 2\n\nعمود 0 من الصفحة 2\n\nعمود 1 من الصفحة 2', '3192w/2', 2000, 800,
                         Decimal('0.000300'), 'b1', 'end_turn,end_turn', True)]
    assert [r[0] for r in saved[1]] == [i for i in range(30) if i != 1]
    # The newest whole-page reading's first line heads the page; a page with none starts with its first column.
    assert [r[2].split('\n')[0] for r in saved[1]] == [
        f'عمود 0 من الصفحة {i}' if i % 4 == 3 else f'الجريدة الرسمية {i}' if i % 3 == 0 else f'رأس قديم {i}'
        for i in range(30) if i != 1]
    assert costs[0] == costs[1], costs


def test_a_batchs_strips_are_saved_at_one_cost(monkeypatch, tmp_path):
    crop = tmp_path / 'strip.webp'
    crop.write_bytes(b'x')
    monkeypatch.setattr(reading, 'render_strips', lambda page, width, columns: [crop, crop])
    monkeypatch.setattr(reading, '_params', lambda page, model, max_tokens, image, ask: ({}, None))
    costs, saved = [], []
    for n in (3, 30):
        pages = made(n, start=100 + n)
        results = {f'p{p.pk}s{i}': answer(f'شريط {i} من الصفحة {p.index}') for p in pages for i in (0, 1)}
        monkeypatch.setattr(reading, '_send', lambda requests, model, log: results)  # noqa: B023 (called in this iteration)
        with CaptureQueriesContext(connection) as queries:
            out = reading.ocr_strips_batch([(p, p.index % 2 == 0) for p in pages], HAIKU, width=3192, log=lambda m: None)
        costs.append(len(queries))
        saved.append(runs(out))
    assert [r[2] for r in saved[0]] == ['الجريدة الرسمية 0\nشريط 0 من الصفحة 0\nشريط 1 من الصفحة 0',
                                        'شريط 0 من الصفحة 1\nشريط 1 من الصفحة 1',
                                        'رأس قديم 2\nشريط 0 من الصفحة 2\nشريط 1 من الصفحة 2']
    assert len(saved[1]) == 30
    assert costs[0] == costs[1], costs


def test_the_coverage_line_tallies_every_issue_at_one_cost(settings, tmp_path, monkeypatch):
    """Each issue's legal texts as its contents list them, against those loaded from it: counted for all the issues in
    one query (one an issue before), each issue's tally what it was."""
    import json
    from datetime import date, timedelta

    from apps.corpus.models import Text
    from apps.sources.models import Edition, Issue
    from apps.sources.services import coverage

    settings.CORPUS_DIR = tmp_path
    known = {}
    costs, tallies = [], []
    for start, end in ((0, 3), (3, 30)):
        for i in range(start, end):
            day = date(2024, 1, 1) + timedelta(days=7 * i)
            issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7300 + i, suffix='bis' if i % 5 == 4 else '',
                                         date=day)
            known[issue.key] = day
            for t in range(i % 3):
                Text.objects.create(akn_uri=f'/akn/ma/act/decret/{i}-{t}', type='decree', number=f'{i}-{t}',
                                    title_ar=f'مرسوم {i} {t}', first_published_in=issue)
            entries = [{'toc': {'type': 'decree', 'title': f'مرسوم {t}'}, 'data': {'found': t < i % 3}} for t in range(3)]
            folder = tmp_path / 'reports' / 'issues' / issue.key
            folder.mkdir(parents=True)
            (folder / 'texts.json').write_text(json.dumps(entries))
        monkeypatch.setattr(coverage, '_known', lambda: dict(known))
        with CaptureQueriesContext(connection) as queries:
            saved = coverage.refresh()
        costs.append(len(queries))
        tallies.append(saved)
    assert len(tallies[1]) == 30
    assert tallies[1]['7304-bis'] == {'date': '2024-01-29', 'listed': 3, 'loaded': 1, 'unfound': 2,
                                      'unfound_titles': ['مرسوم 1', 'مرسوم 2'], 'waiting': 0, 'waiting_rules': 0}
    assert [tallies[1][k]['loaded'] for k in sorted(tallies[1])][:6] == [0, 1, 2, 0, 1, 2]
    assert costs[0] == costs[1], costs
