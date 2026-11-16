"""The counts kept before the measures began, brought into the day counts as `past.*` (services/past.py): the removed
request log's day totals from data/past_counts.json, and the topics' tool counter. Run again, it writes the same rows
over its own."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.analytics.services import past


class Command(BaseCommand):
    help = 'Bring the counts from before 16 Nov 2026 into the day counts (past.*), replacing what they held.'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(past.FILE), help="the request log's day totals, as JSON")

    def handle(self, *args, file, **opts):
        try:
            written = past.bring_in(Path(file))
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise CommandError(f'{file}: {e!r}') from None
        self.stdout.write(f"{written['log']} counts from the request log's days, {written['tools']} from the tool counter")
