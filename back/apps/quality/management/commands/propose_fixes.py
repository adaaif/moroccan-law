"""Corrections a text's copies agree on (A1 of the consumer plan): the version readers see (`--base`, the SGG's) set
word by word beside a second copy (`--witness`, Adala's), and every place they part judged by a third, the BO's
reading of the page (`--judge`). A place becomes a correction only when the witness and the judge say the same words
and the base's are not in the judge: two copies made from other files by other hands. The corrections go to a YAML
file `apply_page_reading` takes (the base's words as they stand, one each side to find them once); the places the
judge could not settle are listed for a person, never written.

    propose_fixes /akn/ma/act/loi/31-08 --out apps/quality/data/consumer_31_08.yaml
"""
import re
from difflib import SequenceMatcher
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError

from apps.corpus.models import Text
from apps.corpus.services.addresses import text_path
from apps.sources.services.compare import fold


def _version(text, consolidation):
    qs = text.versions.filter(language='ar', consolidation=consolidation)
    return (qs.order_by('valid_from') if consolidation == 'as_published' else qs.order_by('-valid_from')).first()


def _find(body: str, tokens: list[str]) -> str | None:
    """The base's own words for these tokens, as the body spells them (its spaces and line breaks)."""
    pattern = r'\s+'.join(re.escape(t) for t in tokens)
    found = list(re.finditer(pattern, body))
    return found[0].group(0) if len(found) == 1 else None


def places(base: str, witness: str):
    """Where two copies of an article part, as (base tokens with one word of context each side, the witness's words
    in their place, the base's own words)."""
    b, w = base.split(), witness.split()
    fb, fw = [fold(t) for t in b], [fold(t) for t in w]
    for op, i1, i2, j1, j2 in SequenceMatcher(None, fb, fw, autojunk=False).get_opcodes():
        if op == 'equal':
            continue
        lo, hi = max(0, i1 - 1), min(len(b), i2 + 1)
        before, after = b[lo:i1], b[i2:hi]
        yield b[lo:hi], before + w[j1:j2] + after, b[i1:i2], w[j1:j2]


class Command(BaseCommand):
    help = "Corrections two other copies agree on, for apply_page_reading."

    def add_arguments(self, parser):
        parser.add_argument('uri')
        parser.add_argument('--base', default='sgg')
        parser.add_argument('--witness', default='adala')
        parser.add_argument('--judge', default='as_published')
        parser.add_argument('--out', required=True, help='the YAML file to write, under back/')
        parser.add_argument('--changed', default='', help='article numbers changed since the BO, never judged by it')
        parser.add_argument('--show', type=int, default=15, help='how many places left for a person to print')

    def handle(self, *args, uri, base, witness, judge, out, changed, show, **opts):
        text = Text.objects.filter(akn_uri=uri).first()
        if text is None:
            raise CommandError(f'{uri}: not in the corpus')
        vb, vw, vj = _version(text, base), _version(text, witness), _version(text, judge)
        if not (vb and vw and vj):
            raise CommandError(f'{uri}: needs its {base}, {witness} and {judge} versions')
        skip = {n.strip() for n in changed.split(',') if n.strip()}
        theirs = {a.number: a for a in vw.articles.all()}
        judged = {a.number: fold(a.body) for a in vj.articles.all()}
        fixes, open_places = [], []
        for a in vb.articles.all():
            w = theirs.get(a.number)
            if w is None or a.number in skip:
                continue
            j = judged.get(a.number)
            for tokens, right_tokens, ours, wits in places(a.body, w.body):
                core_w, core_b = fold(' '.join(wits)), fold(' '.join(ours))
                if not core_w.replace(' ', '') and not core_b.replace(' ', ''):
                    continue                     # only punctuation parts them
                wrong = _find(a.body, tokens)
                verdict = None
                if j is not None and wrong:
                    has_w = (not core_w) or core_w in j or core_w.replace(' ', '') in j.replace(' ', '')
                    has_b = bool(core_b) and (core_b in j)
                    # The base's words split or glued the witness's own («والم خلاصات», «عملهمن»): the letters agree.
                    same_letters = core_w.replace(' ', '') == core_b.replace(' ', '')
                    if has_w and (not has_b or same_letters):
                        verdict = 'fix'
                    # With a word each side the place is the judge's own: «يطالب المقرض به» read there, «يطالب
                    # القرض به» not, though «القرض» stands elsewhere in the article.
                    elif fold(' '.join(right_tokens)) in j and fold(' '.join(tokens)) not in j:
                        verdict = 'fix'
                row = {'arts': [a.number], 'wrong': wrong or ' '.join(tokens), 'right': ' '.join(right_tokens)}
                (fixes if verdict == 'fix' else open_places).append(row)
        path = Path(out)
        data = {'text': text_path(text.akn_uri), 'document': vb.source_document.path if vb.source_document else '',
                'read_on': str(__import__('datetime').date.today()),
                'fixes': fixes, 'notes': [], 'checked': sorted({f['arts'][0] for f in fixes}, key=lambda x: (len(x), x))}
        path.write_text('# ' + f'{text_path(text.akn_uri)} as the {base.upper()} prints it, put right where {witness}\'s copy and the {judge} '
                        'reading of the BO page agree (propose_fixes, A1 of the consumer plan).\n'
                        + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200), encoding='utf-8')
        self.stdout.write(f'{uri}: {len(fixes)} corrections written to {out}; {len(open_places)} places left for a person')
        for row in open_places[:show]:
            self.stdout.write(f'   ? {row["arts"][0]}: «{row["wrong"]}» / {witness}: «{row["right"]}»')
