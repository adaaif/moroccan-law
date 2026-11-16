"""Draft the everyday-words list (decision C2): Haiku gives, for each seed term, the Arabic terms Moroccan
legislation itself uses; the drafts go to CORPUS_DIR/reports/vocab/drafts.json for a person to review. Nothing
here reaches the search: only `apply_vocab` writes the approved entries into apps/search/data/everyday.json."""
import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.corpus.services.llm import request, run_batch
from apps.sources.services.ocr import allow_spending

SEEDS = Path(__file__).resolve().parents[2] / 'data' / 'everyday_seeds.json'
MODEL = 'claude-haiku-5-5'
SYSTEM = (
    'You help a free search engine of Moroccan legislation (the Bulletin officiel, Arabic edition). People type '
    'everyday words: French administrative acronyms and terms, Darija, colloquial Arabic. For each typed term, give '
    'the Arabic terms that Moroccan legal texts themselves use for the same thing, written as the Bulletin officiel '
    'writes them (formal Arabic): most common first, at most 3, each at most 7 words. When the term has no clear '
    'equivalent in Moroccan legislation, give an empty list. Set sure to false when you are not confident. Never '
    'explain, and never give a term Moroccan legislation does not use.')
SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['entries'],
    'properties': {'entries': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['typed', 'means', 'sure'],
        'properties': {'typed': {'type': 'string'}, 'means': {'type': 'array', 'items': {'type': 'string'}},
                       'sure': {'type': 'boolean'}}}}},
}


class Command(BaseCommand):
    help = 'Draft the everyday-words list with Haiku, for review.'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')

    def handle(self, *args, **opts):
        allow_spending(opts['write'], log=self.stdout.write)
        seeds = json.loads(SEEDS.read_text())
        groups = {k: v for k, v in seeds.items() if isinstance(v, list)}
        requests = [request(f'vocab-{kind}', model=MODEL, system=SYSTEM, schema=SCHEMA, max_tokens=8000,
                            content='Typed terms, one a line:\n' + '\n'.join(terms))
                    for kind, terms in groups.items()]
        results = run_batch('vocab', requests, log=self.stdout.write)
        drafts = []
        for kind, terms in groups.items():
            got = (results.get(f'vocab-{kind}') or {}).get('data') or {'entries': []}
            for e in got['entries']:
                if e['typed'] in terms and e['means']:
                    drafts.append({'typed': e['typed'], 'kind': kind, 'means': e['means'][:3], 'sure': e['sure']})
        out = Path(settings.CORPUS_DIR) / 'reports' / 'vocab' / 'drafts.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({'date': date.today().isoformat(), 'model': MODEL, 'drafts': drafts},
                                  ensure_ascii=False, indent=1))
        self.stdout.write(f'{len(drafts)} drafts of {sum(map(len, groups.values()))} seed terms → {out}')
