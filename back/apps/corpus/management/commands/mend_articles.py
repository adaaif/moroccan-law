"""Every article in its text (FX6 of the mended-Bulletin review).

    mend_articles              what would change: numbers to give, articles 1 to put back, first, or out of a preamble
    mend_articles --write      does it, then puts the search index right
"""
from django.core.management.base import BaseCommand

from apps.corpus.services import articles


class Command(BaseCommand):
    help = 'Give articles their numbers and texts their article 1 (a dry run unless --write).'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')

    def handle(self, *args, write: bool, **opts):
        from django.db import transaction

        from apps.corpus.models import Text
        from apps.corpus.services import generation
        from apps.search.services.index import rebuild

        self.stdout.write(f'{articles.numbers(write=write)} articles whose label carries a number their row lacked'
                          + (' — given' if write else ''))
        found = articles.problems()
        texts, left = set(), []
        for kind, mend in (('missing', articles.restore_first), ('late', articles.put_in_order),
                           ('preamble', articles.split_preamble)):
            done = 0
            for v in found[kind]:
                if not write:
                    ok = articles.found_first(v) is not None if kind == 'missing' else True
                else:
                    with transaction.atomic():
                        ok = mend(v)
                done += ok
                if ok:
                    texts.add(v.text_id)
                else:
                    left.append(f'{kind}: {v.text.akn_uri}')
            self.stdout.write(f'{kind}: {done} of {len(found[kind])} ' + ('mended' if write else 'can be mended'))
        for line in left[:40]:
            self.stdout.write(f'  left: {line}')
        if write:
            rebuild(list(Text.objects.filter(pk__in=texts)), log=self.stdout.write)
            generation.bump('corpus')
