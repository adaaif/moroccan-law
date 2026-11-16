"""MC22 of the MCP review: does an assistant cite the right article with the site, and without it?

Questions from the goldsets (each with the articles that answer it, owner-provisional) go to Haiku twice: alone, and with
the site's MCP server as tools (this command is the MCP client, as Claude or ChatGPT would be: it lists the tools, calls
them for the model and hands back their results, with the server's instructions). Graded by code, no judge:

- right: the answer cites one of the expected articles (a link to the site, or a citation ma_law reads and the site resolves);
- wrong cites: citations the site cannot find (an article a text does not have, a text that is not Moroccan law);
- linked: the answer gives a link to the site.

    python manage.py measure_mcp --url http://localhost:5190/mcp --user <username> --per-set 13 --cap 2 --write
(paid, so --write; needs ANTHROPIC_API_KEY; the account's quotas raised for the run: MCP_QUOTA_MINUTE, MCP_QUOTA_DAY,
MCP_QUOTA_ARTICLES.)
"""
import json
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anyio
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.sources.services import ocr

MODEL = 'claude-haiku-5-5'
SETS = ['work', 'family', 'housing', 'road', 'tax', 'papers', 'justice', 'digital']
ASK = ('A reader in Morocco asks: «{q}»\n\nAnswer in the reader\'s language, in five lines at most, and cite the '
       'articles of Moroccan law your answer rests on (article number and text).')
SYSTEM = 'You answer questions about Moroccan law.'
LINK = re.compile(r'/ma/[a-z_]+/[\w.-]+(?:/[\w.-]+)*?/art_[\w-]+')
MAX_TURNS = 10


class Command(BaseCommand):
    help = 'Measure answers about Moroccan law by Haiku with and without the site\'s MCP server.'

    def add_arguments(self, parser):
        parser.add_argument('--url', required=True)
        parser.add_argument('--user', required=True)
        parser.add_argument('--per-set', type=int, default=13)
        parser.add_argument('--cap', type=float, default=2.0, help='Dollars at most.')
        parser.add_argument('--out', default=str(Path(settings.CORPUS_DIR) / 'reports' / 'mcp'))
        parser.add_argument('--threads', type=int, default=4)
        parser.add_argument('--regrade', default='', help='A run\'s .jsonl: grade its saved answers again, no API call.')
        parser.add_argument('--spent', type=float, default=None, help='With --regrade: what the run cost.')
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')

    def handle(self, *args, **opts):
        if opts['regrade']:
            return self._regrade(Path(opts['regrade']), opts['spent'])
        ocr.allow_spending(opts['write'], log=self.stdout.write)
        try:
            self.api = ocr._client()
        except RuntimeError as exc:         # no key
            raise CommandError(str(exc)) from exc
        self.cap, self.spent, self.counting = opts['cap'], 0.0, threading.Lock()
        self.url = opts['url']
        self.token = self._token(opts['user'])
        self.tools, self.instructions = anyio.run(self._list)
        questions = self._questions(opts['per_set'])
        self.stdout.write(f'{len(questions)} questions, {len(self.tools)} tools')
        out = Path(opts['out'])
        out.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime('%Y%m%d-%H%M')
        # Each answer written as it lands: a run stopped halfway keeps what it paid for.
        lines = out / f'measure-{stamp}.jsonl'
        lock = threading.Lock()

        def one(item):
            row = self._one(item)
            with lock, lines.open('a') as f:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + '\n')
            return row
        with ThreadPoolExecutor(opts['threads']) as pool:
            rows = list(pool.map(one, questions))
        (out / f'measure-{stamp}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
        summary = self._summary(rows)
        (out / f'measure-{stamp}-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=1))

    def _regrade(self, path: Path, spent):
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        for row in rows:
            for side in ('alone', 'tools'):
                if row.get(side):
                    row[side].update(grade(row[side]['answer'], row['expect']))
        self.spent = spent or 0.0
        out = path.with_name(path.stem + '-regraded.jsonl')
        out.write_text(''.join(json.dumps(r, ensure_ascii=False, default=str) + '\n' for r in rows))
        summary = self._summary(rows)
        path.with_name(path.stem + '-regraded-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=1))

    # ── the account and the server ───────────────────────────────────────────

    def _token(self, username):
        from apps.oauth.models import Client, Grant
        from apps.oauth.services import tokens

        user = get_user_model().objects.get(username=username)
        client, _ = Client.objects.get_or_create(client_id='qc_measure', defaults={
            'kind': 'dcr', 'name': 'measure_mcp', 'domain': 'localhost', 'redirect_uris': ['http://localhost/callback']})
        grant = (Grant.objects.filter(user=user, client=client, revoked_at=None).first()
                 or Grant.objects.create(user=user, client=client, scope='law:read', resource=settings.MCP_RESOURCE))
        return tokens._pair(grant)['access_token']

    async def _session(self, work):
        import httpx2
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client

        async with httpx2.AsyncClient(headers={'Authorization': f'Bearer {self.token}'}, timeout=120) as http:
            async with Client(streamable_http_client(self.url, http_client=http), mode='legacy') as client:
                return await work(client)

    async def _list(self):
        async def work(client):
            listed = await client.list_tools()
            tools = [{'name': t.name, 'description': t.description or '', 'input_schema': t.input_schema}
                     for t in listed.tools]
            return tools, client.instructions or ''
        return await self._session(work)

    def _call(self, name, arguments) -> tuple[str, bool]:
        async def work(client):
            r = await client.call_tool(name, arguments)
            text = '\n'.join(getattr(c, 'text', '') for c in r.content)
            if r.structured_content and name not in ('search', 'fetch'):
                text += '\n' + json.dumps(r.structured_content, ensure_ascii=False)
            return text, bool(r.is_error)
        return anyio.run(self._session, work)

    # ── the questions and the answers ────────────────────────────────────────

    @staticmethod
    def _questions(per_set):
        root = Path(__file__).resolve().parents[3] / 'search' / 'goldset'
        rng = random.Random(20261103)
        out = []
        for name in SETS:
            if not (root / f'{name}.json').is_file():      # a set kept out of the public tree
                continue
            items = [q for q in json.loads((root / f'{name}.json').read_text())['questions'] if q.get('expect')]
            out += [{'set': name, **q} for q in rng.sample(items, min(per_set, len(items)))]
        return out

    def _ask(self, **params):
        """One turn, inside the shared budget like every paid request: its worst case held while it is out (the
        threads see each other's), its cost in the ledger when it answers; --cap bounds this run on top."""
        with self.counting:
            if self.spent >= self.cap:
                raise RuntimeError('cap')
        worst = ocr.call_worst(MODEL, len(json.dumps(params, ensure_ascii=False, default=str)), params['max_tokens'])
        with ocr.reserve('mcp-measure', worst):
            r = self.api.messages.create(model=MODEL, **params)
            cost = ocr.record_call('mcp-measure', MODEL, r.usage)
        with self.counting:
            self.spent += float(cost)
        return r

    def _answer(self, q, with_tools):
        messages = [{'role': 'user', 'content': ASK.format(q=q)}]
        params = {'max_tokens': 1500, 'messages': messages,
                  'system': SYSTEM + ('\n\n' + self.instructions if with_tools else '')}
        if with_tools:
            params['tools'] = self.tools
        calls = []
        for turn in range(MAX_TURNS):
            if with_tools and turn == MAX_TURNS - 1:
                params['tool_choice'] = {'type': 'none'}       # the last turn answers with what it read
            r = self._ask(**params)
            if r.stop_reason != 'tool_use':
                return ''.join(b.text for b in r.content if b.type == 'text'), calls
            messages.append({'role': 'assistant', 'content': [b.model_dump(exclude_none=True) for b in r.content]})
            results = []
            for b in r.content:
                if b.type == 'tool_use':
                    text, failed = self._call(b.name, b.input)
                    calls.append({'tool': b.name, 'input': b.input, 'error': failed, 'chars': len(text)})
                    results.append({'type': 'tool_result', 'tool_use_id': b.id, 'content': text[:40000],
                                    'is_error': failed})
            messages.append({'role': 'user', 'content': results})
        return '(no final answer after the tool turns)', calls

    def _one(self, item):
        row = {'set': item['set'], 'q': item['q'], 'expect': item['expect']}
        for name, with_tools in (('alone', False), ('tools', True)):
            try:
                answer, calls = self._answer(item['q'], with_tools)
            except RuntimeError:
                row[name] = None
                continue
            row[name] = {'answer': answer, 'calls': calls, **grade(answer, item['expect'])}
        return row

    def _summary(self, rows):
        done = [r for r in rows if r.get('alone') and r.get('tools')]

        def share(side, key):
            return round(sum(1 for r in done if r[side][key]) / len(done), 3) if done else None

        def mean(side, key):
            return round(sum(r[side][key] for r in done) / len(done), 2) if done else None
        by_set = {}
        for name in SETS:
            mine = [r for r in done if r['set'] == name]
            if mine:
                by_set[name] = {'questions': len(mine), 'right_alone': sum(r['alone']['right'] for r in mine),
                                'right_tools': sum(r['tools']['right'] for r in mine)}
        return {'model': MODEL, 'questions': len(done), 'spent_usd': round(self.spent, 4),
                'right': {'alone': share('alone', 'right'), 'tools': share('tools', 'right')},
                'any_unfound_cite': {'alone': share('alone', 'unfound'), 'tools': share('tools', 'unfound')},
                'cites_per_answer': {'alone': mean('alone', 'cites'), 'tools': mean('tools', 'cites')},
                'linked': share('tools', 'linked'),
                'tool_calls_per_answer': round(sum(len(r['tools']['calls']) for r in done) / len(done), 2) if done else None,
                'tool_errors': sum(c['error'] for r in done for c in r['tools']['calls']),
                'by_set': by_set}


def grade(answer: str, expect) -> dict:
    """What an answer cites, resolved by the site: right when one of the expected articles is among them. A bare «المادة
    66» is read as an article of the one text the answer names (by its name, its number or both), when it names one."""
    import ma_law

    from apps.corpus.services.citations import resolve

    expect = [expect] if isinstance(expect, str) else list(expect)
    plain = re.sub(r'[*_#`>]+', ' ', answer)            # Markdown's marks are no part of a citation
    found, unfound = set(LINK.findall(answer)), 0
    cites = ma_law.parse_citations(plain)
    texts = {}
    for c in cites:
        if (c.get('code') or c.get('text_number')) and not c.get('article'):
            t = resolve(c).get('text') or {}
            if t.get('path'):
                texts.setdefault(t['path'], c)
    only = next(iter(texts.values())) if len(texts) == 1 else None
    for c in cites:
        if not c.get('article'):
            continue
        if not (c.get('code') or c.get('text_number')):
            if only is None:
                continue
            c = {**c, **{k: only.get(k) for k in ('code', 'text_kind', 'text_number')}}
        r = resolve(c)
        if r.get('article'):
            found.add(r['article']['path'])
        elif r['state'] in ('text_only', 'unknown'):
            unfound += 1
    return {'right': bool(found & set(expect)), 'cited': sorted(found), 'cites': len(found) + unfound,
            'unfound': unfound > 0, 'linked': bool(re.search(r'https?://[^\s)]+/ma/[^\s)]*/art_', answer))}
