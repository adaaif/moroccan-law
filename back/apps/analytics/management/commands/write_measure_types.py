"""The registry's names and rules written for the web (apps/analytics/services/typescript.py): run it after changing
apps/analytics/registry.py, and commit both."""
from django.core.management.base import BaseCommand

from apps.analytics.services import typescript


class Command(BaseCommand):
    help = 'Write web/src/shared/analytics/measures.ts from the analytics registry.'

    def handle(self, *args, **opts):
        typescript.write()
        self.stdout.write(f'{typescript.TARGET} written')
