"""Nightly (deploy/nightly.sh): the crawlers' published address lists, kept under CORPUS_DIR/seo/ (apps/seo/services/
crawlers.py). A list that fails to come or to parse, or names a network wider than crawlers.WIDEST, keeps its last good
copy; the others are replaced. Lists of names no longer in crawlers.SOURCES are dropped."""
import ipaddress
import json
import urllib.request

from django.core.management.base import BaseCommand, CommandError

from apps.seo.services import crawlers
from apps.sources.services.fetch import Unnamed, agent


def fetch(url: str) -> tuple[str, list[str]]:
    request = urllib.request.Request(url, headers={'User-Agent': agent(), 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read(4_000_000))
    return checked(str(data.get('creationTime', ''))[:10],
                   [p.get('ipv4Prefix') or p.get('ipv6Prefix') for p in data['prefixes']])


def checked(as_of: str, prefixes: list[str]) -> tuple[str, list[str]]:
    """A list as published, if every network in it parses and is no wider than a crawler is given."""
    for p in prefixes:
        if crawlers.too_wide(ipaddress.ip_network(p, strict=False)):
            raise ValueError(f'{p} is wider than a crawler is given')
    if not prefixes:
        raise ValueError('no prefix')
    return as_of, prefixes


class Command(BaseCommand):
    help = "Refresh the search engines' published crawler addresses."

    def handle(self, *args, **options):
        try:
            agent()
        except Unnamed as exc:
            raise CommandError(str(exc)) from exc
        kept = {name: entry for name, entry in json.loads(crawlers.source().read_text()).items()
                if name in crawlers.SOURCES}
        for name, url in crawlers.SOURCES.items():
            try:
                as_of, prefixes = fetch(url)
            except Exception as exc:  # noqa: BLE001 — the last good copy stays
                self.stdout.write(f'{name}: kept the last list ({exc})')
                continue
            kept[name] = {'source': url, 'as_of': as_of, 'prefixes': prefixes}
            self.stdout.write(f'{name}: {len(prefixes)} prefixes as of {as_of}')
        path = crawlers.kept_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(kept, indent=1) + '\n')
        tmp.replace(path)
