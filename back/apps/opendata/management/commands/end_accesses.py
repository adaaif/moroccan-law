"""The night's job for access on request (deploy/nightly.sh): the accesses whose end date passed are ended and their
holders told; each holder whose access ends in exactly 30 days gets a letter; and the requests past the retention
/privacy states lose their typed answers (a declined one six months after the decision, an accepted one twelve months
after its access ended). It writes nothing a public answer is made of (manage.py READ_ONLY)."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.opendata.services import access, requests


class Command(BaseCommand):
    help = 'End the accesses past their end date, warn those ending in 30 days, empty old requests\' typed answers.'

    def handle(self, *args, **opts):
        today = timezone.localdate()
        ended = access.expire(today)
        warned = access.warn(today)
        emptied = requests.forget_typed(today)
        self.stdout.write(f'{ended} accesses ended, {warned} holders told their access ends in {access.WARN_DAYS} '
                          f'days, {emptied} requests emptied')
