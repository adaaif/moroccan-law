"""DB-IP's free «IP to ASN Lite» database (CC BY 4.0, NOTICE), monthly, no account: the network operator of an address
for the day of reading's READING_OPERATOR_CEILING (apps/corpus/services/operators.py). The newest month that answers is
written to GEOIP_DIR as dbip-asn-lite.mmdb, the month's file kept beside it.

    fetch_geoip"""
import gzip
import shutil
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.corpus.services.operators import ASN
from apps.sources.services import fetch

URL = 'https://download.db-ip.com/free/dbip-asn-lite-{month}.mmdb.gz'


class Command(BaseCommand):
    help = "Fetch DB-IP's free ASN database (CC BY 4.0) for the day of reading's ceiling per network operator."

    def handle(self, *args, **opts):
        try:
            name = fetch.agent()
        except fetch.Unnamed as exc:
            raise CommandError(str(exc)) from exc
        folder = Path(settings.GEOIP_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        today = date.today()
        for month in (today.strftime('%Y-%m'), (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')):
            url = URL.format(month=month)
            kept = folder / f'dbip-asn-lite-{month}.mmdb'
            try:
                if not kept.exists():
                    request = urllib.request.Request(url, headers={'User-Agent': name})
                    with urllib.request.urlopen(request, timeout=120) as answer, open(f'{kept}.tmp', 'wb') as out:
                        shutil.copyfileobj(gzip.GzipFile(fileobj=answer), out)
                    Path(f'{kept}.tmp').replace(kept)
            except OSError as e:
                self.stderr.write(f'{url}: {e}')
                continue
            current = folder / ASN
            shutil.copyfile(kept, f'{current}.tmp')
            Path(f'{current}.tmp').replace(current)
            self.stdout.write(f'asn: {month}, {kept.stat().st_size // 2**20} MB')
            return
        raise CommandError('no asn database could be fetched')
