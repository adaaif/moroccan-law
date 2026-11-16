"""A second copy as witness for a reading (A7 of the consumer plan): a scanned BO page has no text layer, so nothing
confirms what the model read on it. Where Adala or the SGG keeps the same text, made from other files by other hands,
each article of the BO's version is set beside the witness's. Articles that say the same words are confirmed by two
independent copies; the rest are listed with the words each side alone holds, for a second reading and a person.

An article changed between the two dates (a Change the site knows, whatever its source) is set apart: the copies differ
there because the law did, not because a reading did.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from types import SimpleNamespace
from difflib import SequenceMatcher

from apps.consolidation.models import Change
from apps.corpus.models import Text, Version
from apps.sources.services.compare import cer, fold, word_f1

# Two readings of one article agree when their folded words overlap this much and their letters differ this little
# (a missing «و» in an article of 200 words passes; a dropped line does not), or when their letters, spaces left out,
# differ this little: a layer that splits a word («والم خلاصات») or glues two («عملهمن») reads the same letters.
AGREE_F1 = 0.98
AGREE_CER = 0.03
AGREE_LETTERS = 0.015


@dataclass
class Row:
    number: str
    label: str
    status: str              # agree · differ · changed · only_bo · only_witness
    f1: float = 0.0
    cer: float = 0.0
    bo_only: list[str] = field(default_factory=list)
    witness_only: list[str] = field(default_factory=list)


def _version(text: Text, consolidation: str) -> Version | None:
    qs = text.versions.filter(language='ar', consolidation=consolidation)
    # The BO's version is the first one published; a witness's, its newest copy.
    return (qs.order_by('valid_from') if consolidation == 'as_published' else qs.order_by('-valid_from')).first()


def changed_between(text: Text, start, end) -> set[str]:
    """The article numbers some text changed after `start` and up to `end`, by the changes the site knows ('' = whole)."""
    out = set()
    for c in Change.objects.filter(text_uri=text.akn_uri):
        by = Text.objects.filter(akn_uri=c.by_uri).select_related('first_published_in').first() if c.by_uri else None
        when = by.first_published_in.date if by and by.first_published_in_id else None
        if when is None or start < when <= end:
            out.add(c.number)
    return out


def _words_apart(a: str, b: str, most: int = 12) -> tuple[list[str], list[str]]:
    """The runs of words only `a` holds and only `b` holds, in their order (folded)."""
    x, y = fold(a).split(), fold(b).split()
    only_a, only_b = [], []
    for op, i1, i2, j1, j2 in SequenceMatcher(None, x, y, autojunk=False).get_opcodes():
        if op in ('replace', 'delete'):
            only_a.append(' '.join(x[i1:i2]))
        if op in ('replace', 'insert'):
            only_b.append(' '.join(y[j1:j2]))
    return only_a[:most], only_b[:most]


# Where a text is signed («وحرر بالرباط في …», then «الإمضاء: …»): Adala keeps it in the last article, the BO's cut
# puts it after the text. Neither is the article's words.
_SIGNED = re.compile(r'^\s*و?حرر\s+ب', re.M)


def _unsigned(body: str) -> str:
    m = _SIGNED.search(body)
    return body[:m.start()] if m else body


def compare(text: Text, witness: str = 'adala', base: str = 'as_published', file: str | None = None) -> dict:
    """The BO's version of `text` against the witness's copy, article by article. `file`: Adala's copy read from its
    PDF, for a text whose Adala version the BO's took the place of (same date: decree 2.12.503, 24 Oct 2026)."""
    bo = _version(text, base)
    if file:
        from apps.consolidation.services import adala
        read = adala.read(file)
        wit = SimpleNamespace(valid_from=read.text.as_of or date.today())
        listed = [SimpleNamespace(number=a.number, label=a.label, body=a.body) for a in read.text.articles]
    else:
        wit = _version(text, witness)
        listed = list(wit.articles.all()) if wit else []
    if bo is None or wit is None:
        return {'text': text.akn_uri, 'error': f'no {base if bo is None else witness} version'}
    changed = changed_between(text, bo.valid_from, wit.valid_from)
    ours = {a.number or a.label: a for a in bo.articles.all()}
    theirs = {a.number or a.label: a for a in listed}
    rows: list[Row] = []
    for n, a in ours.items():
        w = theirs.get(n)
        if w is None:
            rows.append(Row(n, a.label, 'only_bo'))
            continue
        fa, fw = fold(_unsigned(a.body)), fold(_unsigned(w.body))
        f1, c = word_f1(fw, fa), cer(fw, fa)
        letters = cer(fw.replace(' ', ''), fa.replace(' ', ''))
        same = (f1 >= AGREE_F1 and c <= AGREE_CER) or letters <= AGREE_LETTERS
        status = 'agree' if same else ('changed' if n in changed or '' in changed else 'differ')
        row = Row(n, a.label, status, round(f1, 4), round(c, 4))
        if status != 'agree':
            row.bo_only, row.witness_only = _words_apart(a.body, w.body)
        rows.append(row)
    rows += [Row(n, w.label, 'only_witness') for n, w in theirs.items() if n not in ours]
    counted = [r for r in rows if r.status in ('agree', 'differ')]
    agree = sum(1 for r in counted if r.status == 'agree')
    return {
        'text': text.akn_uri, 'base': {'consolidation': base, 'from': str(bo.valid_from), 'pages': bo.source_pages},
        'witness': {'consolidation': witness, 'from': str(wit.valid_from), **({'file': file} if file else {})},
        'articles': len(rows), 'compared': len(counted), 'agree': agree,
        'share': round(agree / len(counted), 4) if counted else None,
        'changed': sum(1 for r in rows if r.status == 'changed'),
        'only_bo': sum(1 for r in rows if r.status == 'only_bo'),
        'only_witness': sum(1 for r in rows if r.status == 'only_witness'),
        'rows': [asdict(r) for r in rows],
    }
