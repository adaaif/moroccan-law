from django.core.management.base import BaseCommand

from apps.topics.services import places


class Command(BaseCommand):
    help = ('The BO\'s land texts since 2019 read as places and plots for «أرضي فالجريدة الرسمية» (the land review, '
            'M8–M9): their kind, communes, provinces, properties, numbers and table rows. $0; run after a load.')

    def handle(self, *args, **opts):
        out = places.build()
        self.stdout.write(f"{out['texts']} texts, {out['rows']} rows")
        for kind, n in sorted(out['kinds'].items(), key=lambda x: -x[1]):
            self.stdout.write(f'  {kind}: {n}')
