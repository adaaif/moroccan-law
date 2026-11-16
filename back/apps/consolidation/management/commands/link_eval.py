"""How far the site's links can be trusted (row L11 of the links review), before they are shown as fact.

Changes are measured against the notes of two others who keep the same history: the SGG's under each article of its
consolidated texts, and Adala's footnotes. A note counts when the text that made the change is one the site has read
from the BO (so the site could have read the change too) and it was published from 2019:

  recall      the notes our reading also has (same text, article and amending text);
  precision   of our readings on a text the SGG keeps up to date past them, those a note bears out; one no note
              records is counted against the site (the SGG's notes may miss a change, so this errs low).

Citations are counted by state, and each one linked is checked to lead to a text of the kind its words name.
`--sample N` also writes N links (half changes, half citations) with their BO issue and page, for a person to check
against the page.

    link_eval
    link_eval --sample 200
"""
import json
import random
import re
from collections import Counter, defaultdict
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.consolidation.models import Change
from apps.consolidation.services.engine.shared import SHOWN, variants
from apps.corpus.models import Consolidation, Mention, Text
from apps.corpus.services import works
from apps.corpus.services.addresses import text_path

FROM = date(2019, 1, 1)
KIND_WORDS = {'law': ('law', 'organic_law'), 'organic_law': ('organic_law', 'law'), 'dahir': ('dahir', 'law', 'organic_law'),
              'decree': ('decree', 'decree_law'), 'decree_law': ('decree_law', 'decree'), 'order': ('order',)}


def _pct(a: int, b: int) -> float | None:
    return round(100 * a / b, 1) if b else None


def changes_eval() -> dict:
    read_from_bo = set(Text.objects.filter(versions__consolidation=Consolidation.AS_PUBLISHED)
                       .values_list('akn_uri', flat=True))
    readings = defaultdict(list)
    for c in Change.objects.filter(source=Change.Source.READING):
        readings[(c.text_uri, c.by_uri)].append(c)
    out = {}
    for source in (Change.Source.SGG, Change.Source.ADALA):
        notes = [n for n in Change.objects.filter(source=source) if n.by_uri in read_from_bo
                 and n.published_on and n.published_on >= FROM]
        found, by_year, states = 0, defaultdict(lambda: [0, 0]), Counter()
        for n in notes:
            mine = readings.get((n.text_uri, n.by_uri), [])
            hit = next((c for c in mine if c.number in variants(n.number) or (not n.number and not c.number)), None)
            by_year[n.published_on.year][1] += 1
            if hit:
                found += 1
                by_year[n.published_on.year][0] += 1
                states[hit.state] += 1
            else:
                states['missed'] += 1
        out[source] = {'notes': len(notes), 'found': found, 'recall': _pct(found, len(notes)), 'states': dict(states),
                       'by_year': {y: {'found': f, 'notes': t, 'recall': _pct(f, t)} for y, (f, t) in sorted(by_year.items())}}

    # Precision: readings on a text the SGG keeps, dated on or before its consolidation.
    kept = {}
    for t in Text.objects.filter(versions__consolidation=Consolidation.SGG).distinct():
        v = t.versions.filter(consolidation=Consolidation.SGG).select_related('source_document').first()
        as_of = v.source_document.meta.get('as_of') if v and v.source_document_id else None
        if as_of:
            kept[t.akn_uri] = date.fromisoformat(as_of)
    noted = defaultdict(set)
    for uri, number, by in Change.objects.filter(source=Change.Source.SGG).values_list('text_uri', 'number', 'by_uri'):
        noted[(uri, by)].add(number)
    tally = defaultdict(Counter)
    examples = defaultdict(list)
    for c in Change.objects.filter(source=Change.Source.READING, text_uri__in=list(kept)):
        if not c.published_on or c.published_on < FROM or c.published_on > kept[c.text_uri]:
            continue
        numbers = noted.get((c.text_uri, c.by_uri), set())
        if any(n in variants(c.number) for n in numbers) or (not c.number and numbers):
            verdict = 'note'                 # the SGG's note records this change
        elif c.verdict == Change.Verdict.AGREES or (c.witnesses or {}).get('wording'):
            verdict = 'wording'              # the SGG's later text holds the new wording
        elif c.verdict in (Change.Verdict.DISAGREES, Change.Verdict.ABSENT):
            verdict = 'against'              # the SGG's later text does not bear it out
        else:
            verdict = 'silent'               # no note, nothing to compare (a whole-text change, an annex)
        tally[c.state][verdict] += 1
        if verdict in ('against', 'silent') and len(examples[f'{c.state}:{verdict}']) < 8:
            examples[f'{c.state}:{verdict}'].append({'text': text_path(c.text_uri), 'article': c.number,
                                                     'by': text_path(c.by_uri), 'issue': c.issue, 'page': c.page,
                                                     'verb': c.verb})

    def rate(counts):
        judged = counts['note'] + counts['wording'] + counts['against']
        return {**counts, 'precision': _pct(counts['note'] + counts['wording'], judged)}

    precision = {state: rate(counts) for state, counts in tally.items()}
    shown = Counter()
    for state in SHOWN:
        shown.update(tally.get(state, {}))
    out['precision'] = {'texts': len(kept), 'by_state': precision, 'shown': rate(shown), 'examples': examples}
    return out


def mentions_eval() -> dict:
    states = Counter(Mention.objects.values_list('state', flat=True))
    kinds = Counter(Mention.objects.values_list('kind', flat=True))
    held = set(Text.objects.filter(versions__isnull=False).values_list('akn_uri', flat=True))
    linked = Mention.objects.filter(state=Mention.State.RESOLVED, kind=Mention.Kind.CITES).exclude(to_uri='')
    import ma_law
    wrong_kind = checked = in_corpus = 0
    examples = []
    for m in linked.iterator(chunk_size=5000):
        if m.to_uri in held:
            in_corpus += 1
        cites = [c for c in ma_law.parse_citations(m.words) if c.get('text_kind')]
        if not cites:
            continue
        checked += 1
        kind = works.kind_of(m.to_uri)
        # «قانون رقم 1.77.340» is a dahir having force of law, numbered as a dahir is (1.x.x): its own kind.
        dahir_numbered = kind == 'dahir' and re.match(r'1-\d+-\d+$', cites[0].get('text_number') or '')
        if kind not in KIND_WORDS.get(cites[0]['text_kind'], (cites[0]['text_kind'],)) and not dahir_numbered:
            wrong_kind += 1
            if len(examples) < 10:
                examples.append({'words': m.words[:120], 'to': text_path(m.to_uri)})
    return {'states': dict(states), 'kinds': dict(kinds), 'resolved': linked.count(), 'resolved_in_corpus': in_corpus,
            'kind_checked': checked, 'wrong_kind': wrong_kind, 'wrong_kind_examples': examples}


def hand_sample(n: int) -> list[dict]:
    random.seed(19)
    changes = list(Change.objects.filter(source=Change.Source.READING, state__in=SHOWN, published_on__gte=FROM))
    held = set(Text.objects.filter(versions__isnull=False).values_list('akn_uri', flat=True))
    mentions = [m for m in Mention.objects.filter(state=Mention.State.RESOLVED, kind=Mention.Kind.CITES)
                .exclude(from_eid='').exclude(to_uri='') if m.to_uri in held and m.to_uri != m.from_uri]
    out = []
    for c in random.sample(changes, min(n // 2, len(changes))):
        out.append({'kind': 'change', 'state': c.state, 'verb': c.verb, 'text': text_path(c.text_uri), 'article': c.number,
                    'by': text_path(c.by_uri), 'by_article': c.by_article, 'issue': c.issue, 'bis': c.issue_bis,
                    'page': c.page, 'takes_effect': c.effective_on, 'check': ''})
    for m in random.sample(mentions, min(n - len(out), len(mentions))):
        out.append({'kind': 'citation', 'words': m.words, 'from': text_path(m.from_uri), 'eid': m.from_eid,
                    'to': text_path(m.to_uri), 'article': m.to_number, 'check': ''})
    return out


class Command(BaseCommand):
    help = "Measure the site's links against the SGG's notes and Adala's footnotes."

    def add_arguments(self, parser):
        parser.add_argument('--sample', type=int, default=0)

    def handle(self, *args, sample: int, **opts):
        report = {'at': date.today(), 'from': FROM, 'changes': changes_eval(), 'mentions': mentions_eval()}
        base = settings.CORPUS_DIR / 'reports'
        (base / 'link_eval.json').write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str))
        if sample:
            (base / 'link_sample.json').write_text(json.dumps(hand_sample(sample), ensure_ascii=False, indent=1,
                                                              default=str))
        c = report['changes']
        for source in ('sgg', 'adala'):
            self.stdout.write(f"{source}: {c[source]['found']} of {c[source]['notes']} notes found "
                              f"(recall {c[source]['recall']} %), {c[source]['states']}")
        self.stdout.write(f"precision of what is shown: {c['precision']['shown']}")
        for state, row in c['precision']['by_state'].items():
            self.stdout.write(f'  {state:>10}: {row}')
        m = report['mentions']
        self.stdout.write(f"citations: {m['states']}; linked {m['resolved']} ({m['resolved_in_corpus']} to a text the site "
                          f"holds); kind checked {m['kind_checked']}, wrong kind {m['wrong_kind']}")
