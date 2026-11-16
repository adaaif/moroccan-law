"""Takes out of the stored French articles the next part's heading their readers ran into them (N15 of
the read-and-trusted review: 456 articles of 30 texts in the development database, 92 in the Labour Code). The API trims what it serves
either way; this keeps search's index and the open data clean. --write to save."""
from django.core.management.base import BaseCommand

from apps.translations.models import FrenchArticle
from apps.translations.services import divisions


class Command(BaseCommand):
    help = "Take the next part's heading out of the stored French articles' ends."

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')

    def handle(self, *args, write, **options):
        changed = []
        for a in FrenchArticle.objects.only('pk', 'body').iterator(chunk_size=2000):
            body = divisions.trim(a.body)
            if body != a.body.rstrip():
                a.body = body
                changed.append(a)
        if write:
            FrenchArticle.objects.bulk_update(changed, ['body'], batch_size=500)
        self.stdout.write(f'{len(changed)} French articles {"trimmed" if write else "to trim (--write)"}')
