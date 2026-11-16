"""Ministers' orders the model filed as decisions (R18 of the road plan): «قرار لوزير … رقم 1234.20» is an order, at
/akn/ma/act/arrete/1234-20, where a citation of «القرار رقم 1234.20» leads. Each moves there with its type, its old
address kept as an alias; a row waiting at the new address is merged in. Where the new address already holds the
order read from the same issue (one text loaded twice), the decision's copy goes; one from another issue is named
and left for a person.

    retype_orders            # what it would do
    retype_orders --write
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.corpus.models import Alias, Consolidation, Text
from apps.corpus.services import works
from apps.corpus.services.issue_structure import normalize_number


class Command(BaseCommand):
    help = "Move ministers' orders filed as decisions to their order addresses."

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')

    def handle(self, *args, write=False, **opts):
        counts = {'moved': 0, 'merged': 0, 'twins': 0, 'left': 0}
        for text in Text.objects.filter(type='decision').iterator():
            if not works.ministers_order(text.title_ar, text.number_as_printed):
                continue
            dest = works.address('order', normalize_number(text.number_as_printed))
            other = Text.objects.filter(akn_uri=dest).first()
            kind = 'moved'
            if other is not None and not works.mergeable(other):
                mine = set(text.versions.filter(consolidation=Consolidation.AS_PUBLISHED).values_list('source_document', flat=True))
                theirs = set(other.versions.filter(consolidation=Consolidation.AS_PUBLISHED).values_list('source_document', flat=True))
                if not mine & theirs:
                    counts['left'] += 1
                    self.stdout.write(f'  left: {text.akn_uri} and {dest} come from different issues')
                    continue
                kind = 'twins'
            elif other is not None:
                kind = 'merged'
            counts[kind] += 1
            if not write:
                continue
            with transaction.atomic():
                old = text.akn_uri
                if kind == 'twins':
                    # The same order read twice from one issue: the copy at its order address stays.
                    text.versions.filter(consolidation=Consolidation.AS_PUBLISHED).delete()
                    works.move(old, dest, Alias.Reason.MERGED)
                    if not text.versions.exists():
                        text.delete()
                    continue
                if other is not None:
                    works.merge(other, text)
                text.akn_uri, text.type = dest, 'order'
                text.save(update_fields=['akn_uri', 'type', 'updated_at'])
                works.move(old, dest, Alias.Reason.MOVED)
        self.stdout.write(str(counts))
