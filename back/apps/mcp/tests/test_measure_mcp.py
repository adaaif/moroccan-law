"""`measure_mcp` (MC22): goldset questions answered by Haiku alone and with the site's tools, this command being the MCP
client, graded by code. The Messages API is a stand-in in the API's own types (`anthropic.types`), answering as a model
that keeps calling tools until told not to; the MCP server is the site's own, in a thread; the budget, the ledger and the
grading all run. `--regrade` grades saved answers again for nothing."""
import copy
import gc
import json
import re
from datetime import date
from io import StringIO
from pathlib import Path

import pytest
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.mcp.management.commands.measure_mcp import ASK, MODEL, SETS, SYSTEM
from apps.mcp.models import Tally
from apps.mcp.server import instructions
from apps.mcp.tests.test_server import server_url, the_clock_stands_still  # noqa: F401  (fixtures)
from apps.oauth.models import Client, Day, Grant
from apps.sources.models import Document, Issue

SITE = 'http://localhost:5190'
GOLDSET = Path(__file__).resolve().parents[2] / 'search' / 'goldset'
TEXT = '/ma/loi/99-98'
ART = TEXT + '/art_1'


class Haiku:
    """`anthropic.Anthropic()` as the command uses it: `messages.create` answers with a Message, each request kept as
    it was sent. `act(question, params, answer_now)` is the model: its answer's text, or a turn that calls tools (a
    list of (tool, input), with a text before them where it says one); told to use no tool (`tool_choice` none), it
    answers."""

    def __init__(self, act):
        self.act, self.sent, self.questions = act, [], []
        self.messages = self

    def create(self, **params):
        self.sent.append(copy.deepcopy(params))
        question = re.search('«(.+?)»', params['messages'][0]['content']).group(1)
        if question not in self.questions:
            self.questions.append(question)
        said = self.act(question, params, params.get('tool_choice') == {'type': 'none'})
        if isinstance(said, str):
            content, stop = [TextBlock(type='text', text=said)], 'end_turn'
        else:
            content = [TextBlock(type='text', text=part) if isinstance(part, str) else
                       ToolUseBlock(type='tool_use', id=f'toolu_{len(self.sent):02d}_{k}', name=part[0], input=part[1])
                       for k, part in enumerate(said)]
            stop = 'tool_use'
        return Message(id=f'msg_{len(self.sent):02d}', type='message', role='assistant', model=params['model'],
                       content=content, stop_reason=stop, stop_sequence=None,
                       usage=Usage(input_tokens=1000, output_tokens=200))           # $0.0002 a request


@pytest.fixture
def api(monkeypatch, settings, tmp_path):
    """The paid client is the stand-in; the ledger and the budget's holds live under the test's folder; the permission
    to spend is this test's alone."""
    import anthropic

    from apps.sources.services.ocr import guard

    settings.CORPUS_DIR = tmp_path
    settings.ANTHROPIC_API_KEY = 'sk-ant-test'
    made = []
    monkeypatch.setattr(anthropic, 'Anthropic', lambda **kw: made[0])
    monkeypatch.setattr(guard, '_SPENDING', False)
    return made


@pytest.fixture
def pool_connections(transactional_db):
    """The command grades in worker threads, which leave their database connection to the garbage collector (a real
    run's process ends with them): collected before the test's database is emptied, none holds it when the suite's
    test database is dropped."""
    yield
    gc.collect()


def expectations() -> dict:
    """Each goldset question the command can ask, with the articles that answer it."""
    out = {}
    for name in SETS:
        if (GOLDSET / f'{name}.json').is_file():
            for q in json.loads((GOLDSET / f'{name}.json').read_text())['questions']:
                out[q['q']] = [q['expect']] if isinstance(q['expect'], str) else q['expect']
    return out


def run(*args, **options) -> str:
    out = StringIO()
    call_command('measure_mcp', *args, stdout=out, **options)
    return out.getvalue()


@pytest.mark.django_db(transaction=True)
def test_a_run_asks_each_set_alone_and_with_the_tools_pays_into_the_ledger_and_grades_by_code(
        pool_connections, server_url, api, settings, tmp_path):
    settings.MCP_QUOTAS = {'minute': 1000, 'day': 1000, 'articles': 1000}      # the account's quotas raised for a run
    get_user_model().objects.create_user(username='measure', email='measure@example.org', password='daftar-2026-x')
    # A text no goldset question names, its articles too long to give whole.
    scan = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='7' * 64, path='bo/7560.pdf',
                                   mime='application/pdf', bytes=1, language='ar', fetched_at=timezone.now())
    issue = Issue.objects.create(edition='general_ar', number=7560, date=date(2026, 11, 9), document=scan)
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/99-98', type='law', number='99-98', number_as_printed='99.98',
                               title_ar='قانون المالية رقم 99.98', status='in_force', first_published_in=issue,
                               first_published_page=12)
    version = Version.objects.create(text=text, language='ar', valid_from=date(2026, 1, 1),
                                     consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.bulk_create(Article(version=version, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}',
                                        body='المادة ' * 2000) for n in range(1, 5))
    expect = expectations()

    def act(question, params, answer_now):
        n, turn = haiku.questions.index(question), (len(params['messages']) - 1) // 2
        if 'tools' not in params:                               # alone: articles the text does not have
            return 'المادة 700 من القانون رقم 99.98' + (' والمادة 800 من القانون رقم 99.98' if n == 1 else '')
        if answer_now or (n == 1 and turn == 1):                # with the tools: the expected article's link
            return f'{SITE}{expect[question][0]}'
        if turn == 0:
            return [('fetch', {'id': ART}), ('fetch', {'id': f'{TEXT}/art_700'})] if n == 0 else [
                'سأقرأ المادة الأولى.', ('fetch', {'id': ART})]
        if turn == 1:
            return [('read_articles', {'id': TEXT, 'count': 4})]
        return [('get_bulletin', {})]                           # the first question's model calls on until told not to

    haiku = Haiku(act)
    api.append(haiku)
    out = tmp_path / 'out'
    cost = 0.0002
    said = run(url=server_url, user='measure', per_set=1, cap=14.5 * cost, out=str(out), threads=1, write=True)
    present = [name for name in SETS if (GOLDSET / f'{name}.json').is_file()]       # a set kept out of the tree is skipped
    assert said.splitlines()[0] == f'{len(present)} questions, 5 tools'
    # The cap: the first two questions both ways (11 and 3 requests), the third alone; nothing more was asked.
    sent = haiku.sent
    assert len(sent) == 15 and len(haiku.questions) == 3
    alone, first, last = sent[0], sent[1], sent[10]
    assert alone == {'model': MODEL, 'max_tokens': 1500, 'system': SYSTEM,
                     'messages': [{'role': 'user', 'content': ASK.format(q=haiku.questions[0])}]}
    assert first['system'] == SYSTEM + '\n\n' + instructions()
    assert [t['name'] for t in first['tools']] == ['search', 'fetch', 'read_articles', 'check_references', 'get_bulletin']
    assert first['tools'][2]['input_schema']['properties']['count']['maximum'] == 20
    assert first['tools'][1]['description'].startswith('Read one item from 3adala by its id.')
    # The last turn answers with what it read; every turn before it may call a tool.
    assert [r.get('tool_choice') for r in sent[1:11]] == [None] * 9 + [{'type': 'none'}]
    assert sent[2]['messages'][1] == {'role': 'assistant', 'content': [
        {'type': 'tool_use', 'id': 'toolu_02_0', 'name': 'fetch', 'input': {'id': ART}},
        {'type': 'tool_use', 'id': 'toolu_02_1', 'name': 'fetch', 'input': {'id': f'{TEXT}/art_700'}}]}
    fetched, refused = sent[2]['messages'][2]['content']
    assert (fetched['tool_use_id'], fetched['is_error'], json.loads(fetched['content'])['id']) == ('toolu_02_0', False, ART)
    assert (refused['tool_use_id'], refused['is_error']) == ('toolu_02_1', True)
    assert refused['content'].startswith('قانون المالية رقم 99.98 has no article 700')
    long = sent[3]['messages'][4]['content'][0]['content']
    assert len(long) == 40000 and long.startswith('قانون المالية رقم 99.98 — in force')
    listed = sent[4]['messages'][6]['content'][0]['content']
    assert '\n{"issues": [{"key": "7560"' in listed                       # get_bulletin's data after its text
    assert last['messages'][-1]['content'][0]['content'] == listed
    said_first = sent[13]['messages'][1:3]                              # what the model said before its call stays
    assert said_first[0]['content'] == [{'type': 'text', 'text': 'سأقرأ المادة الأولى.'},
                                        {'type': 'tool_use', 'id': 'toolu_13_1', 'name': 'fetch', 'input': {'id': ART}}]
    assert [b['tool_use_id'] for b in said_first[1]['content']] == ['toolu_13_1']
    # Every answer is written as it lands, then the whole run and its summary.
    rows = [json.loads(line) for line in next(out.glob('measure-*.jsonl')).read_text().splitlines()]
    assert rows == json.loads(next(out.glob('measure-*[0-9].json')).read_text())
    assert [r['set'] for r in rows] == present and [r['q'] for r in rows[:3]] == haiku.questions
    assert all(r['expect'] == expect[r['q']] for r in rows)
    one, two, three = rows[:3]
    assert {k: one['alone'][k] for k in ('right', 'cited', 'cites', 'unfound', 'linked', 'calls')} == {
        'right': False, 'cited': [], 'cites': 1, 'unfound': True, 'linked': False, 'calls': []}
    assert {k: one['tools'][k] for k in ('answer', 'right', 'cited', 'cites', 'unfound', 'linked')} == {
        'answer': f"{SITE}{one['expect'][0]}", 'right': True, 'cited': [one['expect'][0]], 'cites': 1,
        'unfound': False, 'linked': True}
    calls = one['tools']['calls']
    assert [(c['tool'], c['error']) for c in calls] == [('fetch', False), ('fetch', True), ('read_articles', False)] + [
        ('get_bulletin', False)] * 7
    assert calls[0]['input'] == {'id': ART} and calls[2]['chars'] > 40000
    assert (two['alone']['cites'], len(two['tools']['calls'])) == (2, 1)
    assert three['alone']['unfound'] and three['tools'] is None
    assert all(r['alone'] is None and r['tools'] is None for r in rows[3:])
    summary = json.loads(next(out.glob('measure-*-summary.json')).read_text())
    assert json.loads(said[said.index('{'):]) == summary
    assert summary == {
        'model': MODEL, 'questions': 2, 'spent_usd': 0.003, 'right': {'alone': 0.0, 'tools': 1.0},
        'any_unfound_cite': {'alone': 1.0, 'tools': 0.0}, 'cites_per_answer': {'alone': 1.5, 'tools': 1.0},
        'linked': 1.0, 'tool_calls_per_answer': 5.5, 'tool_errors': 1,
        'by_set': {present[0]: {'questions': 1, 'right_alone': 0, 'right_tools': 1},
                   present[1]: {'questions': 1, 'right_alone': 0, 'right_tools': 1}}}
    ledger = json.loads((tmp_path / 'reports' / 'llm_ledger.json').read_text())
    assert ledger == [{'kind': 'mcp-measure', 'model': MODEL, 'call': True, 'input_tokens': 1000, 'output_tokens': 200,
                       'cost_usd': cost}] * 15
    assert json.loads((tmp_path / 'reports' / 'inflight.json').read_text()) == {}      # no hold left
    # The tools were called as the account, through a connection of the command's own.
    client = Client.objects.get(client_id='qc_measure')
    assert (client.kind, client.name, client.domain, client.redirect_uris) == (
        'dcr', 'measure_mcp', 'localhost', ['http://localhost/callback'])
    grant = Grant.objects.get()
    assert (grant.user.username, grant.client, grant.scope, grant.resource) == (
        'measure', client, 'law:read', settings.MCP_RESOURCE)
    day = Day.objects.get(grant=grant)
    assert (day.calls, day.articles, day.tools) == (10, 6, {'fetch': 2, 'read_articles': 1, 'get_bulletin': 7})
    # Every tool call as the account: none was counted as a direct caller's.
    assert list(Tally.objects.values_list('origin', 'calls')) == [('accounts', 10)]
    # A request whose worst case (1,500 tokens written) would pass the ledger's budget is never sent, whatever the
    # run's cap; past the cap from the start nothing is either. The next run keeps the connection, a revoked one is
    # replaced.
    settings.OCR_BUDGET_USD = 0.003 + 0.0005
    said = run(url=server_url, user='measure', per_set=1, out=str(tmp_path / 'again'), threads=1, write=True)
    assert len(haiku.sent) == 15 and Grant.objects.get() == grant
    again = [json.loads(line) for line in next((tmp_path / 'again').glob('measure-*.jsonl')).read_text().splitlines()]
    assert [r['q'] for r in again] == [r['q'] for r in rows]                   # the same questions each run
    assert json.loads(said[said.index('{'):]) == {
        'model': MODEL, 'questions': 0, 'spent_usd': 0.0, 'right': {'alone': None, 'tools': None},
        'any_unfound_cite': {'alone': None, 'tools': None}, 'cites_per_answer': {'alone': None, 'tools': None},
        'linked': None, 'tool_calls_per_answer': None, 'tool_errors': 0, 'by_set': {}}
    Grant.objects.update(revoked_at=timezone.now())
    said = run(url=server_url, user='measure', cap=0, write=True)          # 13 questions a set, under CORPUS_DIR
    assert said.splitlines()[0] == f'{13 * len(present)} questions, 5 tools'
    assert Grant.objects.count() == 2 and Grant.objects.filter(revoked_at=None).exclude(pk=grant.pk).exists()
    assert len(list((tmp_path / 'reports' / 'mcp').glob('measure-*-summary.json'))) == 1


@pytest.mark.django_db
def test_nothing_is_asked_without_write_or_without_a_key(api, settings, tmp_path):
    haiku = Haiku(lambda question, params, answer_now: 'never asked')
    api.append(haiku)
    with pytest.raises(CommandError, match=r'^This step sends paid requests to the model: run the command again with '
                                           r'--write\.$'):
        run(url='http://127.0.0.1:9/mcp', user='measure')
    settings.ANTHROPIC_API_KEY = ''
    with pytest.raises(CommandError, match=r'^Set ANTHROPIC_API_KEY in the environment\.$'):
        run(url='http://127.0.0.1:9/mcp', user='measure', write=True)
    assert haiku.sent == [] and not (tmp_path / 'reports' / 'llm_ledger.json').exists()


@pytest.mark.django_db
def test_saved_answers_are_graded_again_by_code_for_nothing(labour, tmp_path):
    Text.objects.create(akn_uri='/akn/ma/act/loi/12-26', type='law', number='12-26', number_as_printed='12.26',
                        title_ar='القانون رقم 12.26')
    stale = {'right': False, 'cited': [], 'cites': 0, 'unfound': False, 'linked': False}

    def side(answer, calls=()):
        return {'answer': answer, 'calls': [{'tool': t, 'error': e} for t, e in calls], **stale}
    rows = [
        {'set': 'work', 'q': 'q1', 'expect': ['/ma/loi/65-99/art_51'],
         'alone': side('https://3adala.com/ma/loi/65-99/art_51'),
         'tools': side('المادة 51 من مدونة الشغل والمادة 700 من القانون رقم 65.99', [('fetch', False), ('fetch', True)])},
        # A bare article is read in the one text the answer names, by its number and its name.
        {'set': 'work', 'q': 'q2', 'expect': '/ma/loi/65-99/art_53',
         'alone': side('القانون رقم 65.99 (مدونة الشغل) ينص في المادة 53'),
         'tools': side('القانون رقم 65.99: **المادة 53** والمادة 52 والمادة 50 والمادة 49، راجع '
                        'https://3adala.com/ma/loi/65-99/art_53',
                        [('search', False)])},
        # Two texts named: a bare article is nobody's; a text the site does not hold is no wrong citation.
        {'set': 'family', 'q': 'q3', 'expect': ['/ma/loi/70-03/art_19'],
         'alone': side('القانون رقم 65.99 والقانون رقم 12.26، المادة 19، والمادة 4 من القانون رقم 70.03'),
         'tools': side('https://3adala.com/ma/loi/70-03/art_19', [('fetch', False)])},
        {'set': 'road', 'q': 'q4', 'expect': ['/ma/loi/52-05/art_30'], 'alone': None,          # stopped by the cap
         'tools': side('المادة 30 من القانون رقم 52.05')},
    ]
    saved = tmp_path / 'measure-20261103-2210.jsonl'
    saved.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    said = run(url='http://127.0.0.1:9/mcp', user='nobody', regrade=str(saved), spent=0.47)
    again = [json.loads(line) for line in (tmp_path / 'measure-20261103-2210-regraded.jsonl').read_text().splitlines()]
    graded = [{side: {k: r[side][k] for k in stale} if r[side] else None for side in ('alone', 'tools')} for r in again]
    assert graded == [
        {'alone': {'right': True, 'cited': ['/ma/loi/65-99/art_51'], 'cites': 1, 'unfound': False, 'linked': True},
         'tools': {'right': True, 'cited': ['/ma/loi/65-99/art_51'], 'cites': 2, 'unfound': True, 'linked': False}},
        {'alone': {'right': True, 'cited': ['/ma/loi/65-99/art_53'], 'cites': 1, 'unfound': False, 'linked': False},
         'tools': {'right': True, 'cited': [f'/ma/loi/65-99/art_{n}' for n in (49, 50, 52, 53)], 'cites': 4,
                    'unfound': False, 'linked': True}},
        {'alone': {'right': False, 'cited': [], 'cites': 0, 'unfound': False, 'linked': False},
         'tools': {'right': True, 'cited': ['/ma/loi/70-03/art_19'], 'cites': 1, 'unfound': False, 'linked': True}},
        {'alone': None,
         'tools': {'right': False, 'cited': [], 'cites': 0, 'unfound': False, 'linked': False}}]
    assert [r['tools']['calls'] for r in again] == [r['tools']['calls'] for r in rows]
    summary = json.loads((tmp_path / 'measure-20261103-2210-regraded-summary.json').read_text())
    assert json.loads(said) == summary == {
        'model': MODEL, 'questions': 3, 'spent_usd': 0.47, 'right': {'alone': 0.667, 'tools': 1.0},
        'any_unfound_cite': {'alone': 0.0, 'tools': 0.333}, 'cites_per_answer': {'alone': 0.67, 'tools': 2.33},
        'linked': 0.667, 'tool_calls_per_answer': 1.33, 'tool_errors': 1,
        'by_set': {'work': {'questions': 2, 'right_alone': 2, 'right_tools': 2},
                   'family': {'questions': 1, 'right_alone': 0, 'right_tools': 1}}}
    assert json.loads(run(url='http://127.0.0.1:9/mcp', user='nobody', regrade=str(saved)))['spent_usd'] == 0.0
