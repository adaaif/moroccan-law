"""Nightly (deploy/nightly.sh): what the assistants' sign-in keeps no longer than /privacy says.

- Requests and codes once expired; access tokens once expired; refresh tokens once expired or replaced a day ago.
- Ended connections after 90 days, with their days and tokens.
- Each connection's daily counts after 90 days.
- A registered client never used after 7 days (Claude registers again on each fresh connection without its metadata
  document), and a metadata document's client with no connection after 90 days.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.oauth.models import AuthRequest, Client, Code, Day, Grant, Token


class Command(BaseCommand):
    help = 'Remove the expired parts of the assistants\' sign-in, and their counts after 90 days.'

    def handle(self, *args, **options):
        now = timezone.now()
        quarter = now - timedelta(days=90)
        gone = {
            'requests': AuthRequest.objects.filter(expires_at__lt=now).delete()[0],
            'codes': Code.objects.filter(expires_at__lt=now).delete()[0],
            'tokens': Token.objects.filter(Q(expires_at__lt=now) | Q(replaced_at__lt=now - timedelta(days=1))).delete()[0],
            'connections': Grant.objects.filter(revoked_at__lt=quarter).delete()[0],
            'days': Day.objects.filter(day__lt=timezone.localdate() - timedelta(days=90)).delete()[0],
            'clients': Client.objects.filter(
                Q(kind=Client.Kind.DCR, used_at=None, created_at__lt=now - timedelta(days=7))
                | Q(created_at__lt=quarter, grants=None)).delete()[0],
        }
        self.stdout.write(' '.join(f'{k}: {v}' for k, v in gone.items()))
