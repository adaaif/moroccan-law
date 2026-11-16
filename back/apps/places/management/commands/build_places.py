from django.core.management.base import BaseCommand

from apps.places.services import build


class Command(BaseCommand):
    help = ('Count the places in every Arabic text of the Bulletin (general and conventions editions): «Places in the '
            'Bulletin», PL2. $0; run after make_gazetteer and after each load.')

    def handle(self, *args, **opts):
        self.stdout.write(str(build.build(log=self.stdout.write)))
