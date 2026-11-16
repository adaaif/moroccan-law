"""The rows an address keeps, moved when a text's address changes: everything kept by the old address (changes,
mentions, translations, memoranda, reports, the later apps' paths) and an alias left behind; a twin merged, a copy
folded, a row waiting for its issue, a dahir's number filed as a law's folded into the dahir."""
import re

from django.db import IntegrityError, transaction

from apps.corpus.models import Alias, Text
from apps.corpus.services.works.identity import address, fold, path_of


def move(old: str, new: str, reason: str) -> None:
    """Everything kept by `old`'s address now kept by `new`'s, and `old` an alias of `new`. The tables that keep a text
    by its address: changes and doubts, mentions, the French translation, the explanatory memoranda, the bills,
    readers' reports (by path), and the aliases that led to `old`."""
    from apps.consolidation.models import Change, Doubt
    from apps.corpus.models import Mention
    from apps.parliament.models import Explanation
    from apps.quality.models import Report
    from apps.sources.models import Document, Source
    from apps.translations.models import FrenchArticle, FrenchText

    if old == new:
        return
    Change.objects.filter(text_uri=old).update(text_uri=new)
    Change.objects.filter(by_uri=old).update(by_uri=new)
    Doubt.objects.filter(text_uri=old).update(text_uri=new)
    Doubt.objects.filter(by_uri=old).update(by_uri=new)
    Mention.objects.filter(from_uri=old).update(from_uri=new)
    Mention.objects.filter(to_uri=old).update(to_uri=new)
    if not FrenchText.objects.filter(text_uri=new).exists():
        FrenchText.objects.filter(text_uri=old).update(text_uri=new)
        FrenchArticle.objects.filter(text_uri=old).update(text_uri=new)
    if not Explanation.objects.filter(text_uri=new).exists():
        Explanation.objects.filter(text_uri=old).update(text_uri=new)
    for doc in Document.objects.filter(source=Source.PARLIAMENT, meta__text_uri=old):
        doc.meta = {**doc.meta, 'text_uri': new}
        doc.save(update_fields=['meta'])
    old_path, new_path = path_of(old), path_of(new)
    for report in Report.objects.filter(path__startswith=old_path):
        if report.path == old_path or report.path.startswith(old_path + '/'):
            report.path = new_path + report.path[len(old_path):]
            report.save(update_fields=['path'])
    _repath(old_path, new_path)
    Alias.objects.filter(uri=old).update(uri=new)
    Alias.objects.filter(alias=new).delete()
    Alias.objects.update_or_create(alias=old, defaults={'uri': new, 'reason': reason})


def _repath(old_path: str, new_path: str) -> None:
    """The rows later apps keep by the site's path follow the text to its new address (R18 of the road plan, when
    14,422 orders moved): a reader's correction (applied again at every reload), a discussion, an explanation, a
    follow. A path the new address already holds is left where it was."""
    from django.apps import apps
    for label, fields in (('quality.Correction', ('path',)), ('discussion.Discussion', ('path', 'text_path')),
                          ('explain.Explanation', ('path',)), ('follows.Follow', ('path',))):
        try:
            model = apps.get_model(label)
        except LookupError:
            continue        # an app this branch does not have
        for field in fields:
            for row in model.objects.filter(**{f'{field}__startswith': old_path}):
                value = getattr(row, field)
                if value != old_path and not value.startswith(old_path + '/') and not value.startswith(old_path + '#'):
                    continue
                setattr(row, field, new_path + value[len(old_path):])
                try:
                    with transaction.atomic():
                        row.save(update_fields=[field])
                except IntegrityError:
                    pass


def mergeable(twin: Text) -> bool:
    """A row that only waits for its text, or holds only someone else's consolidation of it (the SGG's, Adala's):
    never one whose words were read from the BO."""
    return not twin.versions.filter(consolidation='as_published').exists()


def merge(twin: Text, into: Text) -> None:
    """A twin row folded into the text: its consolidations move over, its address leads there."""
    from apps.budget.models import FinanceLaw
    if twin.pk == into.pk or not mergeable(twin):
        return
    for v in twin.versions.all():
        if into.versions.filter(language=v.language, valid_from=v.valid_from, consolidation=v.consolidation).exists():
            v.delete()
        else:
            v.text = into
            v.save(update_fields=['text'])
    FinanceLaw.objects.filter(text=twin).update(text=into)
    if not into.title_ar and twin.title_ar:
        into.title_ar = twin.title_ar
        into.save(update_fields=['title_ar', 'updated_at'])
    old = twin.akn_uri
    twin.delete()
    move(old, into.akn_uri, Alias.Reason.MERGED)


def fold_copy(twin: Text, into: Text, reason: str = Alias.Reason.COPY) -> None:
    """A text cut twice, from an issue and from a copy of it (FX3 of the mended-Bulletin review), folded into the cut that
    is kept: the twin's own readings of the Bulletin go (the kept text has its own), anything else it holds that the
    kept text lacks (a translation, a consolidation) moves over, and its address leads to the kept one. `merge` never
    folds a text read from the Bulletin; this does, for two cuts of one printed text only."""
    from apps.budget.models import FinanceLaw
    if twin.pk == into.pk:
        return
    for v in twin.versions.all():
        if v.consolidation == 'as_published' or into.versions.filter(
                language=v.language, valid_from=v.valid_from, consolidation=v.consolidation).exists():
            v.delete()
        else:
            v.text = into
            v.save(update_fields=['text'])
    FinanceLaw.objects.filter(text=twin).update(text=into)
    old = twin.akn_uri
    twin.delete()
    move(old, into.akn_uri, reason)


def wait(uri: str, kind: str, number: str, title: str) -> Text:
    """The row a text gets before its own issue is read: its address, kind, number and the title it is cited by."""
    text, _ = Text.objects.get_or_create(akn_uri=uri, defaults={
        'type': kind, 'number': fold(number), 'number_as_printed': fold(number).replace('-', '.'),
        'title_ar': title[:500]})
    return text


DAHIR_NUMBER = re.compile(r'^/akn/ma/act/loi/(1-\d+-\d+)$')


def fold_dahir_numbers(log=print) -> dict:
    """A number in three parts (1.72.184) is a dahir's: a row filed as a law under it (the SGG lists «قانون رقم
    1.72.184») is folded into the dahir's row, or moves to the dahir's address when there is none. Rows read from the
    BO are left alone (T2 of the work plan: the social security dahir's changes were split between two addresses)."""
    folded = moved = 0
    for row in Text.objects.filter(akn_uri__regex=DAHIR_NUMBER.pattern):
        if not mergeable(row):
            continue
        target = address('dahir', DAHIR_NUMBER.match(row.akn_uri).group(1))
        twin = Text.objects.filter(akn_uri=target).first()
        if twin is not None:
            merge(row, twin)
            folded += 1
        else:
            old = row.akn_uri
            row.akn_uri, row.type = target, 'dahir'
            row.save(update_fields=['akn_uri', 'type', 'updated_at'])
            move(old, target, Alias.Reason.MERGED)
            moved += 1
        log(f'  {row.akn_uri if twin is None else target}')
    return {'folded': folded, 'moved': moved}
