"""Structured requests through the Message Batches API (`services/llm.py`): every answer read by its custom id, an
answer that is not JSON or not answered kept as such, every cost in the ledger, a key out of credit stopping what is
left to send and keeping what was sent, a refusal closing its open line; and the situations' drafts, which are written
from those answers and keep only the candidates' articles."""
import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.corpus.services import llm, situations
from apps.corpus.tests import claude
from apps.sources.services.ocr import OutOfCredit, allow_spending

pytestmark = pytest.mark.django_db
SCHEMA = {'type': 'object', 'properties': {'n': {'type': 'integer'}}}


def ask(*ids):
    """Requests whose worst case is $0.005 each (20,000 tokens out at $0.25 a million, batched)."""
    return [llm.request(i, model='claude-haiku-5-5', system='Count.', content='واحد', schema=SCHEMA, max_tokens=20000)
            for i in ids]


@pytest.fixture
def batches(monkeypatch, settings, tmp_path):
    answers = {'a': {'n': 1}, 'b': 'not JSON at all', 'c': None}
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: answers[cid])
    allow_spending(True, log=lambda *a: None)
    return sent


def test_each_answer_is_read_by_its_id_and_priced_in_the_ledger(batches):
    logged = []
    out = llm.run_batch('count', ask('a', 'b', 'c'), poll_s=0, log=logged.append)
    assert out['a'] == {'data': {'n': 1}, 'stop': 'end_turn', 'error': ''}
    assert out['b']['data'] is None and out['b']['error'].startswith('not JSON: ')
    assert out['c'] == {'data': None, 'stop': 'errored', 'error': 'errored'}
    assert logged[0].startswith('count: batch msgbatch_01, 3 requests (worst case $')
    priced = [e for e in llm.ledger() if 'request' in e]
    assert [(e['request'], e['input_tokens'], e['output_tokens'], e['cost_usd']) for e in priced] == [
        ('a', 2000, 400, 0.0002), ('b', 2000, 400, 0.0002)]
    assert batches.requests()[0]['params']['output_config']['format']['schema'] == SCHEMA


def test_a_request_written_without_thinking_says_so():
    [r] = [llm.request('w', model='claude-haiku-5-5', system='s', content='c', schema=SCHEMA, max_tokens=10, think=False)]
    assert r['params']['thinking'] == {'type': 'disabled'}
    assert 'thinking' not in ask('t')[0]['params']


def test_out_of_credit_after_a_first_batch_keeps_its_answers_and_sends_no_more(batches, monkeypatch):
    monkeypatch.setattr(llm, 'BATCH_REQUESTS', 1)                 # LLM_BATCH_REQUESTS=1: one request a batch
    batches.refusals = [(400, 'Your credit balance is too low to access the Anthropic API.')] * 2
    with pytest.raises(OutOfCredit):
        llm.run_batch('count', ask('a'), poll_s=0, log=lambda *a: None)
    # The refused create's open line is closed at its worst case: nothing stays counted for it.
    assert sum(e['cost_usd'] for e in llm.ledger()) == 0
    batches.refusals = [None, (400, 'Your credit balance is too low to access the Anthropic API.')]
    logged = []
    out = llm.run_batch('count', ask('a', 'b'), poll_s=0, log=logged.append)
    assert list(out) == ['a'] and out['a']['data'] == {'n': 1}
    assert 'count: out of credit, the batches already sent answered, the rest left unanswered' in logged


def test_a_refused_batch_raises_and_closes_its_line(batches):
    import anthropic
    batches.refusals = [(413, 'request too large')]
    with pytest.raises(anthropic.APIStatusError):
        llm.run_batch('count', ask('a'), poll_s=0, log=lambda *a: None)
    assert sum(e['cost_usd'] for e in llm.ledger()) == 0 and batches.sent == {}


def test_without_a_key_nothing_is_sent(batches, settings):
    settings.ANTHROPIC_API_KEY = ''
    with pytest.raises(RuntimeError, match='Set ANTHROPIC_API_KEY'):
        llm.run_batch('count', ask('a'), poll_s=0, log=lambda *a: None)
    assert batches.sent == {}


def test_a_situations_draft_keeps_only_the_candidates_articles_and_writes_the_sites_name(tmp_path, settings, monkeypatch):
    listed, drafts = tmp_path / 'situations.json', tmp_path / 'drafts.json'
    monkeypatch.setattr(situations, 'SITUATIONS', listed)
    monkeypatch.setattr(situations, 'DRAFTS', drafts)
    # No search of its own here: no candidate article, so any article the model names is one it made up.
    listed.write_text(json.dumps({'situations': [
        {'slug': 'accident', 'title': {'ar': 'وقعت لي حادثة سير', 'fr': "J'ai eu un accident"}, 'searches': [],
         'shelf': ['road']},
        {'slug': 'fired', 'title': {'ar': 'طردت من العمل', 'fr': "J'ai été licencié"}, 'searches': [], 'shelf': []}]},
        ensure_ascii=False))
    drafts.write_text(json.dumps({'situations': [{'slug': 'older', 'intro': {'ar': 'ق', 'fr': 'o'}, 'articles': []}]}))
    answers = {'situation-accident': {'intro': {'ar': 'تنظم ماتن ومدونة السير هذه الحالة.', 'fr': 'Le code de la route.'},
                                      'articles': [{'path': '/ma/loi/52-05/art_999', 'says': {'ar': 'ي', 'fr': 'd'}}]},
               'situation-fired': None}
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: answers[cid])
    out = StringIO()
    call_command('draft_situations', '--write', stdout=out)
    assert out.getvalue().splitlines()[-2:] == ['fired: no draft (errored)', '2 situations drafted; 0 articles chosen']
    written = {s['slug']: s for s in json.loads(drafts.read_text())['situations']}
    assert list(written) == ['older', 'accident']
    assert written['accident']['intro']['ar'] == 'تنظم «قانون» ومدونة السير هذه الحالة.'
    assert written['accident']['articles'] == [] and written['accident']['model'] == 'claude-haiku-5-5'
    content = sent.requests()[0]['params']['messages'][0]['content']
    assert content.startswith("Situation: وقعت لي حادثة سير / J'ai eu un accident\nTexts that govern it but are not in "
                              '3adala yet: ') and not content.endswith('none\n\nCandidates:')



def test_the_structure_trial_reads_each_chosen_page_and_keeps_what_it_cost(tmp_path, settings, monkeypatch):
    from django.utils import timezone

    from apps.corpus.management.commands.structure_trial import PAGES
    from apps.sources.models import Document, OcrRun, Page
    claude.install(monkeypatch, settings, tmp_path, lambda cid, params: {'texts': [
        {'type': 'decree', 'number': '2.25.100', 'title': params['messages'][0]['content'], 'articles': []},
        {'type': 'order', 'number': '12.25', 'title': 'قرار', 'articles': []}]})
    selection = []
    for k, (label, group) in enumerate(PAGES):
        doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{k}'.ljust(64, '0'), path=f'p{k}.pdf',
                                      mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now())
        page = Page.objects.create(document=doc, index=2, text='')
        OcrRun.objects.create(page=page, engine='claude-sonnet-5-5', variant='page', text=f'الصفحة {label}')
        selection.append({'label': label, 'group': group, 'path': f'p{k}.pdf', 'index': 2})
    (tmp_path / 'samples').mkdir()
    (tmp_path / 'reports').mkdir(exist_ok=True)
    (tmp_path / 'samples' / 'ocr_selection.json').write_text(json.dumps(selection))
    out = StringIO()
    call_command('structure_trial', '--write', stdout=out)
    # Sonnet, sent alone (no batch discount): 2,000 tokens in at $2 a million, 400 out at $10.
    assert out.getvalue().splitlines() == [f'{label}: 2 texts, $0.008' for label, _ in PAGES]
    results = json.loads((tmp_path / 'reports' / 'structure_trial.json').read_text())
    assert [r['structure']['texts'][0]['title'] for r in results] == [f'الصفحة {label}' for label, _ in PAGES]
    assert [e['kind'] for e in llm.ledger() if e.get('call')] == ['structure'] * 4
    assert {k: results[0]['usage'][k] for k in ('model', 'input_tokens', 'output_tokens', 'cost_usd')} == {
        'model': 'claude-sonnet-5-5', 'input_tokens': 2000, 'output_tokens': 400, 'cost_usd': 0.008}
    assert (results[0]['ocr_engine'], results[0]['label'], results[0]['index']) == ('claude-sonnet-5-5', '1938', 2)
