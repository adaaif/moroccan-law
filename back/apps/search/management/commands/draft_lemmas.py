"""B4 of the search plan: the lemma of every Arabic word the index holds (seen --min times or more), from Haiku, so a
broken plural meets its singular («عقود» «عقد», «حقوق» «حق», «شروط» «شرط»). Haiku reads each stem's commonest written
word (derived/stem_words.json, by the corpus) and gives its dictionary form; the table maps the index's stem to the
lemma's stem (derived/lemmas.json), read by the index build and by every query the same way. Rules check each answer
(one Arabic word, sharing letters with the word); a provisional check by the editors stands until lawyers sample it.

    manage.py draft_lemmas --min 5 --write"""
import json
from pathlib import Path

import ma_law
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.corpus.services.llm import _worst_case, request, run_batch
from apps.sources.services.ocr import allow_spending

MODEL = 'claude-haiku-5-5'
PER_REQUEST = 250
SYSTEM = (
    'You give the dictionary form (lemma) of Arabic words from Moroccan legal texts. For each numbered word, written '
    'without vowel marks and with ة written ه and ى written ي, give the singular, masculine dictionary form a '
    'dictionary would list it under: a broken or sound plural gives its singular (عقود → عقد, حقوق → حق, شروط → شرط, '
    'المحاكم → محكمه, قوانين → قانون); a feminine or dual gives the base noun or adjective; a verb gives its past '
    'third-person masculine singular (يلتزم → التزم); a word with a pronoun or preposition attached gives the word alone '
    '(لحقوقه → حق). Keep the word itself when it is already its own dictionary form, a name, or not Arabic. Write the '
    'lemma folded the same way: no vowel marks, ة as ه, ى as ي, no article ال. One word only.')
SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['lemmas'],
    'properties': {'lemmas': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['n', 'lemma'],
        'properties': {'n': {'type': 'integer'}, 'lemma': {'type': 'string'}}}}},
}


def _plausible(word: str, lemma: str) -> bool:
    """One Arabic word that shares at least two letters with the word it lemmatizes."""
    return bool(lemma) and ' ' not in lemma and all('ء' <= c <= 'ي' for c in lemma) \
        and len(set(lemma) & set(word)) >= min(2, len(set(lemma)))


class Command(BaseCommand):
    help = 'Draft the lemma table with Haiku (B4).'

    def add_arguments(self, parser):
        parser.add_argument('--min', type=int, default=5, help='stems seen this many times or more')
        parser.add_argument('--write', action='store_true')

    def handle(self, *args, min, write, **opts):
        derived = Path(settings.CORPUS_DIR) / 'derived'
        source = derived / 'stem_words.json'
        if not source.exists():
            raise CommandError('derived/stem_words.json is missing: collect the stems\' words first.')
        stems = {s: v for s, v in json.loads(source.read_text()).items() if v[1] >= min and len(s) >= 2}
        order = sorted(stems, key=lambda s: -stems[s][1])
        reqs, meta = [], {}
        for i in range(0, len(order), PER_REQUEST):
            chunk = order[i:i + PER_REQUEST]
            cid = f'lemma-{i // PER_REQUEST:04d}'
            reqs.append(request(cid, model=MODEL, system=SYSTEM, schema=SCHEMA, max_tokens=12000,
                                content='\n'.join(f'{n} {stems[s][0]}' for n, s in enumerate(chunk, 1))))
            meta[cid] = chunk
        self.stdout.write(f'{len(order)} stems seen {min} times or more, {len(reqs)} requests; worst case ${_worst_case(reqs)}')
        if not write:
            return
        allow_spending(log=self.stdout.write)
        results = run_batch('search-lemmas', reqs, log=self.stdout.write)
        table, kept, refused = {}, 0, 0
        for cid, chunk in meta.items():
            for item in ((results.get(cid) or {}).get('data') or {}).get('lemmas', []):
                n = item.get('n')
                if not isinstance(n, int) or not 1 <= n <= len(chunk):
                    continue
                stem, word = chunk[n - 1], stems[chunk[n - 1]][0]
                lemma = ma_law.fold(item.get('lemma') or '')
                if not _plausible(word, lemma):
                    refused += 1
                    continue
                target = ma_law.stem(lemma)
                if target != stem:
                    table[stem] = target
                kept += 1
        (derived / 'lemmas.json').write_text(json.dumps({
            'about': 'B4 of the search plan: index stem → its lemma\'s stem, from Haiku 5.5 (draft_lemmas); owner-provisional.',
            'model': MODEL, 'min': min, 'lemmas': table}, ensure_ascii=False))
        self.stdout.write(f'{kept} stems lemmatized, {len(table)} of them to another stem, {refused} answers refused by the rules')
