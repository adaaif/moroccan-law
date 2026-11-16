"""Every few minutes (deploy/law-letters.timer): the letters the discussion's notices claimed, sent. A request that
makes a notice never calls the mail provider; this job does, one letter at a time, each once."""
from django.core.management.base import BaseCommand

from apps.discussion.services import notices


class Command(BaseCommand):
    help = "Send the letters the discussion's notices are waiting for."

    def handle(self, *args, **options):
        sent = 0
        while True:
            claimed, took = notices.send_due()
            sent += took
            if claimed < notices.LETTERS_A_RUN:
                break
        self.stdout.write(f'{sent} letters sent')
