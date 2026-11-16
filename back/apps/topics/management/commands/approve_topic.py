"""Record that a person checked a page of a topic (F16, F17 of the family plan): who, when, and the digests of the
articles it cites, in the database (the review desk does the same under the signed-in account). Only then does a reader
see it; a later change to one of those articles marks it «يحتاج مراجعة».

    approve_topic family journeys/divorce-agreement --by "a reviewer"
    approve_topic family tools/inheritance --by "an adoul"
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.topics.services import kit


class Command(BaseCommand):
    help = 'Record that a person checked a journey, checklist, page, the reform, a series or a tool.'

    def add_arguments(self, parser):
        parser.add_argument('slug')
        parser.add_argument('refs', nargs='+', help='kind/key, e.g. journeys/marry or tools/inheritance')
        parser.add_argument('--by', required=True, help='who checked it, as readers will see it')

    def handle(self, *args, slug, refs, by, **opts):
        try:
            kit.record_checks(slug, refs, by, date.today().isoformat())
        except KeyError as e:
            raise CommandError(f'{slug}: no {e}') from e
        self.stdout.write(f'{slug}: {len(refs)} checked by {by}')
