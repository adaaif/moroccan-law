"""Nightly (deploy/nightly.sh): OpenAI's published ChatGPT connector ranges, kept under CORPUS_DIR/mcp/ beside Anthropic's
(apps/mcp/services/origin.py). A fetch that fails, or a list that does not parse, leaves the last good copy in place."""
import ipaddress
import json
import urllib.request

from django.core.management.base import BaseCommand, CommandError

from apps.mcp.services import origin
from apps.sources.services import fetch

OPENAI = 'https://openai.com/chatgpt-connectors.json'


class Command(BaseCommand):
    help = "Refresh the assistants' platform address ranges the MCP server shares limits by."

    def handle(self, *args, **options):
        try:
            name = fetch.agent()
        except fetch.Unnamed as exc:
            raise CommandError(str(exc)) from exc
        base = json.loads(origin._source().read_text())
        try:
            request = urllib.request.Request(OPENAI, headers={'User-Agent': name, 'Accept': 'application/json'})
            with urllib.request.urlopen(request, timeout=15) as response:
                fetched = json.loads(response.read(2_000_000))
            prefixes = [p.get('ipv4Prefix') or p.get('ipv6Prefix') for p in fetched['prefixes']]
            for p in prefixes:
                ipaddress.ip_network(p, strict=False)
        except Exception as exc:  # noqa: BLE001 — the last good copy stays
            self.stdout.write(f'kept the last list: {exc}')
            return
        if not prefixes:
            self.stdout.write('kept the last list: OpenAI published no prefix')
            return
        base['chatgpt'] = {'source': OPENAI, 'as_of': str(fetched.get('creationTime', ''))[:10], 'prefixes': prefixes}
        path = origin.kept_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(base, indent=1) + '\n')
        tmp.replace(path)
        self.stdout.write(f"chatgpt: {len(prefixes)} prefixes as of {base['chatgpt']['as_of']}")
