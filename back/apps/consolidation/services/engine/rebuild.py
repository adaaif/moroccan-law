"""3. apply: each changed text rebuilt in the order its changes take effect, into versions «consolidated by machine»
dated by that day: one amending text's changes all or none, never a conflict or an unclear one; a change put into an
article (its words, its paragraphs, a dotted wording filled)."""
from collections import defaultdict
from datetime import date

from apps.consolidation.models import Change, Doubt, Verb
from apps.consolidation.services import fill
from apps.consolidation.services.engine.shared import SHOWN, pick, variants
from apps.consolidation.services.engine.weighing import OFFICIAL_EDITIONS, later_texts
from apps.consolidation.services.instructions.labels import label_key
from apps.corpus.models import RANK, Article, Consolidation, Text, TextType, Version

REPEALED = '(نسخت)'


def _insert_after(rows: list[dict], key: str) -> int:
    """Where an added article goes: after the article it is numbered from («7-1», «5-bis» after 7, 5)."""
    root = key.split('-')[0]
    spots = [i for i, r in enumerate(rows) if r['key'].split('-')[0] == root]
    return spots[-1] + 1 if spots else len(rows)


def apply(rows: list[dict], change: Change) -> None:
    """One change put into the version's articles ({key, label, eid, body, heading_path, page}); raises Unplaced."""
    if change.verb == Verb.WORDS:
        pairs = [tuple(p) for p in change.detail.get('pairs', [])]
        scope = [r for r in rows if not change.number or r['key'] in variants(change.number)]
        total = 0
        for r in scope:
            r['body'], n = fill.words_replaced(r['body'], pairs)
            total += n
        if not total:
            raise fill.Unplaced('words_not_found')
        return
    if change.verb == Verb.REPEALED and not change.number:
        for r in rows:
            r['body'] = REPEALED
        return
    row = next((r for r in rows if r['key'] in variants(change.number)), None)
    if change.verb == Verb.REPEALED:
        if change.detail.get('part'):
            raise fill.Unplaced('part')
        if row is None:
            raise fill.Unplaced('article_missing')
        row['body'] = REPEALED
        return
    new_lines = change.wording
    if change.verb == Verb.ADDED and row is None:
        rows.insert(_insert_after(rows, change.number), {
            'key': change.number, 'label': change.detail.get('label') or change.number, 'eid': f'art_{change.number}',
            'body': '\n'.join(fill.paragraphs('\n'.join(new_lines))), 'heading_path': [], 'page': None})
        return
    if row is None:
        raise fill.Unplaced('article_missing')
    part = change.detail.get('part')
    # «(الباقي بدون تغيير.)» under a wording without dots keeps the rest as a line of dots would (37.25 art. 6).
    dotted = change.detail.get('dotted') or any(fill.REST.match(line.strip()) for line in new_lines)
    if part and part[0] in ('الفقرة', 'الفقرات'):
        # Only the paragraphs it names change, counted as the law counts them: a list belongs to the paragraph that
        # opens it. Filled against the whole article, «وفي حالة عدم الاتفاق على …» (27.22 on 65.00 art. 21, its third
        # paragraph) had dropped the two before it.
        blocks = _blocks(fill.paragraphs(row['body']))
        spots = sorted(n - 1 if n > 0 else len(blocks) + n for n in part[1] if n)
        if not spots or spots[0] < 0 or spots[-1] >= len(blocks) or spots != list(range(spots[0], spots[-1] + 1)):
            raise fill.Unplaced('part')
        old = '\n'.join(p for b in blocks[spots[0]:spots[-1] + 1] for p in b)
        body = fill.fill(new_lines, old)[0] if dotted else '\n'.join(fill.paragraphs('\n'.join(new_lines)))
        blocks[spots[0]:spots[-1] + 1] = [[body]]
        row['body'] = '\n'.join(p for b in blocks for p in b)
    elif dotted:
        body, dropped = fill.fill(new_lines, row['body'])
        if dropped and not part:
            change.detail['dropped'] = dropped
        row['body'] = body
    elif part:
        raise fill.Unplaced('part')
    else:
        row['body'] = '\n'.join(fill.paragraphs('\n'.join(new_lines)))
    row['page'] = None


def _blocks(paragraphs: list[str]) -> list[list[str]]:
    """Paragraphs as a law counts them: the items of a list («- …», «1)») stay with the paragraph that opens it («…:»)."""
    out: list[list[str]] = []
    for p in paragraphs:
        item = p.startswith('-') or fill.ENUM.match(p)
        if out and item and (len(out[-1]) > 1 or out[-1][0].rstrip().endswith(':')):
            out[-1].append(p)
        else:
            out.append([p])
    return out


def from_archive(uris: set) -> set:
    """The amending texts among `uris` read from the archive run's scans: their issue came from it (its document's
    `meta['archive']`, set by `archive import`)."""
    if not uris:
        return set()
    return set(Text.objects.filter(akn_uri__in=uris, first_published_in__document__meta__has_key='archive')
               .values_list('akn_uri', flat=True))


def _base(target: Text, on: date) -> Version | None:
    versions = [v for v in target.versions.all() if v.valid_from < on]
    if not versions:
        return None
    # On a day several start, the one corpus RANK puts first: an official consolidation before the machine's chain.
    return max(versions, key=lambda v: (v.valid_from, -RANK.get(v.consolidation, 9)))


def apply_to(target: Text, settled: set, worded: dict | None = None) -> tuple[list[Change], list[Doubt], dict]:
    """The text rebuilt from its as-published wording (or the SGG's or Adala's) through every change shown as
    fact, in the order they take effect; a version «consolidated by machine» for each day something changed.
    `worded`: the wording a person gave a change whose dots the machine could not place, by (amending text, article):
    the article whole, as it reads once changed (a resolved «unplaced» doubt's `detail['wording']`)."""
    worded = worded or {}
    stats = defaultdict(int)
    doubts: list[Doubt] = []
    target.versions.filter(consolidation=Consolidation.MACHINE).delete()
    target.versions.exclude(consolidation=Consolidation.MACHINE).update(valid_to=None)
    changes = list(Change.objects.filter(text_uri=target.akn_uri, source=Change.Source.READING))
    for c in changes:
        c.placed = None
        c.detail.pop('waiting', None)
        c.detail.pop('worded', None)
        if (c.by_uri, c.number) in worded:
            c.wording = worded[(c.by_uri, c.number)]
            c.detail['worded'] = True
    # An earlier constitution stays readable as it last stood: its repeal by the next one gives its status (standing),
    # never a version where every article reads «(نسخت)» (C10 of the constitution review).
    shown = [c for c in changes if c.state in SHOWN
             and not (target.type == TextType.CONSTITUTION and c.verb == Verb.REPEALED and not c.number)]
    # A text whose official consolidation the site holds keeps it (28 Oct 2026): an amendment read from the
    # archive's scans (the Bulletin 1956–2018, read by Haiku, unchecked) is shown as found and not applied until a
    # person checks it; the OCR of a first print never stands in for the SGG's, Adala's or the DGI's words.
    if target.versions.filter(consolidation__in=OFFICIAL_EDITIONS).exists():
        scanned = from_archive({c.by_uri for c in shown})
        for c in shown:
            if c.by_uri in scanned:
                c.detail['waiting'] = 'official'
        shown = [c for c in shown if c.by_uri not in scanned]
    for c in shown:
        if c.effective_on is None:
            c.detail['waiting'] = 'condition'
    order = defaultdict(list)
    for c in shown:
        if c.effective_on is not None:
            order[c.effective_on].append(c)
    later = later_texts(target)
    for on in sorted(order):
        base = _base(target, on)
        if base is None:
            for c in order[on]:
                c.detail['waiting'] = 'no_base'
            stats['waiting'] += len(order[on])
            continue
        rows = [{'key': label_key(a.label) or a.number, 'label': a.label, 'eid': a.eid, 'body': a.body,
                 'heading_path': a.heading_path, 'page': a.printed_page} for a in base.articles.all()]
        made = False
        by_text = defaultdict(list)
        for c in sorted(order[on], key=lambda c: (c.published_on or on, c.by_uri, c.by_article, c.id or 0)):
            by_text[c.by_uri].append(c)
        for _by, batch in by_text.items():
            trial = [dict(r) for r in rows]
            failed = []
            for c in batch:
                try:
                    apply(trial, c)
                except fill.Unplaced as e:
                    failed.append((c, str(e)))
            if failed:
                # The SGG's or Adala's consolidation standing at that day or later already holds the change: readers see
                # its wording, so a change the machine could not place on an older base is no doubt (the vehicles
                # decree's 21 «unplaced» of 2.24.393, which Adala's text to 24 August 2026 holds; R4 of the road plan).
                covered = any(as_of and on <= as_of for _, as_of, _ in later)
                for c, why in failed:
                    if (c.by_uri, c.number, Doubt.Reason.UNPLACED) in settled:
                        continue
                    if covered:
                        c.detail['covered'] = True
                        stats['covered'] += 1
                        continue
                    reason = {'words_not_found': Doubt.Reason.WORDS_NOT_FOUND,
                              'article_missing': Doubt.Reason.ARTICLE_MISSING}.get(why, Doubt.Reason.UNPLACED)
                    doubts.append(Doubt(text_uri=c.text_uri, number=c.number, by_uri=c.by_uri, by_article=c.by_article,
                                        reason=reason, detail={'why': why}))
                for c in batch:
                    c.placed = False
                stats['held_back'] += 1
                continue
            rows = trial
            made = True
            for c in batch:
                c.placed = True
                if c.detail.get('dropped') and not c.detail.get('worded'):
                    doubts.append(Doubt(text_uri=c.text_uri, number=c.number, by_uri=c.by_uri, by_article=c.by_article,
                                        reason=Doubt.Reason.DROPPED, detail={'dropped': c.detail['dropped']}))
        if not made:
            continue
        version = Version.objects.create(text=target, language='ar', valid_from=on,
                                         consolidation=Consolidation.MACHINE, source_pages='')
        if base.valid_to is None or base.valid_to > on:
            base.valid_to = on
            base.save(update_fields=['valid_to'])
        seen, articles = set(), []
        for n, r in enumerate(rows, 1):
            eid = r['eid'] if r['eid'] not in seen else f'{r["eid"]}_{n}'
            seen.add(eid)
            articles.append(Article(version=version, order=n, label=r['label'], number=r['key'], eid=eid,
                                    heading_path=r['heading_path'], body=r['body'], printed_page=r['page']))
        Article.objects.bulk_create(articles)
        # The words a person put right in the text are put right in this version too («ما صححناه»).
        from apps.quality.services.corrections import reapply
        reapply(list(version.articles.all()), target.akn_uri)
        stats['versions'] += 1
        for theirs, as_of, _source in later:
            if as_of and on <= as_of:
                for c in order[on]:
                    mine = next((r for r in rows if r['key'] in variants(c.number)), None)
                    art = pick(theirs, c.number) if c.number else None
                    if c.placed and mine and art:
                        c.detail['likeness'] = round(fill.likeness(mine['body'], art.body), 3)
                        if c.detail['likeness'] >= 0.9:
                            c.witnesses = {**c.witnesses, 'wording': True}
                            if c.state == Change.State.READ:
                                c.state = Change.State.CONFIRMED
    return changes, doubts, dict(stats)
