"""A10 of the consumer plan: one model only, held by code, before anything is sent."""
import pytest
from django.test import override_settings

from apps.corpus.services import llm
from apps.sources.services import ocr


@override_settings(LLM_MODELS_ALLOWED='claude-haiku-5-5')
def test_another_model_is_refused_before_it_is_priced():
    with pytest.raises(ocr.ModelNotAllowed):
        ocr._worst_case('claude-sonnet-5-5', 1, 8000, batch=True)
    assert ocr._worst_case('claude-haiku-5-5', 1, 8000, batch=True) > 0


@override_settings(LLM_MODELS_ALLOWED='claude-haiku-5-5')
def test_a_structuring_batch_naming_another_model_is_refused():
    req = llm.request('t1', model='claude-opus-5-5', system='s', content='c', schema={'type': 'object'}, max_tokens=10)
    with pytest.raises(ocr.ModelNotAllowed):
        llm._worst_case([req])


@override_settings(LLM_MODELS_ALLOWED='claude-haiku-5-5')
def test_a_batch_is_refused_even_past_the_reservation(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    with pytest.raises(ocr.ModelNotAllowed):
        ocr._send([('p1', {'model': 'claude-sonnet-5-5'}, 10)], 'claude-sonnet-5-5')


@override_settings(LLM_MODELS_ALLOWED='')
def test_unset_allows_every_priced_model():
    for model in ocr.PRICES:
        ocr.check_model(model)


@pytest.mark.django_db
def test_structuring_requests_go_as_small_batches_sent_together(monkeypatch, settings, tmp_path):
    """LLM_BATCH_REQUESTS cuts a step's requests into groups, all created before any is waited for (24 Oct 2026)."""
    from types import SimpleNamespace as NS
    settings.CORPUS_DIR = tmp_path
    created, polled = [], []

    class Batches:
        def create(self, requests):
            created.append([r['custom_id'] for r in requests])
            return NS(id=f'b{len(created)}', processing_status='in_progress')

        def retrieve(self, bid):
            polled.append((bid, len(created)))
            return NS(processing_status='ended')

        def results(self, bid):
            for cid in created[int(bid[1:]) - 1]:
                usage = NS(input_tokens=10, output_tokens=5)
                msg = NS(model='claude-haiku-5-5', usage=usage, content=[NS(type='text', text='{"ok": true}')], stop_reason='end_turn')
                yield NS(custom_id=cid, result=NS(type='succeeded', message=msg))

    monkeypatch.setattr(llm, '_client', lambda: NS(messages=NS(batches=Batches())))
    monkeypatch.setattr(llm, 'BATCH_REQUESTS', 2)
    monkeypatch.setattr(ocr.batches.time, 'sleep', lambda s: None)
    reqs = [llm.request(f't{i}', model='claude-haiku-5-5', system='s', content='c', schema={'type': 'object'}, max_tokens=10)
            for i in range(5)]
    out = llm._run('texts:1', reqs, poll_s=0, log=lambda m: None)
    assert created == [['t0', 't1'], ['t2', 't3'], ['t4']]
    assert all(n == 3 for _, n in polled)
    assert set(out) == {f't{i}' for i in range(5)} and all(v['data'] == {'ok': True} for v in out.values())
    assert [e['batch'] for e in llm.ledger() if 'request' in e] == ['b1', 'b1', 'b2', 'b2', 'b3']


@pytest.mark.django_db
def test_a_structuring_batch_the_queue_sits_on_is_cancelled_and_its_rest_sent_once_more(monkeypatch, settings, tmp_path):
    from types import SimpleNamespace as NS
    settings.CORPUS_DIR = tmp_path
    created, cancelled = [], []

    class Batches:
        def create(self, requests):
            created.append([r['custom_id'] for r in requests])
            return NS(id=f'b{len(created)}', processing_status='in_progress')

        def retrieve(self, bid):
            return NS(processing_status='in_progress' if bid not in cancelled else 'ended')

        def cancel(self, bid):
            cancelled.append(bid)

        def results(self, bid):
            for cid in created[int(bid[1:]) - 1]:
                if bid == 'b1' and cid != 't0':
                    yield NS(custom_id=cid, result=NS(type='canceled'))
                    continue
                usage = NS(input_tokens=10, output_tokens=5)
                msg = NS(model='claude-haiku-5-5', usage=usage, content=[NS(type='text', text='{"ok": true}')], stop_reason='end_turn')
                yield NS(custom_id=cid, result=NS(type='succeeded', message=msg))

    monkeypatch.setattr(llm, '_client', lambda: NS(messages=NS(batches=Batches())))
    monkeypatch.setattr(ocr.batches, 'BATCH_WAIT_S', -1)
    monkeypatch.setattr(ocr.batches.time, 'sleep', lambda s: None)
    reqs = [llm.request(f't{i}', model='claude-haiku-5-5', system='s', content='c', schema={'type': 'object'}, max_tokens=10)
            for i in range(3)]
    out = llm._run('texts:1', reqs, poll_s=0, log=lambda m: None)
    assert created == [['t0', 't1', 't2'], ['t1', 't2']] and cancelled == ['b1', 'b2']
    assert all(v['data'] == {'ok': True} for v in out.values()) and len(out) == 3
