"""What a topic's folder cites that the site does not have, doors to missing pages, and pages whose articles changed since
their check (F16 of the family plan).

    check_topic family
"""
from django.core.management.base import BaseCommand

from apps.topics.services import kit


class Command(BaseCommand):
    help = "Check a topic's folder against the corpus."

    def add_arguments(self, parser):
        parser.add_argument('slug')

    def handle(self, *args, slug, **opts):
        found = kit.problems(slug)
        content = kit.load(slug) or {}
        counts = {k: len(content.get(k, {})) for k in kit.KINDS}
        self.stdout.write(f'{slug}: {counts}, {len(kit.cited(content))} articles cited')
        for p in found:
            self.stdout.write(f'  {p}')
        if not found:
            self.stdout.write('  nothing to fix')
