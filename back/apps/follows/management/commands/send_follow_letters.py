"""One letter to each account whose follows changed since it was last told (R13 of the for-everyone review). Run after
`consolidate` read a new issue."""
from django.core.management.base import BaseCommand

from apps.follows.services import following


class Command(BaseCommand):
    help = 'Send the follows letters: what changed in the laws, articles and topics people follow.'

    def handle(self, *args, **options):
        self.stdout.write(f'{following.send_letters()} letters')
