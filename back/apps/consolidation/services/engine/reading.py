"""1. read: every article of a text as published, the changes it makes to other texts (Change, «reading»), what it
says of them without changing them (Mention: citations, «بتطبيق», redirected references, kept decrees, corrections,
court rulings), its visas, the whole texts a law held only as a portal's copy repeals, and a change refused when the
text it names was signed more than a year after it was printed."""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

import ma_law

from apps.consolidation.models import Change, Doubt, Verb
from apps.consolidation.services.engine.targets import cited_title, target_of, where
from apps.consolidation.services.engine.when import _PORTALS, as_published, own_rule, own_start, takes_effect
from apps.consolidation.services.instructions.amending import Instructions, read
from apps.consolidation.services.instructions.dates import lead_date
from apps.consolidation.services.instructions.labels import plain
from apps.consolidation.services.instructions.provisions import clauses, title_links
from apps.corpus.models import Article, Mention, Text, Version
from apps.corpus.services import works
from apps.corpus.services.codes import dated

VERBS = {'modify': Verb.MODIFIED, 'replace': Verb.REPLACED, 'add': Verb.ADDED, 'repeal': Verb.REPEALED,
         'words': Verb.WORDS}


@dataclass
class Read:
    changes: list[Change] = field(default_factory=list)
    mentions: list[Mention] = field(default_factory=list)
    doubts: list[Doubt] = field(default_factory=list)
    titled: dict = field(default_factory=dict)     # a text's address → {address its title names: {amends, repeals}}
    names: dict = field(default_factory=dict)      # address → the words it is cited by (for a text not read yet)
    model: dict = field(default_factory=dict)      # (amending text, article label) → what a model read there (L12)
    stats: dict = field(default_factory=lambda: defaultdict(int))


def _change(by: Text, article: Article, target: str, number: str, verb: str, on, rule, words, **extra) -> Change:
    issue = by.first_published_in
    return Change(text_uri=target, number=number, verb=verb, source=Change.Source.READING, by_kind=by.type,
                  by_number=works.fold(by.number), by_uri=by.akn_uri, by_article=article.label if article else '',
                  issue=issue.number if issue else None, issue_bis=bool(issue and issue.suffix),
                  page=article.printed_page if article else by.first_published_page,
                  published_on=issue.date if issue else by.signed_on, effective_on=on, effective_rule=rule,
                  effective_words=words[:600], **extra)


# The kinds whose first visa names their legal basis: «بناء على القانون رقم 65.99 … ولا سيما المادة 43 منه» is the
# decree that applies art. 43 (T1 of the work plan: the notice decree, the wage decrees).
BASIS_KINDS = {'decree', 'order', 'decision'}


def read_visas(text: Text, version: Version, out: 'Read', applied: set, published) -> None:
    """The visas: what the text is taken on, and the articles of the text it applies — those its title says it
    applies («ولا سيما المادة 5 منه»), and for a regulatory text, those its first visa past the Constitution
    pinpoints («ولا سيما المادة 43 منه», «… بتطبيق المادة 356 من القانون رقم 65.99»)."""
    me = text.akn_uri
    basis_read = text.type not in BASIS_KINDS
    for line in version.preamble.splitlines():
        cited = [c for c in ma_law.parse_citations(line) if c['kind'] != 'issue']
        for c in cited:
            uri, state = where(c, published, line[c['end']:])
            if state == Mention.State.SELF:
                continue
            out.mentions.append(Mention(from_uri=me, from_eid='preamble', start=c['start'], end=c['end'],
                                        words=c['raw'], kind=Mention.Kind.CITES, to_uri=uri,
                                        to_number=c.get('article') or '', state=state))
            if uri in applied and 'سيما' in line:
                for n in ma_law.parse_citations(line[line.find('سيما'):]):
                    if n['kind'] == 'article' and not (n.get('text_number') or n.get('code')) and n.get('article'):
                        out.mentions.append(Mention(from_uri=me, from_eid='preamble', start=c['start'], end=c['end'],
                                                    words=line[:300], kind=Mention.Kind.APPLIES, to_uri=uri,
                                                    to_number=n['article'], state=state))
        texts = [c for c in cited if c['kind'] == 'text' or c.get('text_number') or c.get('code')]
        if basis_read or not texts or not re.match(r'^\s*(?:بناء\s+على|وعلى)', line) \
                or texts[0].get('code') == 'constitution':
            continue
        basis_read = True
        basis, state = where(texts[0], published)
        if basis in applied:
            continue                    # its title already made the links («بتطبيق»)
        made = set()
        if 'سيما' in line and state == Mention.State.RESOLVED:
            for n in ma_law.parse_citations(line[line.find('سيما'):]):
                if n['kind'] == 'article' and not (n.get('text_number') or n.get('code')) and n.get('article'):
                    made.add((basis, n['article']))
        for m in re.finditer(r'بتطبيق\s+', line):
            n = next(iter(ma_law.parse_citations(line[m.end():m.end() + 160])), None)
            if n and n['kind'] == 'article' and n.get('article') and (n.get('text_number') or n.get('code')):
                uri, st = where(n, published)
                if st == Mention.State.RESOLVED:
                    made.add((uri, n['article']))
        for uri, number in sorted(made):
            out.mentions.append(Mention(from_uri=me, from_eid='preamble', start=0, end=0, words=line[:300],
                                        kind=Mention.Kind.APPLIES, to_uri=uri, to_number=number,
                                        state=Mention.State.RESOLVED))


def read_copy_repeals(text: Text, out: Read) -> None:
    """The texts a law repeals whole, said in its final provisions, for a law the site holds only as an official portal's
    copy: the family code's art. 397 repeals the personal status code of 1957, which read «لم نجد ما ينسخه», and water
    law 36.15's art. 163 repeals law 10.95 (RD3 of the readers review: 21 such repeals in the 145 texts so held
    on 10 Nov 2026). Whole texts only, from the day the law itself starts: what it changes inside other texts still
    comes from the Bulletin alone, since a copy holds other laws' words too."""
    copy = text.versions.filter(language='ar', consolidation__in=_PORTALS).order_by('-valid_from').first()
    if copy is None:
        return
    articles = list(copy.articles.all())
    issue = text.first_published_in
    published = issue.date if issue else text.signed_on
    default = takes_effect(own_rule(articles[-30:]), published)
    for a in articles:
        for clause in clauses(a.body):
            if clause.kind != 'repeal':
                continue
            for c in clause.citations:
                if c['kind'] == 'article' and c.get('article'):
                    continue
                uri, state = where(c, published)
                if state != Mention.State.RESOLVED or uri == text.akn_uri:
                    continue
                on, rule, words = (clause.on, Change.Rule.STATED, clause.words) if clause.on else \
                    (default[0], default[1], default[2] or clause.words)
                out.changes.append(_change(text, a, uri, '', Verb.REPEALED, on, rule, words,
                                           detail={'clause': clause.words[:300], 'whole': True, 'copy': copy.consolidation}))
                out.names.setdefault(uri, cited_title(plain(a.body), c))
                out.stats['copy_repeals'] += 1


def read_text(text: Text, out: Read) -> None:
    """One text's changes to others and what it says of them, as printed."""
    version = as_published(text)
    if version is None:
        # A text the site holds only as Adala's or the SGG's: its visas, not its changes (those come from the BO).
        latest = text.versions.filter(language='ar').exclude(preamble='').order_by('-valid_from').first()
        if latest is not None:
            read_visas(text, latest, out, set(), text.signed_on)
        read_copy_repeals(text, out)
        return
    articles = list(version.articles.all())
    issue = text.first_published_in
    published = issue.date if issue else text.signed_on
    default = own_start(text, version, published)
    me = text.akn_uri

    # The title's formula: what the text says it does, and which texts it applies, corrects or rules on.
    titled: dict[str, set] = defaultdict(set)
    for relation, c in title_links(text.title_ar, text.number):
        uri, state = where(c, published)
        if relation in ('amends', 'repeals'):
            titled[uri].add(relation)
            continue
        kind = {'applies': Mention.Kind.APPLIES, 'corrects': Mention.Kind.CORRECTS,
                'rules_on': Mention.Kind.RULES_ON}[relation]
        out.mentions.append(Mention(from_uri=me, from_eid='', start=c['start'], end=c['end'], words=c['raw'],
                                    kind=kind, to_uri=uri, to_number=c.get('article') or '', state=state))
        if relation == 'corrects':
            out.doubts.append(Doubt(text_uri=uri, by_uri=me, reason=Doubt.Reason.CORRECTION,
                                    detail={'title': text.title_ar[:300]}))
        if relation == 'rules_on' and any('غير مطابق' in a.body for a in articles):
            out.doubts.append(Doubt(text_uri=uri, by_uri=me, reason=Doubt.Reason.COURT,
                                    detail={'title': text.title_ar[:300]}))
    out.titled[me] = titled
    applied = {m.to_uri for m in out.mentions if m.from_uri == me and m.kind == Mention.Kind.APPLIES}
    read_visas(text, version, out, applied, published)

    for a in articles:
        if a.number == 'annex' or a.eid == 'annex':
            continue        # the tail after the last article: where another item of the issue can spill when cut
        ins = read(a.body)
        target, _target_kind, _target_number = target_of(ins, published) if ins else ('', '', '')
        if ins is not None and not target and len(titled) == 1:
            target = next(iter(titled))          # «يتمم القانون السالف الذكر …»: the text the title names
        by_model = out.model.get((me, a.label)) if ins is not None and (ins.action == 'unclear' or not target) else None
        if by_model:
            # The code could not read it; a model did, every quoted line found in the article (read_unclear).
            out.stats['read_by_model'] += 1
            for m in by_model:
                out.changes.append(Change(**{f.attname: getattr(m, f.attname) for f in Change._meta.concrete_fields
                                             if f.attname not in ('id', 'source', 'state')},
                                          source=Change.Source.READING, state=''))
            ins = None
        if ins is not None:
            out.stats['articles_read'] += 1
            when = lead_date(a.body)
            on, rule, words = (when, Change.Rule.STATED, '') if when else default
            if ins.action == 'unclear':
                out.stats['unclear'] += 1
                out.doubts.append(Doubt(text_uri=target, by_uri=me, by_article=a.label, reason=Doubt.Reason.UNCLEAR,
                                        detail={'why': ins.reason}))
                if target:
                    for named in ins.articles or [{'number': ''}]:
                        out.changes.append(_change(text, a, target, named['number'], Verb.MODIFIED, on, rule, words,
                                                   state=Change.State.UNCLEAR, detail={'why': ins.reason}))
            elif not target:
                out.stats['target_unknown'] += 1
                out.doubts.append(Doubt(by_uri=me, by_article=a.label, reason=Doubt.Reason.TARGET_UNKNOWN,
                                        detail={'target': ins.target}))
            else:
                out.changes.extend(_record(text, a, ins, target, on, rule, words))
            if target and ins.target and ins.target.get('number'):
                for c in ma_law.parse_citations(a.body[:600]):
                    if c.get('text_number') and works.fold(c['text_number']) == works.fold(ins.target['number']):
                        out.names.setdefault(target, cited_title(a.body, c))
                        break
        # Repeals of whole texts and articles said in the final provisions; redirects; kept decrees.
        for clause in clauses(a.body, instructed=ins is not None):
            for c in clause.citations:
                uri, state = where(c, published)
                if state != Mention.State.RESOLVED or uri == me:
                    continue
                if clause.kind == 'repeal':
                    on, rule, words = (clause.on, Change.Rule.STATED, clause.words) if clause.on else \
                        (default[0], default[1], default[2] or clause.words)
                    number = c.get('article') or '' if c['kind'] == 'article' else ''
                    out.changes.append(_change(text, a, uri, number, Verb.REPEALED, on, rule, words,
                                               detail={'clause': clause.words[:300], 'whole': not number}))
                    out.names.setdefault(uri, cited_title(plain(a.body), c))
                else:
                    kind = Mention.Kind.REDIRECTS if clause.kind == 'redirect' else Mention.Kind.KEEPS
                    out.mentions.append(Mention(from_uri=me, from_eid=a.eid, start=c['start'], end=c['end'],
                                                words=clause.words[:600], kind=kind, to_uri=uri, state=state))
        # Every citation in the article, kept with its words and place. In an amending article a bare «المادة 7»
        # is the amended text's.
        for c in (dated(a.body, c) for c in ma_law.parse_citations(a.body)):
            if c['kind'] == 'issue':
                continue
            uri, state = where(c, published, a.body[c['end']:c['end'] + 200])
            if state == Mention.State.SELF:
                if target and ins is not None:
                    uri, state = target, Mention.State.RESOLVED
                else:
                    uri = me
            out.mentions.append(Mention(from_uri=me, from_eid=a.eid, start=c['start'], end=c['end'], words=c['raw'],
                                        kind=Mention.Kind.CITES, to_uri=uri, to_number=c.get('article') or '',
                                        state=state))


# How long before a text was signed a change to it must be printed to be refused: under it, a date read wrong on
# either side is likelier than a wrong text (an order of 24 Oct 1979 changed by one of 1 Aug 1979).
LATER = timedelta(days=365)


def refuse_later(out: Read) -> None:
    """A text cannot change one signed more than a year after it was printed: the change names another text, and is kept
    as a doubt for a person instead (RD3 of the readers review: the civil procedure code of 2026 read «عُدّل بعد
    صدوره» by law 1.13 of 2014, which amends «قانون المسطرة المدنية», the name the 2026 code now answers to; orders
    «82.22» of 2022 changed by decisions of 1982). 38 changes on 16 texts of the development database on 10 Nov 2026. A
    target dated in the future is a date read wrong, and refuses nothing."""
    born = {}
    for uri, signed, issued in Text.objects.filter(akn_uri__in={c.text_uri for c in out.changes}).values_list(
            'akn_uri', 'signed_on', 'first_published_in__date'):
        if (signed or issued) and (signed or issued) <= date.today():
            born[uri] = signed or issued
    kept, seen = [], set()
    for c in out.changes:
        if c.text_uri in born and c.published_on and c.published_on < born[c.text_uri] - LATER:
            out.stats['refused_later'] += 1
            if (c.by_uri, c.by_article, c.text_uri) not in seen:
                seen.add((c.by_uri, c.by_article, c.text_uri))
                out.doubts.append(Doubt(by_uri=c.by_uri, by_article=c.by_article, reason=Doubt.Reason.TARGET_UNKNOWN,
                                        detail={'target': {'uri': c.text_uri}, 'why': 'later',
                                                'signed': str(born[c.text_uri])}))
            continue
        kept.append(c)
    out.changes[:] = kept


def _record(by: Text, article: Article, ins: Instructions, target: str, on, rule, words) -> list[Change]:
    """An instruction's changes, one per article it names (or the whole text)."""
    out = []
    if ins.action in ('modify', 'replace', 'add'):
        for u in ins.units:
            part = next((a['part'] for a in ins.articles if a['number'] == u.number and a['part']), None) or u.part
            out.append(_change(by, article, target, u.number, VERBS[ins.action], on, rule, words, wording=u.lines,
                               detail={'dotted': u.dotted, 'label': u.label, 'part': part}))
    elif ins.action == 'repeal':
        for a in ins.articles or [{'number': ''}]:
            out.append(_change(by, article, target, a['number'], Verb.REPEALED, on, rule, words,
                               detail={'part': a.get('part'), 'whole': not a['number']}))
    elif ins.action == 'words':
        for a in ins.articles or [{'number': ''}]:
            out.append(_change(by, article, target, a['number'], Verb.WORDS, on, rule, words,
                               wording=[f'«{old}» ← «{new}»' for old, new in ins.words], detail={'pairs': ins.words}))
    return out
