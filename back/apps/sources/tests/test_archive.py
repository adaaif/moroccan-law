"""The Bulletin-to-1956 review: Tesseract as the witness of a scan's reading, one reading a page, the second
readings, the workers' claims and the append-only ledger (27 Oct 2026)."""
import gzip
import hashlib
import json
from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

# Imported before any test here patches `llm.run_batch`: the archive's phases import it lazily, and its modules bind
# `run_batch` when first imported, so under the patch they kept the fake for every later test of the worker.
import apps.corpus.services.issue_structure  # noqa: F401
from apps.sources.models import Document, Edition, Issue, OcrRun, Page, PageKind
from apps.sources.services import archive, witness

HAIKU = 'claude-haiku-5-5'
WORDS = 'وزير الداخلية بناء على الظهير الشريف المتعلق بالجماعات'


def _line(left, top, right, text, conf=90):
    return [left, top, right, top + 20, text, conf]


def two_columns_page(i=0, lines=30, head='عدد 2685 - الجريدة الرسمية 1341'):
    body = [_line(820, 140 + 40 * n, 1360, WORDS) for n in range(lines)]
    body += [_line(60, 140 + 40 * n, 600, WORDS) for n in range(lines)]
    return {'i': i, 'w': 1400, 'h': 1800, 'rot': 0, 'lines': [_line(300, 40, 1100, head)] + body}


_LETTERS = 'بتثجحخدذرزسشصضطظعغفقكلمنهوي'


def _word(m):
    return 'س' + ''.join(_LETTERS[(m // 27 ** k) % 27] for k in range(3))


def distinct_page(i=0, lines=30):
    """Two columns of lines no two alike, five words each: what a reading lacks shows line by line."""
    body = [_line(820, 140 + 40 * n, 1360, ' '.join(_word(5 * n + k) for k in range(5))) for n in range(lines)]
    body += [_line(60, 140 + 40 * n, 600, ' '.join(_word(5 * (lines + n) + k) for k in range(5))) for n in range(lines)]
    return {'i': i, 'w': 1400, 'h': 1800, 'rot': 0, 'lines': [_line(300, 40, 1100, 'عدد 2685 الجريدة الرسمية 1341')] + body}


def _read(seen, share=1.0):
    """A reading of the first `share` of the witness's body lines, as Haiku would write them."""
    lines = witness.body(seen)
    return '\n'.join(line[4] for line in lines[:round(len(lines) * share)])


def full_width_page(i=0):
    return {'i': i, 'w': 1400, 'h': 1800, 'rot': 0,
            'lines': [_line(60, 140 + 40 * n, 1360, WORDS + ' ' + WORDS) for n in range(30)]}


def contents_page(i=0):
    return {'i': i, 'w': 1400, 'h': 1800, 'rot': 0,
            'lines': [_line(60, 140 + 40 * n, 1360, f'مرسوم رقم 2.64.{n} بتغيير القرار الوزيري .......... {1300 + n}')
                      for n in range(25)]}


def _doc(tmp_path, settings, pages, stem='BO_2685_Ar', key=None):
    settings.CORPUS_DIR = tmp_path
    folder = tmp_path / 'tess'
    folder.mkdir(exist_ok=True)
    with gzip.open(folder / f'{stem}.json.gz', 'wt', encoding='utf-8') as f:
        json.dump({'file': f'{stem}.pdf', 'pages': pages}, f)
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=hashlib.sha256(stem.encode()).hexdigest(),
                                  path=f'issues/bo_ar/{stem.lower()}.pdf', mime='application/pdf', language='ar',
                                  bytes=1, fetched_at=timezone.now(), meta={'archive': f'1964/{stem}.pdf'},
                                  page_count=len(pages))
    for p in pages:
        Page.objects.create(document=doc, index=p['i'], kind=PageKind.SCAN, layer_letters=0)
    if key:
        number, suffix = Issue.parse_key(key)
        Issue.objects.create(edition=Edition.GENERAL_AR, number=number, suffix=suffix, date=date(1964, 3, 11),
                             document=doc)
    return doc


@pytest.mark.django_db
def test_the_witness_tells_two_columns_from_a_full_width_page(tmp_path, settings):
    doc = _doc(tmp_path, settings, [two_columns_page(0), full_width_page(1)])
    first, second = doc.pages.order_by('index')
    assert witness.two_columns(witness.of(first)) is True
    assert witness.two_columns(witness.of(second)) is False      # K10's half-lines: never cut this one in two
    assert witness.sideways(witness.of(first)) is False
    assert witness.head_lines(witness.of(first)) == ['عدد 2685 - الجريدة الرسمية 1341']


@pytest.mark.django_db
def test_the_contents_run_as_long_as_the_pages_read_like_contents(tmp_path, settings):
    doc = _doc(tmp_path, settings, [two_columns_page(0), contents_page(1), contents_page(2), two_columns_page(3),
                                    contents_page(4)])
    assert witness.contents_pages(doc) == 3
    plain = _doc(tmp_path, settings, [two_columns_page(0), two_columns_page(1), two_columns_page(2)], stem='BO_9_Ar')
    assert witness.contents_pages(plain) == 2              # the cover, and the top of the next page


@pytest.mark.django_db
def test_a_short_reading_is_doubted_when_the_witnesss_sure_lines_agree_and_a_long_one_never(tmp_path, settings):
    """The second-archive-run review: readings with more letters than Tesseract held their lines; a short one is in
    doubt when the lines Tesseract is sure of agree it lacks some."""
    garbage = [_line(60, 1500 + 10 * n, 1360, 'عتسصتطواومصغ زاعه' * 6, conf=20) for n in range(20)]
    page_plus = {**distinct_page(1), 'lines': distinct_page(1)['lines'] + garbage}
    doc = _doc(tmp_path, settings, [distinct_page(0), page_plus])
    page, noisy = doc.pages.order_by('index')
    seen = witness.of(page)
    whole = OcrRun.objects.create(page=page, engine=HAIKU, variant='page-1596', text=_read(seen))
    assert archive.doubt(page, whole, median=1.0) == ''
    more = OcrRun.objects.create(page=page, engine=HAIKU, variant='page-1596', text=_read(seen) + '\n' + 'ب' * 5000)
    assert archive.doubt(page, more, median=1.0) == ''                   # never doubted for having more
    half = OcrRun.objects.create(page=page, engine=HAIKU, variant='columns-3192', text=_read(seen, 0.5))
    assert archive.doubt(page, half, median=1.0) == 'letters'            # a column dropped
    assert archive.gap(page, half) == {'run': 30, 'at': [0.078, 0.733], 'lines': 60}     # the left column
    full = OcrRun.objects.create(page=noisy, engine=HAIKU, variant='page-1596', text=_read(page_plus, 60 / 80))
    assert witness.ratio(noisy, full.text) < 0.85 and archive.doubt(noisy, full, median=1.0) == ''   # Tesseract's noise
    cut = OcrRun.objects.create(page=page, engine=HAIKU, variant='page-1596', text='ب', stop_reason='max_tokens')
    assert archive.doubt(page, cut, median=1.0) == 'cut'
    table = OcrRun.objects.create(page=page, engine=HAIKU, variant='columns-3192',
                                  text='\n'.join(['| البند | المبلغ |'] * 10) + '\n' + _read(seen).replace('\n', ' '))
    assert archive.doubt(page, table, median=1.0) == 'table'
    elided = OcrRun.objects.create(page=page, engine=HAIKU, variant='page-1596', text=_read(seen) + '\n| 2 | ... | 31 |')
    assert archive.doubt(page, elided, median=1.0) == 'elided'


@pytest.mark.django_db
def test_a_page_with_too_few_lines_to_compare_is_doubted_only_when_short_of_letters(tmp_path, settings):
    doc = _doc(tmp_path, settings, [{'i': 0, 'w': 1400, 'h': 1800, 'rot': 0,
                                     'lines': [_line(60, 140 + 40 * n, 1360, '١٢٣ ' + 'ب' * 60) for n in range(4)]}])
    page = doc.pages.get()
    expected = witness.page_letters(witness.of(page))
    short = OcrRun.objects.create(page=page, engine=HAIKU, variant='page-1596', text='ب' * (expected // 2))
    long = OcrRun.objects.create(page=page, engine=HAIKU, variant='page-1596', text='ب' * (expected * 2))
    assert (archive.doubt(page, short, 1.0), archive.doubt(page, long, 1.0)) == ('letters', '')


@pytest.mark.django_db
def test_a_doubted_reading_is_read_the_other_way_and_one_cut_at_the_token_limit_in_strips(tmp_path, settings, monkeypatch):
    full = {**distinct_page(2), 'lines': [[60, line[1], 1360, *line[3:]] for line in distinct_page(2)['lines']]}
    doc = _doc(tmp_path, settings, [distinct_page(0), distinct_page(1), full, distinct_page(3), distinct_page(4),
                                    distinct_page(5)])
    pages = list(doc.pages.order_by('index'))
    half = _read(witness.of(pages[0]), 0.5)
    OcrRun.objects.create(page=pages[0], engine=HAIKU, variant='columns-1596', text=half)
    OcrRun.objects.create(page=pages[1], engine=HAIKU, variant='page-1596', text=_read(witness.of(pages[1]), 0.5))
    OcrRun.objects.create(page=pages[2], engine=HAIKU, variant='page-1596', text=_read(witness.of(pages[2]), 0.5))
    OcrRun.objects.create(page=pages[3], engine=HAIKU, variant='columns-1596',
                          text='\n'.join(['| البند | المبلغ |'] * 10) + '\n' + _read(witness.of(pages[3])).replace('\n', ' '))
    OcrRun.objects.create(page=pages[4], engine=HAIKU, variant='columns-1596', text=half, stop_reason='end_turn,max_tokens')
    OcrRun.objects.create(page=pages[5], engine=HAIKU, variant='columns-1596', text=half, stop_reason='max_tokens')
    OcrRun.objects.create(page=pages[5], engine=HAIKU, variant='strips-1596', text=half)
    sent = {}
    monkeypatch.setattr(archive, 'render_columns', lambda page, width=0, **kw: None if page.index == 2 else ['c0', 'c1'])
    monkeypatch.setattr(archive, 'ocr_readings_batch',
                        lambda whole, turned, split, model, width, log: sent.update(whole=whole, split=split))
    monkeypatch.setattr(archive, 'ocr_strips_batch',
                        lambda items, model, width, log: sent.update(strips=[(p.index, c) for p, c in items]))
    why = archive.second_readings(list(Page.objects.filter(document=doc).prefetch_related('ocr_runs')), HAIKU, 1.0,
                                  log=lambda s: None)
    assert [p.index for p in sent['whole']] == [0, 3]     # columns in doubt, and a table read in columns: now whole
    assert [p.index for p in sent['split']] == [1]        # whole in doubt: now by columns
    assert sent['strips'] == [(4, True)]                  # cut at the token limit: its columns' halves; page 5 had them
    assert set(why) == {pages[0].pk, pages[1].pk, pages[3].pk, pages[4].pk}   # a full-width page has nothing else


@pytest.mark.django_db
def test_a_page_keeps_the_widest_standing_columns_and_one_that_may_lack_lines_says_so(tmp_path, settings):
    doc = _doc(tmp_path, settings, [distinct_page(0), distinct_page(1), distinct_page(2)])
    first, second, third = doc.pages.order_by('index')
    whole = _read(witness.of(first))
    OcrRun.objects.create(page=first, engine=HAIKU, variant='page-1596', text=whole)
    wide = OcrRun.objects.create(page=first, engine=HAIKU, variant='columns-3192', text=whole + '\nأ')
    OcrRun.objects.create(page=first, engine=HAIKU, variant='columns-1596', text=whole + '\nب')
    OcrRun.objects.create(page=second, engine=HAIKU, variant='columns-1596', text=_read(witness.of(second), 0.3))
    strips = OcrRun.objects.create(page=second, engine=HAIKU, variant='strips-1596', text=_read(witness.of(second), 0.8))
    only = OcrRun.objects.create(page=third, engine=HAIKU, variant='page-1596', text=_read(witness.of(third), 0.5))
    doubts = archive.keep(list(doc.pages.prefetch_related('ocr_runs')), HAIKU, 1.0)
    first.refresh_from_db(), second.refresh_from_db()
    assert first.text == wide.text                       # all stand: the widest columns
    assert second.text == strips.text                    # neither stands: the nearest in letters
    assert [(d['page'], d['reason'], d['run']) for d in doubts] == [(1, 'letters', strips.pk), (2, 'letters', only.pk)]
    assert (first.quality['reading'], second.quality['reading']) == ('scan', 'short')


@pytest.mark.django_db
def test_each_page_gets_one_reading(tmp_path, settings, monkeypatch):
    doc = _doc(tmp_path, settings, [two_columns_page(0), full_width_page(1), {**two_columns_page(2), 'rot': 90}])
    monkeypatch.setattr(archive, 'render_columns', lambda page, width=0, **kw: ['c0', 'c1'])
    whole, turned, split = archive.plan(list(doc.pages.order_by('index')))
    assert ([p.index for p in split], [p.index for p in whole], [p.index for p in turned]) == ([0], [1], [2])


@pytest.mark.django_db
def test_the_folio_of_a_page_read_by_columns_comes_from_tesseracts_head(tmp_path, settings):
    from apps.sources.services.issue import number_pages
    pages = [two_columns_page(i, head=f'عدد 2685 الجريدة الرسمية {1341 + i}') for i in range(4)]
    doc = _doc(tmp_path, settings, pages, key='2685')
    for p in doc.pages.all():
        p.text = WORDS                          # the columns' reading: no running head in it
        p.save()
    assert number_pages(doc.issue) == 1341
    assert list(doc.pages.order_by('index').values_list('printed_number', flat=True)) == [1341, 1342, 1343, 1344]


@pytest.mark.django_db
def test_the_contents_overrule_a_folio_vote_that_puts_their_texts_outside_the_issue(tmp_path, settings):
    # BO 4231: the first pages voted 2255, one folio read 2358, its contents run 2356–2358.
    from apps.sources.services.issue import number_pages
    heads = [f'عدد 4231 الجريدة الرسمية {2255 + i}' for i in range(3)] + ['عدد 4231 الجريدة الرسمية 2358']
    doc = _doc(tmp_path, settings, [two_columns_page(i, head=h) for i, h in enumerate(heads)], key='4231')
    contents = [{'page': p, 'title': 'قرار', 'number_as_printed': ''} for p in (2356, 2357, 2358)]
    assert number_pages(doc.issue) == 2255
    assert number_pages(doc.issue, contents) == 2355
    assert doc.pages.get(index=3).printed_number == 2358


@pytest.mark.django_db
def test_without_a_folio_that_holds_the_contents_their_texts_numbers_place_the_pages(tmp_path, settings):
    from apps.sources.services.issue import number_pages
    doc = _doc(tmp_path, settings, [two_columns_page(i, head=f'الجريدة الرسمية {6 + i}') for i in range(5)], key='4726')
    numbers = {2: '2039.93', 3: '2040.93', 4: '1.93.603'}
    for page in doc.pages.all():
        page.text = f'قرار رقم {numbers[page.index]} صادر في' if page.index in numbers else WORDS
        page.save()
    contents = [{'page': 2355 + i, 'title': 'قرار', 'number_as_printed': n} for i, n in numbers.items()]
    assert number_pages(doc.issue, contents) == 2355
    # A third found on their very pages is enough when no folio holds the contents (31 Oct 2026); fewer: the vote.
    contents[0]['number_as_printed'] = contents[1]['number_as_printed'] = '9999.93'
    assert number_pages(doc.issue, contents) == 2355
    contents += [{'page': 2360 + i, 'title': 'قرار', 'number_as_printed': f'99{i}.93'} for i in range(3)]
    assert number_pages(doc.issue, contents) == 6


@pytest.mark.django_db
def test_a_laws_contents_entry_pairs_two_numbers_and_the_dahirs_is_the_one_printed(tmp_path, settings):
    # BO 4798: «1.00.200 / 04.00» found nowhere, its folios kept at 2 for 1181, its ten texts lost.
    from apps.sources.services.issue import number_pages
    doc = _doc(tmp_path, settings, [two_columns_page(i, head=f'الجريدة الرسمية {2 + i}') for i in range(6)], key='4798')
    printed = {2: '1.00.200', 3: '1.00.201', 4: '1.00.203'}
    listed = {2: '1.00.200 / 04.00', 3: '1.00.201 / 05.00', 4: 'ظهير شريف رقم 1.00.203 / قانون رقم 07.00'}
    for page in doc.pages.all():
        page.text = f'ظهير شريف رقم {printed[page.index]} صادر في' if page.index in printed else WORDS
        page.save()
    contents = [{'page': 1181 + i, 'title': 'ظهير', 'number_as_printed': n} for i, n in listed.items()]
    assert number_pages(doc.issue, contents) == 1181


@pytest.mark.django_db
def test_a_folio_vote_that_holds_most_of_the_contents_gives_way_to_one_that_finds_their_texts(tmp_path, settings):
    # BO 5398: the folios voted 482, its contents run 490–514 over 30 pages, its first text on the fourth page (487).
    from apps.sources.services.issue import number_pages
    doc = _doc(tmp_path, settings, [two_columns_page(i, head=f'الجريدة الرسمية {10 + i}') for i in range(8)], key='5398')
    numbers = {2: '1.06.07', 3: '1.06.12', 4: '2.05.1585', 5: '2.06.43'}
    for page in doc.pages.all():
        page.text = f'ظهير شريف رقم {numbers[page.index]} صادر في' if page.index in numbers else WORDS
        page.save()
    contents = [{'page': 13 + i, 'title': 'ظهير', 'number_as_printed': n} for i, n in numbers.items()]
    assert number_pages(doc.issue, contents) == 13


def test_a_claim_is_one_workers_and_a_dead_ones_is_taken_over(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    assert archive.claim('read', '2685')
    assert not archive.claim('read', '2685')
    (archive.root() / 'state' / 'read' / '2685.claim').write_text(f'{__import__("socket").gethostname()} 999999 x')
    assert archive.claim('read', '2685')
    archive.release('read', '2685')
    archive.mark('read', '2685', 'done')
    assert archive.done('read', '2685')
    (archive.root() / 'STOP').write_text('an operator')
    assert archive.stopped() == 'STOP: an operator'


@pytest.mark.django_db
def test_an_appended_ledger_is_counted_as_it_grows(tmp_path, settings):
    from apps.corpus.services import llm
    from apps.sources.services import ocr
    settings.CORPUS_DIR = tmp_path
    settings.LLM_LEDGER = 'reports/llm_ledger.jsonl'
    llm._append_to_ledger([{'kind': 'toc:1', 'cost_usd': 0.25}, {'kind': 'toc:2', 'cost_usd': 0.5}])
    assert ocr.spent() == Decimal('0.75')
    llm._append_to_ledger([{'kind': 'texts:1', 'cost_usd': 0.125}])
    assert ocr.spent() == Decimal('0.875')
    with open(tmp_path / 'reports' / 'llm_ledger.jsonl', 'a') as f:
        f.write('{"kind": "half-writ')                  # another process mid-line: not counted yet
    assert ocr.ledger_total() == Decimal('0.875')
    assert [e['kind'] for e in llm.ledger()[:3]] == ['toc:1', 'toc:2', 'texts:1']


def _plan(tmp_path, keys):
    folder = tmp_path / 'archive'
    folder.mkdir(exist_ok=True)
    (folder / 'plan.json').write_text(json.dumps({'pilot': [], 'issues': [
        {'key': k, 'year': 1964, 'date': '1964-03-11', 'url': '', 'path': f'1964/BO_{k}_Ar.pdf'} for k in keys]}))


def test_the_queue_counts_the_plan_from_its_coverage_day(tmp_path, settings):
    """H10 of the Bulletin-from-No.-1 review: the years before 1956 join the coverage line only once the plan says so."""
    from django.core.management import call_command
    settings.CORPUS_DIR = tmp_path
    folder = tmp_path / 'archive'
    folder.mkdir()
    issues = [{'key': '5', 'year': 1913, 'date': '1913-06-06', 'url': '', 'path': '1913/BO_5_Ar.pdf'},
              {'key': '2254', 'year': 1956, 'date': '1956-01-06', 'url': '', 'path': '1956/BO_2254_Ar.pdf'}]
    queue = tmp_path / 'reports' / 'runs' / 'queue_1956_2018.txt'
    (folder / 'plan.json').write_text(json.dumps({'pilot': [], 'issues': issues}))
    call_command('archive', 'queue', stdout=open('/dev/null', 'w'))
    assert queue.read_text() == '2254 1956-01-06 archive\n'
    (folder / 'plan.json').write_text(json.dumps({'pilot': [], 'coverage_from': '1913-01-01', 'issues': issues}))
    call_command('archive', 'queue', stdout=open('/dev/null', 'w'))
    assert queue.read_text() == '5 1913-06-06 archive\n2254 1956-01-06 archive\n'


def _fake_readings(monkeypatch, contents_pages=2):
    """Haiku replaced: a page read whole or by columns gets the issue's contents on its first pages, words after."""
    def batch(whole, turned, split, model, width=3192, log=print):
        for page in whole + turned + split:
            text = ('\n'.join(f'مرسوم رقم 2.64.{n} بتغيير القرار الوزيري .......... {1341 + n}' for n in range(20))
                    if page.index < contents_pages else _read(witness.of(page)))
            variant = 'columns-3192' if page in split else 'page-1596'
            OcrRun.objects.create(page=page, engine=HAIKU, variant=variant, prompt_version='v1', text=text,
                                  cost_usd=Decimal('0.001'))
    monkeypatch.setattr(archive, 'ocr_readings_batch', batch)
    monkeypatch.setattr(archive, 'ocr_strips_batch', lambda items, model, width, log: [])
    monkeypatch.setattr(archive, 'render_columns', lambda page, width=0, **kw: ['c0', 'c1'])
    monkeypatch.setattr('apps.sources.services.render.is_sideways', lambda page: False)


@pytest.mark.django_db
def test_the_catalog_and_the_reading_take_a_chunk_of_issues_one_batch_a_step(tmp_path, settings, monkeypatch):
    from django.core.management import call_command
    from apps.corpus.services import llm
    pages = [two_columns_page(i, head=f'عدد 2685 الجريدة الرسمية {1341 + i}') for i in range(6)]
    _doc(tmp_path, settings, pages, stem='BO_2685_Ar', key='2685')
    _doc(tmp_path, settings, [{**p} for p in pages], stem='BO_2686_Ar', key='2686')
    _plan(tmp_path, ['2685', '2686'])
    _fake_readings(monkeypatch)
    sent = []

    def run_batch(kind, requests, **kw):
        sent.append((kind, len(requests)))
        return {r['custom_id']: {'data': {'entries': [
            {'section': 'general', 'rubric': '', 'type': 'decree', 'number_as_printed': '2.64.1',
             'title': 'مرسوم رقم 2.64.1', 'signed_on_gregorian': '', 'signed_on_hijri': '', 'page': 1343}]},
            'stop': 'end_turn', 'error': ''} for r in requests}
    monkeypatch.setattr(llm, 'run_batch', run_batch)
    call_command('archive', 'work', 'catalog', chunk=2, stdout=open('/dev/null', 'w'))
    assert sent == [('toc:2685+1', 2)]                       # one contents batch for the chunk
    assert archive.done('catalog', '2685') and archive.done('catalog', '2686')
    assert json.loads((tmp_path / 'reports' / 'issues' / '2685' / 'toc.json').read_text())[0]['page'] == 1343
    sent.clear()
    call_command('archive', 'work', 'read', chunk=2, stdout=open('/dev/null', 'w'))
    assert archive.done('read', '2685') and archive.done('read', '2686')
    issue = Issue.objects.get(number=2685)
    assert issue.first_page_number == 1341                    # the folio from Tesseract's head lines
    assert all(p.text for p in issue.document.pages.all())
    assert not (tmp_path / 'reports' / 'issues' / '2686' / 'texts.json').exists()    # the texts step waits
    call_command('archive', 'work', 'texts', chunk=2, stdout=open('/dev/null', 'w'))
    assert archive.done('texts', '2685') and archive.done('texts', '2686')
    assert (tmp_path / 'reports' / 'issues' / '2686' / 'texts.json').exists()
    assert [k for k, _ in sent if k.startswith('texts')] in ([], ['texts:2685+1'])


@pytest.mark.django_db
def test_an_issue_whose_pages_a_cancelled_batch_left_unread_is_set_aside_and_never_done(tmp_path, settings, monkeypatch):
    from django.core.management import call_command
    from apps.corpus.services import llm
    pages = [two_columns_page(i, head=f'عدد 2685 الجريدة الرسمية {1341 + i}') for i in range(6)]
    _doc(tmp_path, settings, pages, stem='BO_2685_Ar', key='2685')
    _doc(tmp_path, settings, [{**p} for p in pages], stem='BO_2686_Ar', key='2686')
    _plan(tmp_path, ['2685', '2686'])
    _fake_readings(monkeypatch)
    monkeypatch.setattr(llm, 'run_batch', lambda kind, requests, **kw: {r['custom_id']: {'data': {'entries': []},
                        'stop': 'end_turn', 'error': ''} for r in requests})
    call_command('archive', 'work', 'catalog', chunk=2, stdout=open('/dev/null', 'w'))
    batch = archive.ocr_readings_batch
    monkeypatch.setattr(archive, 'ocr_readings_batch', lambda whole, turned, split, model, **kw: batch(
        *[[p for p in group if p.document.issue.number != 2686] for group in (whole, turned, split)], model, **kw))
    call_command('archive', 'work', 'read', chunk=2, stdout=open('/dev/null', 'w'))
    assert archive.done('read', '2685') and not archive.done('read', '2686')
    assert 'left unread' in (archive.root() / 'state' / 'read' / '2686.error').read_text()


@pytest.mark.django_db
def test_a_failing_chunk_is_set_aside_and_offered_again(tmp_path, settings, monkeypatch):
    from django.core.management import call_command
    from apps.corpus.services import llm
    _doc(tmp_path, settings, [two_columns_page(i) for i in range(3)], stem='BO_2685_Ar', key='2685')
    _plan(tmp_path, ['2685'])
    _fake_readings(monkeypatch)

    def broken(kind, requests, **kw):
        raise RuntimeError('the API answered 529')
    monkeypatch.setattr(llm, 'run_batch', broken)
    call_command('archive', 'work', 'catalog', stdout=open('/dev/null', 'w'))
    error = archive.root() / 'state' / 'catalog' / '2685.error'
    assert 'the API answered 529' in error.read_text() and not archive.done('catalog', '2685')
    assert not (archive.root() / 'state' / 'catalog' / '2685.claim').exists()
    call_command('archive', 'retry', 'catalog', stdout=open('/dev/null', 'w'))
    assert not error.exists()


@pytest.mark.django_db
def test_an_issue_read_on_another_machine_comes_back_here_whole_and_only_once(tmp_path, settings):
    from django.core.management import call_command
    from PIL import Image
    from apps.sources.services import issue as issue_service
    settings.CORPUS_DIR = tmp_path / 'there'
    pdfs = tmp_path / 'pdfs' / '1964'
    pdfs.mkdir(parents=True)
    Image.new('L', (600, 800), 255).save(pdfs / 'BO_2685_Ar.pdf', 'PDF', save_all=True,
                                         append_images=[Image.new('L', (600, 800), 255)])
    link = tmp_path / 'there' / 'issues' / 'bo_ar' / 'BO_2685_ar.pdf'
    link.parent.mkdir(parents=True)
    link.symlink_to(pdfs / 'BO_2685_Ar.pdf')
    issue = issue_service.register(link, edition=Edition.GENERAL_AR, number=2685, day=date(1964, 3, 11))
    issue.document.meta = {'archive': '1964/BO_2685_Ar.pdf'}
    issue.document.save()
    for page in issue.document.pages.all():
        page.text, page.printed_number = f'الصفحة {page.index}', 1341 + page.index
        page.save()
        OcrRun.objects.create(page=page, engine=HAIKU, variant='columns-3192', text=page.text, batch_id='msgbatch_1',
                              cost_usd=Decimal('0.0009'), input_tokens=8000, output_tokens=1800)
    Issue.objects.filter(pk=issue.pk).update(first_page_number=1341)
    archive.mark('read', '2685', 'done')
    work = tmp_path / 'there' / 'reports' / 'issues' / '2685'
    work.mkdir(parents=True)
    (work / 'toc.json').write_text('[{"page": 1341}]')
    _plan(tmp_path / 'there', ['2685'])
    call_command('archive', 'export', out=str(tmp_path / 'out'), stdout=open('/dev/null', 'w'))
    Issue.objects.all().delete()
    Document.objects.all().delete()

    settings.CORPUS_DIR = tmp_path / 'here'
    for _ in range(2):
        call_command('archive', 'import', folder=str(tmp_path / 'out'), pdfs=str(tmp_path / 'pdfs'),
                     stdout=open('/dev/null', 'w'))
    issue = Issue.objects.get(number=2685)
    assert issue.first_page_number == 1341 and issue.document.meta['archive'] == '1964/BO_2685_Ar.pdf'
    assert list(issue.document.pages.order_by('index').values_list('text', 'printed_number')) == [
        ('الصفحة 0', 1341), ('الصفحة 1', 1342)]
    assert OcrRun.objects.count() == 2                       # imported twice, added once
    assert OcrRun.objects.first().cost_usd == Decimal('0.0009')
    assert json.loads((tmp_path / 'here' / 'reports' / 'issues' / '2685' / 'toc.json').read_text()) == [{'page': 1341}]


@pytest.mark.django_db
def test_an_issue_whose_contents_cannot_be_read_fails_alone_and_its_chunk_is_kept(tmp_path, settings, monkeypatch):
    from django.core.management import call_command
    from apps.corpus.services import llm
    pages = [two_columns_page(i, head=f'عدد 2685 الجريدة الرسمية {1341 + i}') for i in range(4)]
    _doc(tmp_path, settings, pages, stem='BO_2685_Ar', key='2685')
    _doc(tmp_path, settings, [{**p} for p in pages], stem='BO_6695_Ar', key='6695')
    _plan(tmp_path, ['2685', '6695'])
    _fake_readings(monkeypatch)
    kinds = []

    def run_batch(kind, requests, **kw):
        kinds.append(kind)
        entry = {'section': 'general', 'rubric': '', 'type': 'decree', 'number_as_printed': '2.64.1', 'title': 'مرسوم',
                 'signed_on_gregorian': '', 'signed_on_hijri': '', 'page': 1342}
        return {r['custom_id']: ({'data': None, 'stop': 'max_tokens', 'error': 'not JSON'} if '6695' in r['custom_id']
                                 else {'data': {'entries': [entry]}, 'stop': 'end_turn', 'error': ''}) for r in requests}
    monkeypatch.setattr(llm, 'run_batch', run_batch)
    call_command('archive', 'work', 'catalog', chunk=2, stdout=open('/dev/null', 'w'))
    assert archive.done('catalog', '2685')                    # its contents kept although 6695 failed
    assert 'eighths' in (archive.root() / 'state' / 'catalog' / '6695.error').read_text()
    assert kinds == ['toc:2685+1', 'toc:6695/2', 'toc:6695/4', 'toc:6695/8']


@pytest.mark.django_db
def test_a_page_registered_blank_is_read_unless_tesseract_saw_nothing_on_it(tmp_path, settings):
    doc = _doc(tmp_path, settings, [two_columns_page(0), {'i': 1, 'w': 1400, 'h': 1800, 'rot': 0, 'lines': []},
                                    two_columns_page(2)])
    Page.objects.filter(document=doc).update(kind=PageKind.BLANK)    # pdfium saw no image: a form object holds it
    pages = list(doc.pages.order_by('index'))
    assert [p.index for p in archive.unread(pages, HAIKU)] == [0, 2]


@pytest.mark.django_db
def test_the_reading_order_puts_first_the_issues_holding_a_text_the_corpus_cites(tmp_path, settings):
    from django.core.management import call_command
    settings.CORPUS_DIR = tmp_path
    _plan(tmp_path, ['3600', '3601', '3602'])
    for key, title in (('3600', 'قرار لوزير المالية رقم 12.82'), ('3601', 'ظهير شريف رقم 1.81.254 بتنفيذ القانون رقم 7.81'),
                       ('3602', 'مرسوم رقم 2.82.5')):
        work = tmp_path / 'reports' / 'issues' / key
        work.mkdir(parents=True)
        kind = {'3600': 'order', '3601': 'law', '3602': 'decree'}[key]
        (work / 'toc.json').write_text(json.dumps([{'type': kind, 'number_as_printed': '', 'title': title, 'section': 'general'}]))
    (tmp_path / 'missing.json').write_text(json.dumps({'/akn/ma/act/dahir/1-81-254': 146}))
    call_command('archive', 'order', missing=str(tmp_path / 'missing.json'), stdout=open('/dev/null', 'w'))
    assert json.loads((archive.root() / 'order.json').read_text()) == ['3601', '3602', '3600']


@pytest.mark.django_db
def test_a_day_tesseract_read_in_the_head_never_numbers_a_page_below_one(tmp_path, settings):
    # BO 6566: the only number in the heads was a day on the third page, which made the first page −1.
    from apps.sources.services.issue import number_pages
    pages = [two_columns_page(i, head='الجريدة الرسمية') for i in range(2)] + [two_columns_page(2, head='عدد 6566 1 ش')]
    doc = _doc(tmp_path, settings, pages, key='6566')
    assert number_pages(doc.issue) is None
    assert not doc.pages.filter(printed_number__isnull=False).exists()


@pytest.mark.django_db
def test_an_issue_read_here_before_keeps_its_pages_and_files_on_import(tmp_path, settings):
    """28 Oct 2026: the development database held 27 pre-2019 issues already read (some put right against their
    pages); the archive's import adds the archive run's readings to them as witnesses and changes nothing else."""
    from django.core.management import call_command
    doc = _doc(tmp_path, settings, [two_columns_page(0)], key='2685')
    page = doc.pages.get()
    page.text, page.text_source, page.printed_number = 'قرئت هنا وصححت', 'ocr', 1341
    page.save()
    work = tmp_path / 'reports' / 'issues' / '2685'
    work.mkdir(parents=True)
    (work / 'texts.json').write_text('["here"]')
    run = {'engine': HAIKU, 'variant': 'columns-1596', 'prompt_version': '', 'image_px': '', 'input_tokens': 1,
           'output_tokens': 1, 'batch_id': 'b1', 'stop_reason': 'end_turn', 'seconds': None, 'text': 'من بنملال',
           'cost_usd': '0.001', 'created_at': timezone.now().isoformat()}
    bundle = {'key': '2685', 'phase': 'texts',
              'issue': {'number': 2685, 'suffix': '', 'date': '1964-03-11', 'hijri_date': '', 'first_page_number': 9},
              'document': {'sha256': doc.sha256, 'url': '', 'archive': '1964/BO_2685_Ar.pdf', 'page_count': 1},
              'pages': [{'index': 0, 'printed_number': 9, 'text': 'من بنملال', 'text_source': 'ocr', 'quality': None,
                         'runs': [run]}],
              'files': {'texts.json': ['there']}, 'doubts': []}
    folder = tmp_path / 'export'
    folder.mkdir()
    with gzip.open(folder / '2685.json.gz', 'wt', encoding='utf-8') as f:
        json.dump(bundle, f)
    call_command('archive', 'import', folder=str(folder), pdfs=str(tmp_path))
    page.refresh_from_db()
    assert (page.text, page.printed_number) == ('قرئت هنا وصححت', 1341)
    assert json.loads((work / 'texts.json').read_text()) == ['here']
    assert OcrRun.objects.filter(page=page, batch_id='b1').count() == 1


def test_a_page_is_cut_in_halves_between_two_lines():
    from PIL import Image, ImageDraw
    from apps.sources.services.render import _halves
    image = Image.new('L', (400, 1000), 255)
    draw = ImageDraw.Draw(image)
    for top in range(20, 980, 30):            # a line every 30 px
        draw.rectangle((20, top, 380, top + 18), fill=0)
    upper, lower = _halves(image)
    y = upper.size[1]
    assert 470 <= y <= 530 and y + lower.size[1] == 1000                 # near the middle
    assert min(image.crop((0, y - 2, 400, y + 2)).get_flattened_data()) == 255       # between two lines


def test_what_a_page_holds_is_known_from_the_contents():
    from apps.corpus.management.commands.archive import kind_of
    assert kind_of({'section': 'general', 'type': 'decision', 'title': 'قرار'}) == 0
    assert kind_of({'section': 'special', 'type': 'dahir', 'title': 'ظهير'}) == 0           # legislation
    assert kind_of({'section': 'other', 'type': 'other', 'rubric': 'المجلس الدستوري', 'title': 'قرار رقم 93-12'}) == 0
    assert kind_of({'section': 'special', 'type': 'order', 'title': 'قرار لوزير'}) == 1
    assert kind_of({'section': 'special', 'type': 'decision', 'title': 'قرار بتعيين'}) == 2
    assert kind_of({'section': 'other', 'type': 'other', 'rubric': 'اعلانات وبلاغات', 'title': 'بلاغ'}) == 3


@pytest.mark.django_db
def test_reading_by_kind_takes_a_texts_pages_and_the_one_after(tmp_path, settings):
    """Z18: laws first; a text's pages run from its own to the next text's, and one more in case it runs on."""
    from apps.corpus.management.commands.archive import Command
    _doc(tmp_path, settings, [two_columns_page(i, head=f'عدد 2685 الجريدة الرسمية {1341 + i}') for i in range(10)],
         key='2685')
    Issue.objects.filter(number=2685).update(first_page_number=1341)
    work = tmp_path / 'reports' / 'issues' / '2685'
    work.mkdir(parents=True)
    (work / 'toc.json').write_text(json.dumps([
        {'section': 'general', 'type': 'decree', 'title': 'مرسوم', 'page': 1342},
        {'section': 'special', 'type': 'decision', 'title': 'قرار بتعيين', 'page': 1344},
        {'section': 'special', 'type': 'order', 'title': 'قرار لوزير', 'page': 1347},
        {'section': 'other', 'type': 'other', 'rubric': 'اعلانات وبلاغات', 'title': 'بلاغ', 'page': 1349}]))
    command = Command()
    issue = Issue.objects.select_related('document').get(number=2685)
    for only, indexes in (('general', [0, 1, 2, 3, 4]), ('rules', [0, 1, 2, 3, 4, 6, 7, 8, 9]),
                          ('decisions', [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])):
        command.only = only
        assert [p.index for p in command.pages_for(issue)] == indexes, only


@pytest.mark.django_db
def test_before_1956_the_official_texts_pages_end_where_the_non_official_part_starts(tmp_path, settings):
    """The Bulletin-from-No.-1 review: the contents leave out the notices; Tesseract's «القسم الغير الرسمي» heading, past the
    contents (which name it too), ends the last official text's pages."""
    from apps.corpus.management.commands.archive import Command
    assert witness._unofficial('نز القسم الغير الرسمي :#-') and witness._unofficial('القسم التي الرسبي 6ه')
    assert not witness._unofficial('((( القسم الرسمي ))) ست')
    pages = [two_columns_page(i, head=f'عدد 894 الجريدة الرسمية {2685 + i}') for i in range(10)]
    pages[0]['lines'].append([60, 900, 600, 930, 'اسع القسم الفير الرسمي عم', 90])      # the contents name it
    pages[6]['lines'].append([60, 900, 600, 930, 'القسم الغير الرسمى', 90])            # the part starts here
    _doc(tmp_path, settings, pages, stem='BO_894_Ar', key='894')
    Issue.objects.filter(number=894).update(date=date(1929, 12, 13), first_page_number=2685)
    work = tmp_path / 'reports' / 'issues' / '894'
    work.mkdir(parents=True)
    (work / 'toc.json').write_text(json.dumps([
        {'section': 'general', 'type': 'dahir', 'title': 'ظهير شريف', 'page': 2686},
        {'section': 'special', 'type': 'order', 'title': 'قرار وزيري', 'page': 2688}]))
    issue = Issue.objects.select_related('document').get(number=894)
    assert witness.unofficial_from(issue.document) == 6
    command = Command()
    command.only = 'rules'
    assert [p.index for p in command.pages_for(issue)] == [0, 1, 2, 3, 4, 5, 6, 7]
    command.only = 'notices'
    assert len(command.pages_for(issue)) == 10


@pytest.mark.django_db
def test_before_1956_an_issue_printing_a_date_the_corpus_cites_a_text_by_is_read_first(tmp_path, settings):
    """H4 of the Bulletin-from-No.-1 review: an old text is cited by its date; the issue whose pages print it, within 180 days
    after it, comes first."""
    from django.core.management import call_command
    page = full_width_page(0)
    page['lines'].append([60, 900, 1300, 930, 'وحرر بالرباط في 9 رمضان 1331 الموافق 12 غشت سنة 1913', 90])
    _doc(tmp_path, settings, [page], stem='BO_46_Ar', key='46')
    _doc(tmp_path, settings, [full_width_page(0)], stem='BO_47_Ar', key='47')
    Issue.objects.filter(number__in=[46, 47]).update(date=date(1913, 9, 12))
    folder = tmp_path / 'archive'
    folder.mkdir(exist_ok=True)
    (folder / 'plan.json').write_text(json.dumps({'pilot': [], 'issues': [
        {'key': k, 'year': 1913, 'date': '1913-09-12', 'url': '', 'path': f'1913/BO_{k}_Ar.pdf'} for k in ('47', '46')]}))
    cited = tmp_path / 'cited.json'
    cited.write_text(json.dumps({'dahir:1913-08-12': 1548, 'dahir:1914-07-01': 185}))
    call_command('archive', 'order', cited_dates=str(cited), stdout=open('/dev/null', 'w'))
    assert json.loads((folder / 'order.json').read_text()) == ['46', '47']


def test_a_special_text_is_described_by_code_from_its_contents_entry_and_its_lines():
    """Z19, on BO 3086's order 708.71 as Haiku described it on 28 Oct 2026."""
    from apps.corpus.services.issue_structure import describe_by_code
    entry = {'section': 'special', 'type': 'decision', 'number_as_printed': '708.71', 'page': 1520,
             'title': 'قرار لوزير المالية رقم 708.71 بتاريخ 30 يونيه 1971 بتحديد القيمة المسترجعة بها سندات القرض',
             'signed_on_gregorian': '1971-06-30', 'signed_on_hijri': ''}
    front = ('قرار لوزير المالية رقم 708.71 بتاريخ 30 يونيه 1971 بتحديد القيمة المسترجع بها سندات القرض.\n'
             'ان وزير المالية ،\n'
             'بمقتضى الظهير الشريف الصادر في 29 ذي الحجة 1371 (20 شتنبر 1952) بالاذن للحكومة في اصدار قروض ؛\n'
             'وبناء على الفصل الخامس من القرار الصادر في 26 شتنبر 1952 بتحديد شروط اصدار قرض\n'
             'مضمون رأس ماله بما قدره 4 1/2 في المائة ؛\n'
             'يقرر ما يلي :')
    tail = 'وحرر بالرباط في 30 يونيه 1971\nوزير المالية ،\nالامضاء : محمد كريم العمراني.'
    data = describe_by_code(entry, front, tail)
    assert data['authority'] == 'وزير المالية'
    assert data['preamble'] == [
        'بمقتضى الظهير الشريف الصادر في 29 ذي الحجة 1371 (20 شتنبر 1952) بالاذن للحكومة في اصدار قروض',
        'وبناء على الفصل الخامس من القرار الصادر في 26 شتنبر 1952 بتحديد شروط اصدار قرض مضمون رأس ماله بما قدره 4 1/2 في المائة']
    assert (data['closing'], data['signatories']) == ('وحرر بالرباط في 30 يونيه 1971', ['محمد كريم العمراني (وزير المالية)'])
    assert (data['found'], data['number_as_printed'], data['signed_on_gregorian']) == (True, '708.71', '1971-06-30')


def test_an_old_text_signed_in_hijri_and_gregorian_is_sure_of_its_day_by_code():
    """The Bulletin-from-No.-1 review: before 1956 a text signs «… عام 1352 الموافق 29 شتنبر سنة 1933», and has no number."""
    from apps.corpus.services.issue_structure import describe_by_code
    entry = {'section': 'special', 'type': 'order', 'number_as_printed': '', 'page': 1781,
             'title': 'قرار وزيري في تحديد ثمن الملح', 'signed_on_gregorian': '', 'signed_on_hijri': ''}
    front = 'قرار وزيري في تحديد ثمن الملح\nان الصدر الاعظم ،\nبعد الاطلاع على الظهير الشريف الصادر في 9 رمضان 1331 ؛\nقرر ما يلي :'
    tail = 'وحرر بالرباط في 8 جمادى الثانية عام 1352 الموافق 29 شتنبر سنة 1933\nمحمد المقري'
    data = describe_by_code(entry, front, tail)
    assert (data['sure'], data['signed_on_gregorian'], data['number_as_printed']) == (True, '1933-09-29', '')


def test_the_contents_and_texts_steps_know_the_old_bulletin_before_1956():
    from apps.corpus.services.issue_structure import TEXT_SYSTEM, TOC_SYSTEM, text_system, toc_system
    old, new = Issue(number=1097, date=date(1933, 11, 3)), Issue(number=4000, date=date(1989, 6, 7))
    assert toc_system(new) == TOC_SYSTEM and text_system(new) == TEXT_SYSTEM
    assert 'القسم الغير الرسمي' in toc_system(old) and 'قرار وزيري' in text_system(old)


def test_the_texts_step_keeps_a_description_already_paid_and_describes_special_texts_by_code(monkeypatch):
    """Z17 and Z19: an issue cut again after its pages were read again keeps the descriptions it had; a text newly
    found is sent; a special one is described by code."""
    from types import SimpleNamespace
    from apps.corpus.management.commands.archive import kind_of
    from apps.corpus.services import issue_structure as s
    lines = [(1, 'مرسوم رقم 2.70.1'), (1, 'المادة الأولى'),
             (2, 'قرار لوزير الفلاحة رقم 12.70 بتاريخ 3 مارس 1970'), (2, 'ان وزير الفلاحة ،'),
             (3, 'مرسوم رقم 2.70.3'), (3, 'المادة الأولى'), (4, 'بلاغ'), (4, 'نص'),
             (5, 'قرار لوزير الفلاحة رقم 13.70'), (5, 'المادة الأولى')]
    monkeypatch.setattr(s.texts, 'issue_lines', lambda issue: lines)          # where texts_requests looks them up
    monkeypatch.setattr(s.texts, 'segment_issue', lambda issue, toc: [(0, 2), (2, 4), (4, 6), (6, 8), (8, 10)])
    toc = [{'section': 'general', 'type': 'decree', 'title': 'مرسوم رقم 2.70.1', 'page': 1},
           {'section': 'special', 'type': 'order', 'title': 'قرار لوزير الفلاحة رقم 12.70', 'page': 2,
            'signed_on_gregorian': '1970-03-03', 'number_as_printed': '12.70'},
           {'section': 'general', 'type': 'decree', 'title': 'مرسوم رقم 2.70.3', 'page': 3},
           {'section': 'other', 'type': 'other', 'title': 'بلاغ', 'page': 4},
           {'section': 'special', 'type': 'order', 'title': 'قرار لوزير الفلاحة رقم 13.70', 'page': 5,
            'signed_on_gregorian': '', 'number_as_printed': '13.70'}]
    before = [{'toc': toc[0], 'data': {'found': True, 'paid': 1}, 'stop': 'end_turn'},
              {'toc': toc[2], 'data': None, 'stop': 'not_found'}]
    requests, items = s.texts_requests(SimpleNamespace(), toc, 'claude-haiku-5-5', log=lambda m: None, prefix='k-',
                                       only=lambda e: kind_of(e) == 0, by_code=lambda e: kind_of(e) in (1, 2),
                                       before=before)
    assert [r['custom_id'] for r in requests] == ['k-t2', 'k-t4']   # newly found; a special text with no day printed
    assert [t['stop'] for t in items] == ['end_turn', 'code', '', 'later', '']
    assert items[0]['data'] == {'found': True, 'paid': 1} and items[0]['articles']    # kept, cut again
    assert items[1]['data']['authority'] == 'وزير الفلاحة' and items[1]['data']['by'] == 'code'


@pytest.mark.django_db
def test_a_french_issue_of_a_travels_with_its_pages_and_readings_and_never_touches_the_arabic_of_its_number(tmp_path, settings):
    """A of the Bulletin-from-No.-1 review (1 Nov 2026): a translated text opens its French page anywhere, so the French
    issues go out with their folios and readings (`export --french`), as the Arabic ones do."""
    from django.core.management import call_command
    arabic = _doc(tmp_path, settings, [two_columns_page(0)], key='190')
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='f' * 64, path='issues/bo_fr/BO_190_fr.pdf',
                                  mime='application/pdf', language='fr', bytes=1, fetched_at=timezone.now(), page_count=1)
    page = Page.objects.create(document=doc, index=0, kind=PageKind.SCAN, layer_letters=0, printed_number=589,
                               text='ARRÊTÉ RÉSIDENTIEL', text_source='ocr')
    Issue.objects.create(edition=Edition.TRANSLATION_FR, number=190, date=date(1916, 6, 12), document=doc)
    OcrRun.objects.create(page=page, engine=HAIKU, variant='whole', batch_id='f1', text='ARRÊTÉ RÉSIDENTIEL', cost_usd=0.001)
    out = tmp_path / 'out'
    call_command('archive', 'export', french=True, keys='190', out=str(out), stdout=open('/dev/null', 'w'))
    with gzip.open(out / '190.json.gz', 'rt', encoding='utf-8') as f:
        bundle = json.load(f)
    assert bundle['edition'] == Edition.TRANSLATION_FR and bundle['files'] == {} and not bundle['doubts']
    assert bundle['document']['sha256'] == 'f' * 64 and bundle['pages'][0]['printed_number'] == 589
    Page.objects.filter(pk=page.pk).update(printed_number=None, text='', text_source='')     # registered, never read
    OcrRun.objects.filter(page=page).delete()
    call_command('archive', 'import', folder=str(out), pdfs=str(tmp_path), stdout=open('/dev/null', 'w'))
    page.refresh_from_db()
    assert (page.printed_number, page.text) == (589, 'ARRÊTÉ RÉSIDENTIEL') and page.ocr_runs.count() == 1
    assert not arabic.pages.get().text and not (tmp_path / 'reports' / 'issues' / '190' / 'texts.json').exists()
