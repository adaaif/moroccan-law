"""The pipeline: each text at the address its kind and number give (`readdress`), then the stages run for the texts
given and every text they change or that their arrival unblocks (`run`), and the texts nothing changes any more
pruned."""
from collections import defaultdict

from django.db import transaction
from django.db.models import Q

from apps.consolidation.models import Change, Doubt, Verb
from apps.consolidation.services.engine.reading import Read, read_text, refuse_later
from apps.consolidation.services.engine.rebuild import apply_to
from apps.consolidation.services.engine.status import standing
from apps.consolidation.services.engine.targets import _dated, _resolved, where
from apps.consolidation.services.engine.weighing import WITNESSES, _issue_texts, weigh
from apps.consolidation.services.instructions.provisions import title_links
from apps.corpus.models import Consolidation, Mention, Text, Version
from apps.corpus.services import works


def readdress() -> dict:
    """Stage 2 for texts already in the corpus: each text at the address its kind and number give, empty twins merged
    into the text, the promulgating dahirs' addresses leading to their laws. Idempotent."""
    from apps.corpus.models import Alias
    from apps.corpus.services.issue_structure import normalize_number, own_name
    stats = defaultdict(int)
    for text in Text.objects.order_by('id'):
        old = text.akn_uri
        # A law read from the BO is the law its heading names (`as_law` does this for texts read from now on).
        own = own_name(text.title_ar) if text.type in ('law', 'organic_law') else None
        renumbered = False
        if own and (own[0], works.fold(normalize_number(own[1]))) != (text.type, works.fold(text.number)) \
                and text.versions.filter(consolidation=Consolidation.AS_PUBLISHED).exists():
            renumbered = works.fold(normalize_number(own[1])) != works.fold(text.number)
            text.type, text.number, text.number_as_printed = own[0], normalize_number(own[1]), own[1]
            text.save(update_fields=['type', 'number', 'number_as_printed', 'updated_at'])
            stats['renamed'] += 1
        new = works.uri_for(text.type, text.number, text.number_as_printed, old)
        if new == old:
            continue
        held = Text.objects.filter(akn_uri=new).first()
        if held is not None:
            if works.mergeable(held):
                works.merge(held, text)
                stats['merged'] += 1
            elif works.mergeable(text):
                works.merge(text, held)
                stats['merged'] += 1
                continue
            else:
                stats['clash'] += 1
                continue
        text.akn_uri = new
        text.number = works.fold(text.number)
        text.save(update_fields=['akn_uri', 'number', 'updated_at'])
        works.move(old, new, Alias.Reason.MOVED)
        if renumbered:
            Alias.objects.filter(alias=old).delete()    # the old address is another law's number: it leads nowhere
        stats['moved'] += 1
    for text in Text.objects.exclude(promulgating_dahir=''):
        dahir = works.address('dahir', normalize_number(text.promulgating_dahir))
        if dahir == text.akn_uri:
            continue
        twin = Text.objects.filter(akn_uri=dahir).first()
        if twin is not None:
            works.merge(twin, text)
        Alias.objects.update_or_create(alias=dahir, defaults={'uri': text.akn_uri, 'reason': Alias.Reason.DAHIR})
        stats['dahirs'] += 1
    for text in Text.objects.filter(versions__isnull=True, type__in=list(works.FAMILY)):
        for neighbour in works.FAMILY[text.type][1:]:
            held = Text.objects.filter(akn_uri=works.address(neighbour, text.number), versions__isnull=False).first()
            if held is not None and text.akn_uri == works.address(text.type, text.number):
                works.merge(text, held)
                stats['merged'] += 1
                break
    return dict(stats)


def run(texts: list[Text] | None = None, log=print) -> dict:
    """Stages 3 to 5 for the texts given (all texts read from the BO when None) and every text they change or that
    their arrival unblocks."""
    _resolved.cache_clear()
    _dated.cache_clear()
    _issue_texts.cache_clear()
    stats: dict = defaultdict(int)
    whole = texts is None
    if texts is None:
        # The BO's texts, and those the site holds only as a consolidation with visas (read for those alone).
        texts = list(Text.objects.filter(Q(versions__consolidation=Consolidation.AS_PUBLISHED)
                                         | (Q(versions__language='ar') & ~Q(versions__preamble=''))).distinct()
                     .select_related('first_published_in'))
    # A text the site holds only as a machine translation (BO 7410, from its official French) changes nothing and is
    # changed by nothing it says: its words are not the law's.
    printed = set(Version.objects.filter(text__in=texts, language='ar').exclude(consolidation=Consolidation.TRANSLATION)
                  .values_list('text_id', flat=True))
    texts = [t for t in texts if t.pk in printed]
    uris = {t.akn_uri for t in texts}
    # The texts these texts changed before this run: a change that is gone must leave their standing too.
    before = set(Change.objects.filter(source=Change.Source.READING, by_uri__in=uris).values_list('text_uri', flat=True))
    if whole:
        Change.objects.filter(source=Change.Source.READING).delete()
        Mention.objects.all().delete()
        Doubt.objects.filter(status=Doubt.Status.OPEN).delete()
    settled = set(Doubt.objects.exclude(status=Doubt.Status.OPEN).values_list('by_uri', 'number', 'reason'))
    worded = {(by, number): detail['wording'] for by, number, detail in Doubt.objects.filter(
        status=Doubt.Status.RESOLVED, reason=Doubt.Reason.UNPLACED, detail__has_key='wording').values_list(
        'by_uri', 'number', 'detail')}

    out = Read()
    for m in Change.objects.filter(source=Change.Source.MODEL, by_uri__in=uris):
        out.model.setdefault((m.by_uri, m.by_article), []).append(m)
    for t in texts:
        read_text(t, out)
    refuse_later(out)
    for k, v in out.stats.items():
        stats[k] += v
    with transaction.atomic():
        Change.objects.filter(source=Change.Source.READING, by_uri__in=uris).delete()
        Mention.objects.filter(from_uri__in=uris).delete()
        Doubt.objects.filter(status=Doubt.Status.OPEN, by_uri__in=uris).delete()
        Change.objects.bulk_create(out.changes, batch_size=2000)
        Mention.objects.bulk_create(out.mentions, batch_size=5000)
        changed = {c.text_uri for c in out.changes}
        held = set(Text.objects.filter(akn_uri__in=changed).values_list('akn_uri', flat=True))
        for uri in changed - held:
            works.wait(uri, works.kind_of(uri), uri.rsplit('/', 1)[-1], out.names.get(uri, ''))
            stats['waiting_texts'] += 1
    stats['changes'] += len(out.changes)
    stats['mentions'] += len(out.mentions)
    log(f'read {len(texts)} texts: {len(out.changes)} changes, {len(out.mentions)} mentions')

    # Every text a change touches, and the texts read now (changes read earlier may wait for them).
    targets = set(Change.objects.filter(source=Change.Source.READING, by_uri__in=uris).values_list('text_uri', flat=True))
    targets |= uris | before
    titled = dict(out.titled)
    doubts = list(out.doubts)
    for target in Text.objects.filter(akn_uri__in=targets):
        with transaction.atomic():
            Doubt.objects.filter(status=Doubt.Status.OPEN, text_uri=target.akn_uri).exclude(
                reason__in=(Doubt.Reason.UNCLEAR, Doubt.Reason.TARGET_UNKNOWN, Doubt.Reason.CORRECTION,
                            Doubt.Reason.COURT)).delete()
            changes = list(Change.objects.filter(text_uri=target.akn_uri, source=Change.Source.READING))
            if not changes and not target.versions.filter(consolidation=Consolidation.MACHINE).exists():
                continue
            for by in {c.by_uri for c in changes} - set(titled):
                t = Text.objects.filter(akn_uri=by).select_related('first_published_in').first()
                titled[by] = defaultdict(set)
                on = (t.first_published_in.date if t.first_published_in_id else t.signed_on) if t else None
                for r, c in (title_links(t.title_ar, t.number) if t else []):
                    if r in ('amends', 'repeals'):
                        titled[by][works.follow(where(c, on)[0])].add(r)
            doubts += weigh([c for c in changes if c.state != Change.State.UNCLEAR], settled, titled)
            for c in changes:
                # A model's reading is fact only with the SGG or Adala behind it: its first description of the text is
                # the same model, which makes the same mistakes (a paragraph's repeal read as the article's). A repeal
                # it reads is never fact.
                if (c.detail or {}).get('by_model') and c.state in (Change.State.READ, Change.State.CONFIRMED):
                    outside = any((c.witnesses or {}).get(k) for k in WITNESSES)
                    if c.verb == Verb.REPEALED or not outside:
                        c.state = Change.State.UNCLEAR
            Change.objects.bulk_update(changes, ['witnesses', 'state', 'verdict', 'score'], batch_size=2000)
            changes, more, st = apply_to(target, settled, worded)
            doubts += more
            Change.objects.bulk_update(changes, ['placed', 'detail', 'witnesses', 'state'], batch_size=2000)
            for k, v in st.items():
                stats[k] += v
    for t in Text.objects.filter(akn_uri__in=targets):
        status = standing(t)['status']
        if status != t.status:
            t.status = status
            t.save(update_fields=['status', 'updated_at'])
            stats[f'status_{status}'] += 1
    fresh = [d for d in doubts if (d.by_uri, d.number, d.reason) not in settled]
    Doubt.objects.bulk_create(fresh, batch_size=2000)
    stats['doubts'] += len(fresh)
    if whole:
        stats['waiting_pruned'] = prune_waiting()
    return dict(stats)


def prune_waiting() -> int:
    """Texts the site has not read that nothing changes any more (the model's guesses of 18 Oct made many): gone. A text
    cited only needs no row: its address is enough."""
    from apps.budget.models import FinanceLaw
    changed = set(Change.objects.values_list('text_uri', flat=True))
    kept = set(FinanceLaw.objects.exclude(text=None).values_list('text_id', flat=True))
    gone = [t.pk for t in Text.objects.filter(versions__isnull=True) if t.akn_uri not in changed and t.pk not in kept]
    for start in range(0, len(gone), 500):
        Text.objects.filter(pk__in=gone[start:start + 500]).delete()
    return len(gone)
