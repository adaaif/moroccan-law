"""The night's count of machines (deploy/nightly.sh): yesterday's requests read from nginx's access log, by family of
User-Agent, kind of address and status, into day counts that replace the day's `machine.*` rows. `--day` counts another
day, `--log` reads other files (NGINX_LOGS by default; a .gz is read as it is). A file that is missing or cannot be read
is said and passed over, and the command ends well: the first night after the deploy has no rotated file. A day with no
line in the files read keeps the counts it had."""
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.analytics.services import machines


class Command(BaseCommand):
    help = "Count yesterday's requests (or --day's) by machines from nginx's access log into day counts."

    def add_arguments(self, parser):
        parser.add_argument('--day', help='a Moroccan day, YYYY-MM-DD (default: yesterday)')
        parser.add_argument('--log', nargs='+', dest='logs', metavar='PATH', help='the log files (default: NGINX_LOGS)')

    def handle(self, *args, day, logs, **opts):
        try:
            day = date.fromisoformat(day) if day else timezone.localdate() - timedelta(days=1)
        except ValueError:
            raise CommandError(f'--day {day!r} is not a day (YYYY-MM-DD)') from None
        tally = machines.count(day, logs or settings.NGINX_LOGS)
        for path, lines, kept, why in tally.files:
            if why and not lines:
                self.stdout.write(f'{path}: not read ({why})')
            else:
                self.stdout.write(f'{path}: {lines} lines, {kept} of {day}' + (f', then stopped ({why})' if why else ''))
        if tally.total:
            written = machines.write(tally)
            share = 100 * tally.machines / tally.total
            self.stdout.write(f'{day}: {tally.total} requests, {tally.machines} by machines ({share:.1f} %), '
                              f'{written} counts')
        else:
            self.stdout.write(f'{day}: no request in these files, its counts left as they were')
        self.stdout.write(f'{tally.unread} lines not read')
