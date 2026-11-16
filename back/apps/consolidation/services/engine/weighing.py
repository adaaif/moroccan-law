"""2. weigh: each change read against its witnesses (the title's formula, the model's own list in texts.json, the
SGG's, Adala's and the DGI's notes, their later wording), and the state they allow: checked, confirmed, read,
conflict or unclear; the doubts a disagreement raises."""
import json
from collections import defaultdict
from datetime import date
from functools import lru_cache
from pathlib import Path

import ma_law
from django.conf import settings

from apps.consolidation.models import Change, Doubt, Verb
from apps.consolidation.services import fill
from apps.consolidation.services.engine.shared import by_key, pick, variants
from apps.consolidation.services.engine.targets import where
from apps.consolidation.services.instructions.labels import label_key
from apps.corpus.models import Article, Consolidation, Mention, Text
from apps.corpus.services import works


@lru_cache(maxsize=4000)
def _issue_texts(key: str) -> tuple:
    path = Path(settings.CORPUS_DIR) / 'reports' / 'issues' / key / 'texts.json'
    try:
        return tuple(json.loads(path.read_text()))
    except (OSError, ValueError):
        return ()


def model_list(text: Text) -> set[tuple[str, str]] | None:
    """What the model said this text changes, as (address, article number) — one more reader of the same words,
    kept in texts.json; None when it never described the text."""
    from apps.corpus.services.issue_structure import normalize_number
    issue = text.first_published_in
    if issue is None:
        return None
    published = issue.date
    mine = works.fold(text.number)
    for entry in _issue_texts(issue.key):
        data = entry.get('data') or {}
        printed = data.get('number_as_printed') or (entry.get('toc') or {}).get('number_as_printed') or ''
        if not mine or works.fold(normalize_number(printed)) != mine:
            continue
        out = set()
        for change in data.get('amends') or []:
            uri = ''
            for c in ma_law.parse_citations(change.get('target_text') or ''):
                if c['kind'] == 'issue':
                    continue
                u, state = where(c, published)
                if state == Mention.State.RESOLVED:
                    uri = u
                    break
            if uri:
                label = change.get('target_article') or ''
                number = label_key(label if not label[:1].isdigit() else f'المادة {label}') if label else ''
                out.add((uri, number))
        return out
    return None


def check(change: Change, articles: dict[str, Article]) -> None:
    """Does a later consolidated text bear this reading out?"""
    if not change.number:
        return
    art = pick(articles, change.number)
    if change.verb == Verb.REPEALED:
        ok = art is None or 'نسخ' in art.body[:80] or len(art.body) < 40
        change.verdict, change.score = (Change.Verdict.AGREES, 1.0) if ok else (Change.Verdict.DISAGREES, 0.0)
        return
    if art is None:
        change.verdict = Change.Verdict.ABSENT
        return
    if change.verb == Verb.WORDS:
        # Each pair counts where the article holds either wording (a list «على التوالي» spreads over articles).
        seen = [(old, new) for old, new in change.detail.get('pairs', []) if _has(art.body, new) or _has(art.body, old)]
        if not seen:
            change.verdict = Change.Verdict.ABSENT
            return
        change.score = sum(_has(art.body, new) for _, new in seen) / len(seen)
    else:
        change.score = fill.fragments_found(change.wording, art.body)
    change.verdict = (Change.Verdict.AGREES if change.score >= 0.8 else
                      Change.Verdict.PARTLY if change.score >= 0.4 else Change.Verdict.DISAGREES)


def _has(body: str, phrase: str) -> bool:
    return fill.stream(phrase) in fill.stream(body)


def later_texts(target: Text) -> list[tuple[dict, date | None, str]]:
    """The SGG's, Adala's and the DGI's consolidated texts of a text: (articles by number, as of, source)."""
    out = []
    for v in target.versions.filter(consolidation__in=OFFICIAL_EDITIONS).select_related(
            'source_document'):
        as_of = v.source_document.meta.get('as_of') if v.source_document_id else None
        out.append((by_key(v.articles.all()), date.fromisoformat(as_of) if as_of else None, v.consolidation))
    return out


LAW_RANK = {'law', 'organic_law', 'dahir', 'decree_law'}
# The consolidations whose notes and wording witness a change (the DGI's tax code since the tax review, T2).
OFFICIAL_EDITIONS = (Consolidation.SGG, Consolidation.ADALA, Consolidation.DGI)
WITNESSES = (Change.Source.SGG, Change.Source.ADALA, Change.Source.DGI)
BELOW_LAW = {'order', 'decision', 'circular'}


def weigh(changes: list[Change], settled: set, titles: dict) -> list[Doubt]:
    """Each reading's witnesses and the state they allow; the doubts a disagreement raises."""
    doubts = []
    notes = defaultdict(set)
    for uri, number, by, source in Change.objects.filter(
            source__in=WITNESSES,
            text_uri__in={c.text_uri for c in changes}).values_list('text_uri', 'number', 'by_number', 'source'):
        notes[(uri, works.fold(by), source)].add(number)
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in={c.by_uri for c in changes})
             .select_related('first_published_in')}
    lists = {}
    later: dict[str, list] = {}
    last = {}
    touched = defaultdict(list)       # when each article was changed, repeals too
    for c in changes:
        if c.published_on and c.state != Change.State.UNCLEAR and c.verb != Verb.REPEALED:
            key = (c.text_uri, c.number)
            last[key] = max(last.get(key, c.published_on), c.published_on)
        if c.published_on and c.state != Change.State.UNCLEAR and c.number:
            touched[(c.text_uri, c.number)].append(c.published_on)
    for c in changes:
        if c.state == Change.State.UNCLEAR:
            continue
        if works.kind_of(c.by_uri) in BELOW_LAW and works.kind_of(c.text_uri) in LAW_RANK:
            # An order or a decision never changes a law: what it names is a text taken under that law.
            c.witnesses, c.state = {'rank': False}, Change.State.UNCLEAR
            continue
        w = {}
        said = titles.get(c.by_uri, {}).get(c.text_uri)
        if said:
            # A title that says it amends a text is against reading the text repealed whole.
            w['title'] = not (c.verb == Verb.REPEALED and not c.number and 'repeals' not in said)
        if c.by_uri not in lists:
            lists[c.by_uri] = model_list(texts[c.by_uri]) if c.by_uri in texts else None
        listed = lists[c.by_uri]
        if listed is not None and any(u == c.text_uri and (n in variants(c.number) or (not n and not c.number))
                                      for u, n in listed):
            w['model'] = True
        for source in WITNESSES:
            numbers = notes.get((c.text_uri, works.fold(c.by_number), source), ())
            if any(n in variants(c.number) for n in numbers) or (not c.number and numbers):
                w[source] = True
        if c.text_uri not in later:
            target = Text.objects.filter(akn_uri=c.text_uri).first()
            later[c.text_uri] = later_texts(target) if target else []
        for articles, as_of, source in later[c.text_uri]:
            # The tax code is rewritten every year: its edition holds only an article's last change before it.
            if source == Consolidation.DGI and c.published_on and last.get((c.text_uri, c.number), c.published_on) > c.published_on:
                continue
            if as_of and c.published_on and c.published_on <= as_of and c.number:
                check(c, articles)
                if c.verdict in (Change.Verdict.DISAGREES, Change.Verdict.ABSENT):
                    # An edition holding a later change to the article cannot speak against this one (
                    # the health review, S3: Adala's 65.00 of 29 Jan 2026 holds 54.23's repeal of arts 122–124, which 27.22 had
                    # rewritten in 2022).
                    if any(c.published_on < on <= as_of for on in touched[(c.text_uri, c.number)]):
                        continue
                    w[source] = False
                    doubts.append(Doubt(text_uri=c.text_uri, number=c.number, by_uri=c.by_uri, by_article=c.by_article,
                                        reason=Doubt.Reason.SGG_DISAGREES, detail={'verdict': c.verdict, 'score': c.score,
                                                                                   'source': source}))
                elif c.verdict == Change.Verdict.AGREES:
                    w[source] = w.get(source, True)
        c.witnesses = w
        if (c.by_uri, c.number, Doubt.Reason.SGG_DISAGREES) in settled or (c.by_uri, c.number, Doubt.Reason.UNPLACED) in settled:
            c.state = Change.State.CHECKED
        elif False in w.values():
            c.state = Change.State.CONFLICT
        elif any(w.get(k) for k in ('model', *WITNESSES)):
            c.state = Change.State.CONFIRMED
        else:
            c.state = Change.State.READ
    return doubts
