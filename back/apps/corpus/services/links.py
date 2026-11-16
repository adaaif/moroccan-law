"""What the text page says of a text's links (rows L5–L7 and L13 of the links review): where it stands today, what
changed it and what it changes, what cites it and what applies it, where a repealed text leads, and how much of the BO
the site has read since it was published. Everything comes from rows kept by address (Change, Mention)."""
from collections import defaultdict
from datetime import date

from apps.consolidation.models import Change
from apps.consolidation.services.engine import SHOWN, standing
from apps.corpus.models import Article, Mention, Text
from apps.corpus.services import works
from apps.corpus.services.addresses import text_path
from apps.sources.services import coverage

CITED_BY_MAX = 40
# A text from 1964 has some 2,800 issues printed after it that the site has not read: their count is the sentence, the first
# of them an example (29 Oct 2026: the list was 111 KB of a 1964 decree's 110 KB answer).
MISSING_SHOWN = 40
# More than this many unread issues after a text and «in force» is not said of it: «no repeal found» is (UX3). Since 2019
# two or three issues are unread (no file at the SGG); before, thousands.
PARTIAL_AFTER = 10


def brief(uri: str, held: dict[str, Text]) -> dict:
    """A text named by its address: its page when the site holds it, else what the address says (kind and number)."""
    t = held.get(uri)
    if t is not None:
        return {'path': text_path(uri), 'title': t.title_ar, 'type': t.type, 'number': t.number_as_printed,
                'status': t.status, 'in_corpus': bool(getattr(t, 'n_versions', 1))}
    number = uri.rsplit('/', 1)[-1]
    return {'path': None, 'title': '', 'type': works.kind_of(uri), 'number': number.replace('-', '.'),
            'status': 'unknown', 'in_corpus': False}


def _held(uris) -> dict[str, Text]:
    from django.db.models import Count
    return {t.akn_uri: t for t in Text.objects.filter(akn_uri__in=set(uris)).annotate(n_versions=Count('versions'))}


def _stamp(c: Change) -> dict:
    return {'number': c.issue, 'bis': c.issue_bis, 'page': c.page,
            'key': (f'{c.issue}-bis' if c.issue_bis else str(c.issue)) if c.issue else None}


def text_links(text: Text) -> dict:
    """The text's standing line and its link lists."""
    me = text.akn_uri
    received = list(Change.objects.filter(text_uri=me, source=Change.Source.READING).order_by('effective_on', 'published_on'))
    # A bill's proposals are what it changes (never applied: their state says «proposed»).
    made = list(Change.objects.filter(by_uri=me, source=Change.Source.BILL if text.type == 'bill' else Change.Source.READING)
                .order_by('text_uri', 'id'))
    mentions_to = list(Mention.objects.filter(to_uri=me).exclude(from_uri=me))
    mentions_from = list(Mention.objects.filter(from_uri=me).exclude(to_uri=me).exclude(to_uri=''))
    held = _held([c.by_uri for c in received] + [c.text_uri for c in made] + [m.from_uri for m in mentions_to]
                 + [m.to_uri for m in mentions_from])

    stand = standing(text)
    for key in ('repealed', 'repeal_pending'):
        if key in stand:
            stand[key] = {**stand[key], 'by': brief(stand[key]['by_uri'], held)}
    published = text.first_published_in.date if text.first_published_in_id else text.signed_on

    # Each text that changed this one: once, with its articles, the day it takes effect and its best state.
    amended_by: dict[str, dict] = {}
    for c in received:
        row = amended_by.setdefault(c.by_uri, {'by': brief(c.by_uri, held), 'issue': _stamp(c), 'published_on': c.published_on,
                                               'effective_on': c.effective_on, 'rule': c.effective_rule,
                                               'when': c.effective_words[:300], 'articles': [], 'verbs': [],
                                               'whole': False, 'states': []})
        if c.number and c.number not in row['articles']:
            row['articles'].append(c.number)
        row['whole'] = row['whole'] or not c.number
        if c.verb not in row['verbs']:
            row['verbs'].append(c.verb)
        row['states'].append(c.state)
    for row in amended_by.values():
        # Its best state among the changes shown as fact; how many it holds back (a conflict, a change not read).
        states = row.pop('states')
        row['state'] = next((s for s in SHOWN if s in states), None) or \
            next((s for s in ('conflict', 'unclear') if s in states), 'unclear')
        row['held_back'] = sum(1 for s in states if s not in SHOWN)
    # Amended: changes shown as fact, a repeal of the whole text aside (the standing says it).
    shown = [r for r in amended_by.values() if r['state'] in SHOWN and not (r['whole'] and r['verbs'] == ['repealed'])]
    last = max(shown, key=lambda r: (r['effective_on'] or r['published_on']), default=None)

    amends: dict[str, dict] = {}
    for c in made:
        row = amends.setdefault(c.text_uri, {'target': brief(c.text_uri, held), 'changes': []})
        row['changes'].append({'number': c.number, 'verb': c.verb, 'state': c.state, 'effective_on': c.effective_on,
                               'rule': c.effective_rule, 'placed': c.placed, 'waiting': (c.detail or {}).get('waiting')})

    cites: dict[str, dict] = {}
    for m in mentions_from:
        if m.kind != Mention.Kind.CITES:
            continue
        row = cites.setdefault(m.to_uri, {'to': brief(m.to_uri, held), 'count': 0})
        row['count'] += 1
    by_kind = defaultdict(dict)
    for m in mentions_to:
        row = by_kind[m.kind].setdefault(m.from_uri, {'from': brief(m.from_uri, held), 'articles': [], 'count': 0,
                                                      'words': m.words[:300]})
        row['count'] += 1
        number = m.to_number if m.kind == Mention.Kind.APPLIES else m.from_eid
        if number and number not in row['articles']:
            row['articles'].append(number)
    held_versions = list(text.versions.values_list('consolidation', 'valid_from'))     # one query, as before
    return {
        'standing': {**stand, 'changes': len(shown), 'last': last, 'coverage': _coverage(held_versions, published),
                     'sure': _sure(held_versions, published)},
        'amended_by': list(amended_by.values()),
        'amends': list(amends.values()),
        'cites': sorted(cites.values(), key=lambda r: -r['count']),
        'cited_by': sorted(by_kind[Mention.Kind.CITES].values(), key=lambda r: -r['count'])[:CITED_BY_MAX],
        'cited_by_count': len(by_kind[Mention.Kind.CITES]),
        'applied_by': list(by_kind[Mention.Kind.APPLIES].values()),
        'redirected_by': list(by_kind[Mention.Kind.REDIRECTS].values()),
        'kept_by': list(by_kind[Mention.Kind.KEEPS].values()),
        'corrected_by': list(by_kind[Mention.Kind.CORRECTS].values()),
        'ruled_on_by': list(by_kind[Mention.Kind.RULES_ON].values()),
    }


def article_links(text: Text, articles: list[Article]) -> dict[str, dict]:
    """Per article number: the texts that cite it and those that apply it."""
    numbers = {a.number for a in articles if a.number}
    rows = Mention.objects.filter(to_uri=text.akn_uri, to_number__in=numbers,
                                  kind__in=(Mention.Kind.CITES, Mention.Kind.APPLIES)).exclude(from_uri=text.akn_uri)
    rows = list(rows)
    held = _held(m.from_uri for m in rows)
    out: dict[str, dict] = defaultdict(lambda: {'cited_by': [], 'applied_by': []})
    for m in rows:
        key = 'applied_by' if m.kind == Mention.Kind.APPLIES else 'cited_by'
        bucket = out[m.to_number][key]
        if not any(r['from']['path'] == text_path(m.from_uri) and r['eid'] == m.from_eid for r in bucket):
            bucket.append({'from': brief(m.from_uri, held), 'eid': m.from_eid})
    return out


# «In force» is a claim about today (RD6 of the readers review, 9 Nov 2026). It is made of a text an official portal
# publishes as today's law, and of a text as printed since the issues were read as they came, their links measured;
# of an older text as printed the most the site can say is that it found no repeal. It was said of every text with fewer
# than eleven unread issues after it: of every text since about 2012 on the server, and, on a copy where the old issues
# count as read, of a 1941 dahir on suspended newspapers.
OFFICIAL = ('adala', 'sgg', 'dgi')
SURE_SINCE = coverage.FROM


def _sure(held: list[tuple], published) -> bool:
    """Whether «in force» may be said of a text no repeal was found for."""
    if any(kind in OFFICIAL for kind, _ in held):
        return True
    return published is not None and published >= SURE_SINCE


def _coverage(held: list[tuple], published) -> dict | None:
    """What the site has read since the text as held: since its publication for a text held as published; for one held only
    as a consolidation, since that consolidation's day, to which it is complete (HM26 of the hard-moment review:
    the Labour Code, the tax code and the 2011 Constitution were all «published before 1913»). None when no day is known.
    `held`: its versions' (kind, day), read once by the caller."""
    if any(kind == 'as_published' for kind, _ in held):
        day = published
    else:
        started = [d for _, d in held if d and d <= date.today()]
        day = max(started) if started else published
    return shown_coverage(coverage.since(day)) if day is not None else None


def shown_coverage(c: dict) -> dict:
    """What a text's page says of what the site has read since it: how many issues it has not read, and the first of them."""
    n = len(c['missing'])
    return {**c, 'missing': c['missing'][:MISSING_SHOWN], 'missing_count': n, 'partial': n > PARTIAL_AFTER}
