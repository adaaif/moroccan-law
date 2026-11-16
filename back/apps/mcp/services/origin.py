"""Where a call to the MCP server comes from, when nobody signs in (open to everyone since 3 Nov 2026): an assistant's
platform by its published address ranges (Claude, ChatGPT), or a direct caller by its
address (a script, the MCP Inspector, Claude Code). Every Claude user arrives from Anthropic's few addresses and every
ChatGPT user from OpenAI's: a limit per address would be a limit on all of them at once, so a platform shares one wide
limit and a direct caller has its own.

The ranges: `apps/mcp/data/platforms.json` (Anthropic's from its connector documentation, OpenAI's
chatgpt-connectors.json as of its date), replaced by the copy `refresh_platforms` keeps under CORPUS_DIR each night
(OpenAI's ranges change, best effort by its own word)."""
import ipaddress
import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings

BUNDLED = Path(__file__).resolve().parent.parent / 'data' / 'platforms.json'


def kept_file() -> Path:
    return Path(settings.CORPUS_DIR) / 'mcp' / 'platforms.json'


def _source() -> Path:
    kept = kept_file()
    return kept if kept.exists() else BUNDLED


@lru_cache(maxsize=4)
def _networks(path: str, mtime: float) -> list[tuple[str, ipaddress._BaseNetwork]]:
    data = json.loads(Path(path).read_text())
    return [(name, ipaddress.ip_network(p, strict=False)) for name, entry in data.items() for p in entry['prefixes']]


def platform(ip: str) -> str:
    """'claude', 'chatgpt', or '' for an address no platform publishes."""
    try:
        address = ipaddress.ip_address((ip or '').strip())
    except ValueError:
        return ''
    path = _source()
    for name, network in _networks(str(path), path.stat().st_mtime):
        if address.version == network.version and address in network:
            return name
    return ''


def bucket(ip: str) -> str:
    """A direct caller's key: an IPv4 address as itself, an IPv6 one by its /64 (one line, one household holds a whole
    /64), as every limit counts it (apps/opendata/throttles.py)."""
    from apps.opendata.throttles import bucket as by_network
    return by_network(ip)


def client_name(user_agent: str) -> str:
    """The product a direct caller names itself by («python-httpx», «node», «Cursor»), for the day's counts."""
    first = (user_agent or '').split(' ', 1)[0].split('/', 1)[0].strip()
    return first[:40] or 'unknown'
