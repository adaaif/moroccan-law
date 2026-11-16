"""Nightly and at each deploy: the sitemaps under SITEMAPS_DIR (apps/seo/services/sitemaps.py)."""
from django.core.management.base import BaseCommand

from apps.seo.services import sitemaps


class Command(BaseCommand):
    help = 'Write the sitemaps and the index of the open waves.'

    def handle(self, *args, **options):
        done = sitemaps.write()
        total = sum(done['files'].values())
        listed = sum(done['files'][n] for n in done['listed'])
        self.stdout.write(f"wave {done['wave']}: {len(done['files'])} files, {total:,} addresses; "
                          f"{len(done['listed'])} files and {listed:,} addresses in the index")
