"""B9 of the search plan (25 Oct 2026): Haiku reads each article once, for the index. For every article it writes what the
article does inside its text (a sentence in Arabic and one in French), eight searches it answers in the test set's
registers, the legal concepts it uses, its role and its facts. None of it is shown to readers as the law: it is index
material (B9's context is read before the article's passages by the meaning model; the searches are measured as passages
of their own and as a hidden BM25 field).

Kept by address, version and prompt version (CORPUS_DIR/derived/search_surrogates.jsonl, shared by every database): a
changed article is read again, nothing else. A rule drops a search that names the article's number or copies its
wording; a provisional check by the editors stands until lawyers read a sample (`checked: owner-provisional`). The
shelf came first, inside the $5 cap (25 Oct 2026); the core and the rest wait for the measured gain."""
import json
import re
from functools import lru_cache
from pathlib import Path

import ma_law
from django.conf import settings

from apps.corpus.services.llm import request
from apps.search.models import SearchEntry
from apps.search.services.testset import REGISTERS

MODEL = 'claude-haiku-5-5'
PROMPT = 's2'
FILE = 'derived/search_surrogates.jsonl'
BODY_MAX = 4000          # an article's first characters, as the test set's drafts read them
GROUP_CHARS = 6000       # a request holds a text's articles in order, up to this many characters
GROUP_MAX = 6            # and this many articles
LETTERS = 'ABCDEFGH'     # an article's key in a request: a number was taken for the article's own («الفصل 6»)
# Two of each Arabic register people use most, one of the others: eight searches an article.
ASKED = ('msa', 'msa', 'darija', 'darija', 'darija_latin', 'french', 'english', 'professional')
ROLES = ('definition', 'right', 'obligation', 'prohibition', 'sanction', 'procedure', 'deadline', 'competence',
         'transitional', 'repeal', 'entry_into_force', 'formal')
FACTS = ('duration', 'amount', 'rate', 'age', 'actor', 'institution', 'defined_term')
# An article with nothing to ask about: empty, or only says it was repealed.
EMPTY = re.compile(r'^\W*(?:\(?\s*(?:نسخ|ينسخ|ألغي|ملغى|abrogé)[^)]{0,60}\)?)?\W*$')

SYSTEM = (
    'You prepare index material for a free search engine of Moroccan law. Readers never see what you write: it only '
    'helps the engine find each article when people search in their own words. You get articles of one Moroccan '
    'legal text, each after a letter in square brackets ([A], [B]…) and with the headings it sits under. For EVERY '
    'article, write (key: its letter, never the article\'s own number):\n'
    '- context_ar: one sentence in Arabic on what the article does inside this text (its subject and effect), so the '
    'article can be understood alone. Name what the article refers to («الفصل 574» → what that article is about) when '
    'the text makes it clear; never invent.\n'
    '- context_fr: the same sentence in French.\n'
    '- searches: exactly eight searches a real person in Morocco would type whose answer is in this article, one for '
    'each register asked, in the order given. Write as people type: their own words for their situation, not the '
    'article\'s wording; never copy a phrase of four words or more from the article; never give the article\'s number; '
    'only the professional register may name the text. At most 20 words each.\n'
    '- concepts: one to five legal concepts the article is about, as short Arabic legal terms.\n'
    '- role: what the article mainly does.\n'
    '- facts: the durations, amounts, rates, ages, actors, institutions and defined terms it states, each with the '
    'words exactly as the article writes them (empty when none).\n'
    'An article that only publishes, starts or repeals a text still gets its context, role and facts; its searches '
    'ask about what it repeals or starts.\n'
    'Registers:\n' + '\n'.join(f'- {name}: {desc}. For example: {example}' for name, (desc, example) in REGISTERS.items()))

SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['articles'],
    'properties': {'articles': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False,
        'required': ['key', 'context_ar', 'context_fr', 'searches', 'concepts', 'role', 'facts'],
        'properties': {
            'key': {'type': 'string'},
            'context_ar': {'type': 'string'},
            'context_fr': {'type': 'string'},
            'searches': {'type': 'array', 'items': {'type': 'string'}},
            'concepts': {'type': 'array', 'items': {'type': 'string'}},
            'role': {'type': 'string', 'enum': list(ROLES)},
            'facts': {'type': 'array', 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['kind', 'words'],
                'properties': {'kind': {'type': 'string', 'enum': list(FACTS)}, 'words': {'type': 'string'}}}},
        }}}},
}


def _file() -> Path:
    return Path(settings.CORPUS_DIR) / FILE


def key(path: str, version: str | None) -> tuple:
    return path, version or ''


def load() -> dict[tuple, dict]:
    """{(address, version): row} of the current prompt; a later row for the same article wins."""
    out = {}
    if _file().exists():
        for line in _file().read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get('prompt') == PROMPT:
                    out[key(row['path'], row['version'])] = row
    return out


def save(rows: list[dict]) -> None:
    _file().parent.mkdir(parents=True, exist_ok=True)
    with _file().open('a') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def todo(paths: list[str] | None = None, text_paths: list[str] | None = None) -> list[SearchEntry]:
    """The index's articles still to read, in each text's order: of `text_paths`, or the articles at `paths`."""
    rows = SearchEntry.objects.filter(kind=SearchEntry.Kind.ARTICLE)
    if text_paths is not None:
        rows = rows.filter(text_path__in=text_paths)
    if paths is not None:
        rows = rows.filter(path__in=paths)
    done = load()
    return [r for r in rows.order_by('text_path', 'order').only('path', 'text_path', 'label', 'heading_path', 'body',
                                                                'version_from')
            if not EMPTY.match(r.body) and key(r.path, _version(r)) not in done]


def _version(r) -> str:
    return r.version_from.isoformat() if r.version_from else ''


def groups(rows: list[SearchEntry]) -> list[list[SearchEntry]]:
    """A text's articles in order, a request at most GROUP_MAX of them or GROUP_CHARS characters."""
    out: list[list[SearchEntry]] = []
    for r in rows:
        last = out[-1] if out else None
        if (last and last[0].text_path == r.text_path and len(last) < GROUP_MAX
                and sum(min(len(x.body), BODY_MAX) for x in last) + min(len(r.body), BODY_MAX) <= GROUP_CHARS):
            last.append(r)
        else:
            out.append([r])
    return out


def requests(chunks: list[list[SearchEntry]], names: dict[str, str]) -> tuple[list[dict], dict[str, list]]:
    asked = ', '.join(ASKED)
    reqs, meta = [], {}
    for i, chunk in enumerate(chunks):
        cid = f's{i:05d}'
        parts = [f'Text: {names.get(chunk[0].text_path, chunk[0].text_path)}', f'Registers, in order: {asked}']
        for n, r in enumerate(chunk):
            parts.append(f'[{LETTERS[n]}] {" › ".join(r.heading_path or []) or "-"} › {r.label}\n{r.body[:BODY_MAX]}')
        reqs.append(request(cid, model=MODEL, system=SYSTEM, content='\n\n'.join(parts), schema=SCHEMA,
                            max_tokens=800 + 1200 * len(chunk), think=False))
        meta[cid] = chunk
    return reqs, meta


def _copies(search: str, body: str) -> bool:
    """The search repeats four words in a row of the article (folded), or gives its number."""
    words = ma_law.fold(search).split()
    folded = f' {" ".join(ma_law.fold(body).split())} '
    return any(f' {" ".join(words[i:i + 4])} ' in folded for i in range(len(words) - 3))


def rows_from(meta: dict[str, list], results: dict[str, dict]) -> tuple[list[dict], int, int]:
    """(rows to keep, searches dropped by the rules, articles with no answer)."""
    rows, dropped, missing = [], 0, 0
    for cid, chunk in meta.items():
        answers = {(a.get('key') or '').strip('[] '): a for a in ((results.get(cid) or {}).get('data') or {}).get('articles', [])}
        for n, r in enumerate(chunk):
            a = answers.get(LETTERS[n])
            if not a or not a.get('context_ar'):
                missing += 1
                continue
            number = re.search(r'\d+', r.label or '')
            searches = []
            for register, s in zip(ASKED, a.get('searches') or []):
                s = ' '.join(s.split())
                if not s or _copies(s, r.body) or (number and register != 'professional'
                                                   and re.search(rf'(?<!\d){number.group()}(?!\d)', s)):
                    dropped += 1
                    continue
                searches.append({'q': s, 'register': register})
            rows.append({'path': r.path, 'text_path': r.text_path, 'version': _version(r), 'prompt': PROMPT,
                         'model': MODEL, 'context_ar': a['context_ar'].strip(), 'context_fr': a['context_fr'].strip(),
                         'searches': searches, 'concepts': [c.strip() for c in a.get('concepts') or [] if c.strip()][:5],
                         'role': a.get('role', ''), 'facts': a.get('facts') or [], 'checked': 'owner-provisional'})
    return rows, dropped, missing


AMOUNTS = ('duration', 'amount', 'rate', 'age')


def facts(path: str) -> list[str]:
    """The durations, amounts, rates and ages B9 read in an article, as the article writes them (B15 finds them word
    for word in the sentence it shows); kept in memory while the file holds."""
    f = _file()
    return _facts(f.stat().st_mtime if f.exists() else 0).get(path, [])


@lru_cache(maxsize=1)
def _facts(stamp: float) -> dict[str, list[str]]:
    return {path: [x['words'] for x in r['facts'] if x.get('kind') in AMOUNTS and x.get('words')]
            for (path, _), r in load().items() if r.get('facts')}
