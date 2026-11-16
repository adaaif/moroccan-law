"""The Monday letter (services/letter.py, deploy/law-analytics-letter.timer): the last 7 complete days' ten figures, each
beside the 7 before, in plain text to ANALYTICS_LETTER_TO. With no address set it says so and sends nothing; a letter
the mail service did not take fails the command, so its unit says so."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.services import mail
from apps.analytics.services import letter


class Command(BaseCommand):
    help = "Send the week's counts to ANALYTICS_LETTER_TO, in plain text."

    def handle(self, *args, **opts):
        to = settings.ANALYTICS_LETTER_TO
        if not to:
            self.stdout.write('ANALYTICS_LETTER_TO is empty: no letter sent')
            return
        subject, body = letter.letter()
        if not mail.plain(to, subject, body):
            raise CommandError('the letter was not sent: the log says why')
        self.stdout.write(f'«{subject}» sent to {len(to)} address{"es" if len(to) > 1 else ""}')
