"""The night's fold (deploy/nightly.sh): yesterday's events made into counts kept for good, then the events older than
ANALYTICS_DAYS deleted. `--day` folds another day; `--all` every day still held, up to yesterday (after the fold's rules
changed). Folding a day again replaces its counts."""
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.analytics.services import fold


class Command(BaseCommand):
    help = "Fold yesterday's events (or --day, or --all) into day counts, then delete the events past ANALYTICS_DAYS."

    def add_arguments(self, parser):
        which = parser.add_mutually_exclusive_group()
        which.add_argument('--day', help='a Moroccan day, YYYY-MM-DD')
        which.add_argument('--all', action='store_true', dest='every', help='every day still held, up to yesterday')

    def handle(self, *args, day, every, **opts):
        yesterday = timezone.localdate() - timedelta(days=1)
        if every:
            first, last = fold.first_day(), yesterday
        else:
            try:
                first = last = date.fromisoformat(day) if day else yesterday
            except ValueError:
                raise CommandError(f'--day {day!r} is not a day (YYYY-MM-DD)') from None
        if first is not None and first <= last:
            written = fold.fold(first, last)
            self.stdout.write(f'{first} to {last}: {written} counts' if first != last else f'{first}: {written} counts')
        else:
            self.stdout.write('no day to fold')
        self.stdout.write(f'{fold.forget()} events older than the days kept deleted')
