"""What the text page says about versions (row 8): which version stood on a date, each article's changes with
the law and BO issue that made them, and what changed word by word between two versions."""
from datetime import date
from difflib import SequenceMatcher

import ma_law

from apps.consolidation.models import Change
from apps.consolidation.services.instructions.labels import label_key
from apps.corpus.models import RANK, Text, Version
from apps.corpus.services import works
from apps.corpus.services.addresses import text_path
from apps.sources.models import Edition, Issue




def pick_version(text: Text, on: date | None) -> tuple[Version | None, Version | None]:
    """The version in force on `on` (today when none is asked: a version dated later is not yet in force) and the
    one before it."""
    return pick(text.versions.select_related('source_document'), on)


def pick(versions, on: date | None) -> tuple[Version | None, Version | None]:
    """`pick_version` over versions already in hand (prefetched for many texts at once)."""
    versions = sorted(versions, key=lambda v: (v.valid_from, -RANK.get(v.consolidation, 9), v.id))
    if not versions:
        return None, None
    day = on or date.today()
    earlier = [i for i, v in enumerate(versions) if v.valid_from <= day]
    chosen = earlier[-1] if earlier else 0
    return versions[chosen], versions[chosen - 1] if chosen else None


def versions_list(text: Text, current: Version | None) -> list[dict]:
    out = []
    for v in sorted(text.versions.select_related('source_document'),
                    key=lambda v: (v.valid_from, -RANK.get(v.consolidation, 9), v.id)):
        meta = v.source_document.meta if v.source_document_id else {}
        out.append({'valid_from': v.valid_from, 'valid_to': v.valid_to, 'consolidation': v.consolidation,
                    'current': current is not None and v.pk == current.pk, 'as_of': meta.get('as_of')})
    return out


def article_changes(text: Text) -> dict[str, list[dict]]:
    """Each article's changes, oldest first: our readings of the amending texts (with their state, the day they take
    effect and whether they are placed), and the SGG's and Adala's notes; one entry for a change several record (same
    amending text, same issue). Key «» is the whole text."""
    return changes_of([text.akn_uri])[text.akn_uri]


def changes_of(uris) -> dict[str, dict[str, list[dict]]]:
    """`article_changes` for many texts by address, in three queries for all of them."""
    uris = list(dict.fromkeys(uris))
    # A bill's proposals are never an article's history: they are `proposals_of`'s.
    rows = list(Change.objects.filter(text_uri__in=uris).exclude(source__in=(Change.Source.MODEL, Change.Source.BILL))
                .order_by('published_on', 'issue', 'id')) if uris else []
    issues = {(i.number, i.suffix): i for i in Issue.objects.filter(edition=Edition.GENERAL_AR,
                                                                    number__in={r.issue for r in rows if r.issue})}
    paths = dict(Text.objects.filter(akn_uri__in={r.by_uri for r in rows if r.by_uri}).values_list('akn_uri', 'title_ar'))
    by_text: dict[str, list[Change]] = {uri: [] for uri in uris}
    for r in rows:
        by_text[r.text_uri].append(r)
    return {uri: _table(found, issues, paths) for uri, found in by_text.items()}


def _table(rows: list[Change], issues: dict, paths: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        entries = out.setdefault(r.number, [])
        by_number = works.fold(r.by_number)
        same = next((e for e in entries if works.fold(e['by']['number']) == by_number and e['issue']['number'] == r.issue),
                    None)
        if same:
            same['sources'].append(r.source)
            if r.source == Change.Source.READING:
                same.update(_reading(r))
            continue
        issue = issues.get((r.issue, 'bis' if r.issue_bis else ''))
        entries.append({
            'on': r.published_on, 'verb': r.verb, 'sources': [r.source], 'verdict': r.verdict, 'score': r.score,
            'placed': r.placed, 'by_article': r.by_article, 'state': '', 'effective_on': None, 'rule': '',
            'when': '', 'waiting': None,
            'by': {'kind': r.by_kind, 'number': r.by_number, 'path': text_path(r.by_uri) if r.by_uri in paths else None,
                   'title': paths.get(r.by_uri, '')},
            'issue': {'number': r.issue, 'bis': r.issue_bis, 'page': r.page,
                      'path': f'/bo/{issue.edition}/{issue.key}' if issue else None},
            **(_reading(r) if r.source == Change.Source.READING else {}),
        })
    return out


def _reading(r: Change) -> dict:
    return {'verb': r.verb, 'verdict': r.verdict, 'score': r.score, 'placed': r.placed, 'state': r.state,
            'effective_on': r.effective_on, 'rule': r.effective_rule, 'when': r.effective_words[:300],
            'waiting': (r.detail or {}).get('waiting'), 'by_article': r.by_article}


OFFICIAL = ('sgg', 'adala', 'dgi')
SHOWN_AS_FACT = ('checked', 'confirmed', 'read')


def settled(table: dict[str, list[dict]], version, today: date | None = None) -> dict[str, list[dict]]:
    """An article's changes read against the copy shown (RD2 of the readers review, 9 Nov 2026), two ways:

    - A change the Bulletin's scans gave is marked «found and not applied» whenever the text has an official copy. When
      that copy is later than the change it already holds it: the line stood under 1,187 articles of 51 texts (the
      family code's article 16, under words the 2016 law wrote). It goes.
    - A change shown as fact whose words are not in the copy (its amending law's batch held back, or a law newer than
      the official copy) is `missing`: organic law 27.11's article 3 was marked «عُدّلت» over its 2021 words, with
      nothing to say the 2026 wording was not there. A text as printed never misses one: it says «كما نُشر».
    The table itself is not touched."""
    if version is None or version.consolidation in ('as_published', 'bill', 'translation'):
        return table
    today = today or date.today()
    as_of = version.valid_from
    if version.consolidation in OFFICIAL and version.source_document_id:
        try:
            as_of = date.fromisoformat(str(version.source_document.meta.get('as_of') or '')[:10])
        except ValueError:
            pass
    out = {}
    for key, entries in table.items():
        out[key] = []
        for e in entries:
            e = dict(e)
            held = version.consolidation in OFFICIAL and bool(e['on'] and as_of and e['on'] <= as_of)
            if held and e.get('waiting') == 'official':
                e['waiting'] = None
            in_force = e.get('effective_on') is None or e['effective_on'] <= today
            e['missing'] = bool(e.get('state') in SHOWN_AS_FACT and not e.get('placed') and not held and in_force
                                and e.get('rule') != 'condition')
            out[key].append(e)
    return out


def changes_for(table: dict[str, list[dict]], label: str, number: str) -> list[dict]:
    key = label_key(label) or number
    found = table.get(key, [])
    parts = key.split('-')
    if not found and len(parts) == 2 and all(p.isdigit() for p in parts):
        found = table.get(f'{parts[1]}-{parts[0]}', [])
    return found


_SEATS = str.maketrans('أإآؤئء', 'اااااا')


def same_words(old: str, new: str) -> bool:
    """Whether two wordings are one law: the same words once folded (the BO's spacing and punctuation, «.1» or «1 -»,
    Indic or Western digits, a vowel mark, «ى» or «ي»), a hamza on any seat or none (HM38 of
    the hard-moment review: 119 of the road code's 218 diffs were these). Compared, never shown: the words stay as printed."""
    words = lambda s: ma_law.tokens(ma_law.fold(s.translate(_SEATS)))
    return words(old) == words(new)


def word_diff(old: str, new: str) -> list[list[str]]:
    """[[op, words]] with op «=», «-» (gone) or «+» (new), line breaks kept as «\\n» words."""
    a = old.replace('\n', ' \n ').split(' ')
    b = new.replace('\n', ' \n ').split(' ')
    out: list[list[str]] = []

    def push(op: str, words: list[str]) -> None:
        text = ' '.join(w for w in words if w).replace(' \n ', '\n')
        if text:
            out.append([op, text])

    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == 'equal':
            push('=', a[i1:i2])
        else:
            push('-', a[i1:i2])
            push('+', b[j1:j2])
    return out


def proposals_of(text: Text) -> dict[str, dict]:
    """Per article number, what bills filed in Parliament propose for it (P2): the bill, its article, its verb and the
    day it would apply. The article's page asks `proposed` for the words."""
    return proposals_many([text.akn_uri])[text.akn_uri]


def proposals_many(uris) -> dict[str, dict[str, dict]]:
    """`proposals_of` for many texts by address, in two queries for all of them (a reader's follows, P16)."""
    uris = list(dict.fromkeys(uris))
    rows = list(Change.objects.filter(text_uri__in=uris, source=Change.Source.BILL).order_by('effective_on', 'id')) \
        if uris else []
    bills = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in={c.by_uri for c in rows})} if rows else {}
    out: dict[str, dict[str, dict]] = {uri: {} for uri in uris}
    for c in rows:
        bill = bills.get(c.by_uri)
        out[c.text_uri].setdefault(c.number, {
            'bill': text_path(c.by_uri), 'name': bill_name(bill) if bill else None, 'article': c.by_article,
            'verb': c.verb, 'effective_on': c.effective_on, 'partial': bool((c.detail or {}).get('partial')),
            'filed_on': c.published_on})
    return out


def bill_name(t: Text) -> dict:
    """A finance bill as people say it: «مشروع قانون المالية 2027», «projet de loi de finances 2027»; another bill by
    its title."""
    import re
    ar = re.sub(r'^(مشروع قانون المالية) رقم [\d.]+ للسنة المالية (\d{4})$', r'\1 \2', t.title_ar)
    fr = re.sub(r'^Projet de loi de finances n° [\d-]+ pour l’année budgétaire (\d{4})$', r'projet de loi de finances \1',
                t.title_fr or '')
    return {'ar': ar, 'fr': fr or ar}


def proposed(text: Text, number: str) -> list[dict]:
    """What a bill filed in Parliament would make of one article (the finance-bill review, P2): for each of the
    bill's proposals for it, the article today and as the bill would write it (the links pipeline's own `apply` on a
    copy, never saved), word by word, with the bill, its article, its stage and the day it would apply. A proposal the
    code cannot place says so («unplaced»), never a guess."""
    from apps.consolidation.services import fill
    from apps.consolidation.services.engine.rebuild import apply
    from apps.consolidation.services.engine.shared import variants
    rows = [c for c in Change.objects.filter(text_uri=text.akn_uri, source=Change.Source.BILL).order_by('effective_on', 'id')
            if c.number in variants(number) or (not c.number and not number)]
    if not rows:
        return []
    version = text.latest_version()
    current = next((a for a in version.articles.all() if (label_key(a.label) or a.number) in variants(number)), None) \
        if version else None
    bills = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in={c.by_uri for c in rows}).prefetch_related('versions')}
    out = []
    for c in rows:
        before = current.body if current else ''
        copy = [{'key': number, 'label': current.label if current else number, 'eid': current.eid if current else '',
                 'body': before, 'heading_path': [], 'page': None}] if current else []
        after, unplaced = None, ''
        try:
            apply(copy, c)
            after = next((r['body'] for r in copy if r['key'] in variants(number)), None)
        except fill.Unplaced as e:
            unplaced = str(e) or 'unplaced'
        bill = bills.get(c.by_uri)
        stage = bill.versions.filter(consolidation='bill').order_by('-valid_from').first() if bill else None
        out.append({
            'bill': {'path': text_path(c.by_uri), 'title': bill.title_ar if bill else '',
                     'name': bill_name(bill) if bill else None, 'article': c.by_article,
                     'stage': (stage.source_document.meta.get('stage') if stage and stage.source_document_id else None),
                     'since': stage.valid_from if stage else None},
            'verb': c.verb, 'effective_on': c.effective_on, 'when': c.effective_words[:400],
            # The date names only some of its provisions (the bill's own sentence is shown).
            'partial': bool((c.detail or {}).get('partial')),
            # The bill's own words for the article («……» where it keeps today's): shown when the code cannot place them,
            # or when the article is new.
            'wording': c.wording, 'new': current is None,
            'before': before, 'after': after, 'unplaced': unplaced,
            'diff': word_diff(before, after) if after is not None else None})
    return out
