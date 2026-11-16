"""What a citation names: the address of the text it cites, by its number, a code's name as it was on a day, or a
day and the words that tell a day's dahirs apart, kept for a run; the text an instruction amends; the words a text is
cited by."""
from functools import lru_cache

from apps.consolidation.services.instructions.amending import Instructions
from apps.consolidation.services.instructions.labels import plain
from apps.corpus.models import Mention
from apps.corpus.services import works


@lru_cache(maxsize=20000)
def _resolved(kind: str | None, number: str | None, code: str | None, on=None) -> tuple[str, str]:
    if code:
        uri = works.code_address(code, on)
        return (uri, Mention.State.RESOLVED) if uri else ('', Mention.State.UNRESOLVED)
    return works.resolve(kind, number)


@lru_cache(maxsize=20000)
def _dated(kind: str, day: str, words: str) -> tuple[str, str]:
    return works.resolve_dated(kind, day, words)


def where(c: dict, on=None, after: str = '') -> tuple[str, str]:
    """(address, state) of what a citation names (a code by its name as it was on `on`; a text before 1956 by its
    kind and day, `after` the words that tell apart a day's dahirs); an article named without its text is this
    text's own."""
    if c.get('code') or c.get('text_number'):
        return _resolved(c.get('text_kind'), c.get('text_number'), c.get('code') if not c.get('text_number') else None,
                         on if c.get('code') else None)
    if c.get('date') and c.get('text_kind'):
        return _dated(c['text_kind'], c['date'], after[:200])
    if c['kind'] == 'article':
        return '', Mention.State.SELF
    return '', Mention.State.UNRESOLVED


def target_of(ins: Instructions, on=None) -> tuple[str, str, str]:
    """(address, kind, number) of the text an instruction amends; a code named by its name is the one that was that code
    on `on`, the amending text's publication (28 Oct 2026: law 72.03 of 2004 had amended law 58.25 of 2026)."""
    t = ins.target or {}
    if t.get('code'):
        uri = works.code_address(t['code'], on)
        return uri, works.kind_of(uri) if uri else '', ''
    if t.get('number'):
        uri, state = _resolved(t.get('kind'), t['number'], None)
        return (uri, t.get('kind') or '', t['number']) if state == Mention.State.RESOLVED else ('', '', '')
    if t.get('date'):     # never guessed: a day with two dahirs the words do not tell apart is no target
        uri, state = _dated(t.get('kind') or '', t['date'], t.get('words', ''))
        return (uri, t.get('kind') or '', '') if state == Mention.State.RESOLVED else ('', '', '')
    return '', '', ''


def cited_title(body: str, c: dict) -> str:
    """The words a text is cited by: the citation and what follows it up to the dahir, a comma or the colon."""
    rest = plain(body[c['end']:c['end'] + 220])
    stop = min([i for i in (rest.find('، الصادر'), rest.find(' الصادر'), rest.find('،'), rest.find(':'), rest.find(' كما '),
                            rest.find('\n')) if i >= 0] or [len(rest)])
    return (c['raw'] + rest[:stop]).strip()
