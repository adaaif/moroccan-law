from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.sources.models import PageKind
from apps.sources.services import ocr
from apps.sources.services.compare import fold, scores, word_f1
from apps.sources.services.ingest import classify


@pytest.mark.parametrize('letters, has_image, kind', [
    (1500, False, PageKind.TEXT_LAYER),
    (1500, True, PageKind.TEXT_LAYER),
    (0, True, PageKind.SCAN),
    (60, True, PageKind.MIXED),
    (0, False, PageKind.BLANK),
])
def test_a_page_is_classified_by_its_text_layer_and_images(letters, has_image, kind):
    assert classify(letters, has_image) == kind


def test_fold_unifies_arabic_spellings_digits_and_markup():
    assert fold('## المادةُ ٨ — «أ) النصوص»') == fold('المادة 8 ا) النصوص')
    assert fold('Article 8 : a. aux TEXTES') == 'article 8 a aux textes'


def test_the_lam_alef_blind_fold_forgives_the_text_layers_ligature_order():
    layer, printed = 'نوع االعتماد مجال األنشطة', 'نوع الاعتماد مجال الأنشطة'
    assert scores(layer, printed)['cer'] > 0
    assert scores(layer, printed, lam_alef_blind=True)['cer'] == 0


def test_word_f1_ignores_the_order_columns_were_read_in():
    assert word_f1('a b c d', 'c d a b') == 1.0
    assert word_f1('a b c d', 'a b') == pytest.approx(2 / 3)


def test_price_follows_the_usage_and_halves_on_the_batch_api():
    usage = SimpleNamespace(input_tokens=4600, output_tokens=2000, cache_creation_input_tokens=0)
    standard = ocr.price('claude-sonnet-5-5', usage, batch=False)
    assert standard == Decimal('0.0292')
    assert ocr.price('claude-sonnet-5-5', usage, batch=True) == standard / 2


@pytest.mark.django_db
def test_a_batch_that_could_pass_the_budget_is_refused(settings, tmp_path):
    settings.OCR_BUDGET_USD = 1.0
    settings.CORPUS_DIR = tmp_path      # the real structuring ledger is not this test's spending
    with pytest.raises(ocr.OverBudget):
        with ocr.reserve('opus', ocr._worst_case('claude-opus-5-5', 200, 8000, batch=True)):
            pass
    with ocr.reserve('haiku', ocr._worst_case('claude-haiku-5-5', 10, 8000, batch=True)):
        pass


@pytest.mark.django_db
def test_batches_out_in_other_workers_count_against_the_budget(settings, tmp_path):
    """Two workers that each fit under the budget cannot pass it together: while the first one's batch is out,
    the second is refused; once its cost is in, the hold goes. A killed worker's hold does not count."""
    import json

    settings.OCR_BUDGET_USD = 1.0
    settings.CORPUS_DIR = tmp_path
    with ocr.reserve('first', Decimal('0.6')):
        assert ocr.in_flight() == Decimal('0.6')
        with pytest.raises(ocr.OverBudget):
            with ocr.reserve('second', Decimal('0.6')):
                pass
    assert ocr.in_flight() == 0
    (tmp_path / 'reports' / 'inflight.json').write_text(json.dumps({'gone': {'worst': '0.9', 'pid': 999_999_999, 'what': 'x'}}))
    with ocr.reserve('after a crash', Decimal('0.6')):
        assert ocr.in_flight() == Decimal('0.6')


def test_requests_past_the_byte_cap_go_as_batches_sent_together(monkeypatch, settings, tmp_path):
    """Every batch is created before any is waited for, and the answers of all come back by custom_id."""
    from types import SimpleNamespace as NS
    settings.CORPUS_DIR = tmp_path      # each batch is written to the ledger: never the real one

    created, polled = [], []

    class Batches:
        def create(self, requests):
            created.append([r['custom_id'] for r in requests])
            return NS(id=f'b{len(created)}')

        def retrieve(self, bid):
            polled.append((bid, len(created)))
            return NS(processing_status='ended')

        def results(self, bid):
            for cid in created[int(bid[1:]) - 1]:
                yield NS(custom_id=cid, result=NS(type='succeeded', message=f'm-{cid}'))

    monkeypatch.setattr(ocr.batches, '_client', lambda: NS(messages=NS(batches=Batches())))
    monkeypatch.setattr(ocr.batches, 'BATCH_BYTES', 100)
    monkeypatch.setattr(ocr.batches.time, 'sleep', lambda s: None)
    results = ocr._send([('p1', {}, 60), ('p2', {}, 60), ('t3', {}, 30)], 'claude-haiku-5-5', log=lambda m: None)
    assert created == [['p1'], ['p2', 't3']]
    assert all(n == 2 for _, n in polled)
    assert results == {'p1': ('m-p1', 'b1'), 'p2': ('m-p2', 'b2'), 't3': ('m-t3', 'b2')}


def test_a_batch_the_queue_sits_on_is_cancelled_and_what_it_left_sent_again(monkeypatch, settings, tmp_path):
    """29 Oct 2026: one batch sat 4 h 40 with none of its pages begun, its worker waiting with it."""
    from types import SimpleNamespace as NS
    settings.CORPUS_DIR = tmp_path

    created, cancelled = [], []

    class Batches:
        def create(self, requests):
            created.append([r['custom_id'] for r in requests])
            return NS(id=f'b{len(created)}')

        def retrieve(self, bid):
            return NS(processing_status='ended' if bid in cancelled or bid != 'b1' else 'in_progress')

        def cancel(self, bid):
            cancelled.append(bid)

        def results(self, bid):
            for cid in created[int(bid[1:]) - 1]:
                kind = 'canceled' if bid == 'b1' and cid != 'p1' else 'succeeded'
                yield NS(custom_id=cid, result=NS(type=kind, message=f'm-{cid}'))

    monkeypatch.setattr(ocr.batches, '_client', lambda: NS(messages=NS(batches=Batches())))
    monkeypatch.setattr(ocr.batches, 'BATCH_WAIT_S', -1)
    monkeypatch.setattr(ocr.batches.time, 'sleep', lambda s: None)
    results = ocr._send([('p1', {}, 1), ('p2', {}, 1), ('p3', {}, 1)], 'claude-haiku-5-5', log=lambda m: None)
    assert cancelled == ['b1'] and created == [['p1', 'p2', 'p3'], ['p2', 'p3']]
    assert results == {'p1': ('m-p1', 'b1'), 'p2': ('m-p2', 'b2'), 'p3': ('m-p3', 'b2')}


def test_a_key_out_of_credit_stops_its_sending_and_keeps_what_was_sent(monkeypatch, settings, tmp_path):
    """31 Oct 2026: the month's last credit read until the API refused; a refusal is OutOfCredit, never a failed page,
    and the batches sent before it are still waited for and read."""
    from types import SimpleNamespace as NS

    import anthropic
    import httpx2 as httpx
    import pytest

    settings.CORPUS_DIR = tmp_path
    created = []

    def refusal():
        response = httpx.Response(400, request=httpx.Request('POST', 'https://api.anthropic.com/v1/messages/batches'))
        return anthropic.BadRequestError('Your credit balance is too low to access the Anthropic API.',
                                         response=response, body=None)

    class Batches:
        def create(self, requests):
            if created:
                raise refusal()
            created.append([r['custom_id'] for r in requests])
            return NS(id='b1')

        def retrieve(self, bid):
            return NS(processing_status='ended')

        def results(self, bid):
            for cid in created[0]:
                yield NS(custom_id=cid, result=NS(type='succeeded', message=f'm-{cid}'))

    monkeypatch.setattr(ocr.batches, '_client', lambda: NS(messages=NS(batches=Batches())))
    monkeypatch.setattr(ocr.batches, 'BATCH_BYTES', 100)
    monkeypatch.setattr(ocr.batches.time, 'sleep', lambda s: None)
    results = ocr._send([('p1', {}, 60), ('p2', {}, 60)], 'claude-haiku-5-5', log=lambda m: None)
    assert results == {'p1': ('m-p1', 'b1')}
    with pytest.raises(ocr.OutOfCredit):
        ocr._send([('p3', {}, 60)], 'claude-haiku-5-5', log=lambda m: None)
