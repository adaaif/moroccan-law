"""Row L12 of the links review: a model reads the amending articles the code could not, into the same changes the code
writes. Left out are the articles that change an annex or a table: the site does not cut those into parts, so no reading
of them could be placed.

The model is one more witness, never more. Its reading is kept (Change, source «model», by the amending article's
address) only where the text it names is one the article cites and every quoted line it gives stands in the article
as printed; the pipeline then shows it as fact only when another source agrees (the SGG's or Adala's notes, or the
model's first description of the text in texts.json). Texts published from 2019 only.

    read_unclear                # count and price, send nothing
    read_unclear --write        # one batch, within OCR_BUDGET_USD
"""
import json
from collections import defaultdict
from datetime import date

import ma_law
from django.core.management.base import BaseCommand

from apps.consolidation.models import Change, Doubt, Verb
from apps.consolidation.services import engine, fill
from apps.consolidation.services.instructions.labels import DOTS, label_key
from apps.corpus.models import Article, Consolidation, Text
from apps.corpus.services import works
from apps.corpus.services.llm import _worst_case, request, run_batch
from apps.sources.services.ocr import allow_spending

MODEL = 'claude-haiku-5-5'
FROM = date(2019, 1, 1)
VERBS = {'modify': Verb.MODIFIED, 'add': Verb.ADDED, 'replace': Verb.REPLACED, 'repeal': Verb.REPEALED,
         'words': Verb.WORDS}
SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['changes'],
    'properties': {'changes': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False,
        'required': ['action', 'target_kind', 'target_number', 'article', 'new_wording', 'old_words', 'new_words'],
        'properties': {
            'action': {'type': 'string', 'enum': ['modify', 'add', 'replace', 'repeal', 'words']},
            'target_kind': {'type': 'string', 'enum': ['law', 'organic_law', 'dahir', 'decree', 'decree_law', 'order',
                                                      'other']},
            'target_number': {'type': 'string', 'description': 'the changed text\'s number as printed, e.g. 2.00'},
            'article': {'type': 'string', 'description': 'the changed article\'s number as printed (7.1, 5 مكرر); '
                                                         'empty when the whole text is repealed'},
            'new_wording': {'type': 'array', 'items': {'type': 'string'},
                            'description': 'the new wording quoted in the article, copied exactly, one line each, dots '
                                           'kept; empty for a repeal or a swap of words'},
            'old_words': {'type': 'string', 'description': 'for a swap of words: the words replaced'},
            'new_words': {'type': 'string', 'description': 'for a swap of words: the words put in their place'},
        }}}},
}
SYSTEM = (
    'You read ONE article of the Moroccan Bulletin Officiel that changes other legal texts, and list each change it '
    'makes: the action (modify, add, replace, repeal, or words when it swaps words), the kind and number of the text '
    'it changes, the number of the article changed, and the new wording exactly as quoted, line by line, keeping any '
    'dots. Copy words only from the article; never complete, correct or summarise. Leave out a change you cannot read '
    'plainly, and any change to a table, an annex or a list attached to a text. Return an empty list when unsure.'
)


def wanted() -> list[tuple[Text, Article, str]]:
    """The amending articles to read: unclear to the code (not an annex) or naming no text it could find."""
    keys = set()
    for by, label, why in Change.objects.filter(source=Change.Source.READING, state=Change.State.UNCLEAR).values_list(
            'by_uri', 'by_article', 'detail__why'):
        if why != 'annex':
            keys.add((by, label))
    for by, label, detail in Doubt.objects.filter(reason__in=(Doubt.Reason.UNCLEAR, Doubt.Reason.TARGET_UNKNOWN),
                                                  status=Doubt.Status.OPEN).values_list('by_uri', 'by_article', 'detail'):
        if (detail or {}).get('why') != 'annex':
            keys.add((by, label))
    done = set(Change.objects.filter(source=Change.Source.MODEL).values_list('by_uri', 'by_article'))
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in={k[0] for k in keys}, first_published_in__date__gte=FROM)
             .select_related('first_published_in')}
    out = []
    for by, label in sorted(keys - done):
        text = texts.get(by)
        if text is None:
            continue
        article = Article.objects.filter(version__text=text, version__consolidation=Consolidation.AS_PUBLISHED,
                                         label=label).first()
        if article is not None:
            out.append((text, article, f'{text.pk}-{article.pk}'))
    return out


def stands(line: str, body: str) -> bool:
    """A quoted line the model gave stands in the article: each stretch between its dots is printed there."""
    parts = [p.strip(' «»') for p in DOTS.split(line) if len(p.strip(' «»')) > 3]
    return all(fill.stream(p) in fill.stream(body) for p in parts) if parts else not line.strip()


def verified(text: Text, article: Article, item: dict) -> Change | None:
    number = works.fold(item['target_number'].replace('.', '-').strip())
    cited = {works.fold(c['text_number']) for c in ma_law.parse_citations(article.body) if c.get('text_number')}
    if number not in cited:
        return None
    uri, state = works.resolve(item['target_kind'] if item['target_kind'] != 'other' else None, number)
    if state != 'resolved':
        return None
    lines = [ln for ln in item['new_wording'] if ln.strip()]
    if not all(stands(ln, article.body) for ln in lines):
        return None
    if item['action'] == 'words' and not (item['old_words'] and item['new_words'] and stands(item['old_words'], article.body)
                                          and stands(item['new_words'], article.body)):
        return None
    if item['action'] in ('modify', 'add', 'replace') and not lines:
        return None
    label = item['article'].strip()
    key = label_key(label if not label[:1].isdigit() else f'المادة {label}') if label else ''
    issue = text.first_published_in
    on, rule, words = engine.takes_effect(engine.own_rule(list(article.version.articles.all())), issue.date if issue else None)
    return Change(text_uri=uri, number=key, verb=VERBS[item['action']], source=Change.Source.MODEL, by_kind=text.type,
                  by_number=works.fold(text.number), by_uri=text.akn_uri, by_article=article.label,
                  issue=issue.number if issue else None, issue_bis=bool(issue and issue.suffix), page=article.printed_page,
                  published_on=issue.date if issue else None, effective_on=on, effective_rule=rule,
                  effective_words=words[:600],
                  wording=lines if item['action'] != 'words' else [f"«{item['old_words']}» ← «{item['new_words']}»"],
                  detail={'by_model': True, 'dotted': any(DOTS.search(ln) for ln in lines), 'label': label,
                          **({'pairs': [[item['old_words'], item['new_words']]]} if item['action'] == 'words' else {})})


class Command(BaseCommand):
    help = 'A model reads the amending articles the code could not (a witness, never placed on its word alone).'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')
        parser.add_argument('--dry-run', action='store_true', help='count and price only (what it does without --write)')

    def handle(self, *args, write: bool, dry_run: bool, **opts):
        items = wanted()
        requests = [request(key, model=MODEL, system=SYSTEM, content=f'{text.title_ar}\n\n{article.label}\n{article.body}',
                            schema=SCHEMA, max_tokens=4000) for text, article, key in items]
        self.stdout.write(f'{len(items)} articles; worst case ${_worst_case(requests) if requests else 0}')
        if dry_run or not write or not requests:
            return
        allow_spending(log=self.stdout.write)
        results = run_batch('links:unclear', requests, log=self.stdout.write)
        kept, dropped = [], defaultdict(int)
        for text, article, key in items:
            data = (results.get(key) or {}).get('data') or {}
            for item in data.get('changes', []):
                change = verified(text, article, item)
                if change is None:
                    dropped[item.get('action', '?')] += 1
                else:
                    kept.append(change)
        Change.objects.bulk_create(kept)
        self.stdout.write(f'kept {len(kept)} changes the article bears out; set aside {dict(dropped)}')
        self.stdout.write(json.dumps({'texts': sorted({c.by_uri for c in kept})}, ensure_ascii=False)[:2000])
