"""An editor's approval of the situations' drafts (call C2): the named drafts are copied, as they are, into
apps/corpus/data/situations_approved.json, which readers see. A draft sent back stays a draft."""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.corpus.services.situations import APPROVED, DRAFTS, load


class Command(BaseCommand):
    help = 'Publish the situations an editor approved.'

    def add_arguments(self, parser):
        parser.add_argument('slugs', nargs='+', help='the approved situations')

    def handle(self, *args, slugs, **options):
        drafts = {s['slug']: s for s in load(DRAFTS)}
        unknown = [s for s in slugs if s not in drafts]
        if unknown:
            raise CommandError(f'no draft for {", ".join(unknown)}')
        approved = {s['slug']: s for s in load(APPROVED)}
        approved.update({s: {k: v for k, v in drafts[s].items() if k != 'draft'} for s in slugs})
        APPROVED.write_text(json.dumps({'about': 'Situations an editor approved (call C2); readers see these.',
                                        'situations': list(approved.values())}, ensure_ascii=False, indent=1) + '\n')
        self.stdout.write(f'{len(approved)} situations approved')
