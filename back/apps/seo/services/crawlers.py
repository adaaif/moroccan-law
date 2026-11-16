"""The search engines' crawlers, known by the addresses their makers publish (IX10 of the search-engines review, 9 Nov 2026):
Google, Bing, Apple, OpenAI's search and Perplexity's. A crawler named by its User-Agent alone is anyone who typed it;
an address in a published list is that crawler. The fetchers an assistant's user drives (ChatGPT's, Perplexity's) are
not here: anyone can send them, so they are held like any reader.

They read past a day's reading (apps/corpus/services/reading.py) and the public API's per-address limit
(apps/opendata/throttles.py): Google renders a page by asking for the same answers a reader's browser does, from a few
addresses, all day. The training crawlers (GPTBot, ClaudeBot, CCBot, Google-Extended, Applebot-Extended) are not here:
robots.txt turns them away (C4, apps/seo/views.py).

The lists: `apps/seo/data/crawlers.json` as of the dates it holds, replaced by the copy `refresh_crawlers` keeps under
CORPUS_DIR each night (deploy/nightly.sh), as apps/mcp/services/origin.py does for the assistants' connectors. A list
that names a network wider than WIDEST is refused (`refresh_crawlers`), and such a network is never read: a mistaken
0.0.0.0/0 would lift both limits for everyone."""
import ipaddress
import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings

BUNDLED = Path(__file__).resolve().parent.parent / 'data' / 'crawlers.json'

SOURCES = {
    'googlebot': 'https://developers.google.com/static/search/apis/ipranges/googlebot.json',
    'bingbot': 'https://www.bing.com/toolbox/bingbot.json',
    'applebot': 'https://search.developer.apple.com/applebot.json',
    'oai-searchbot': 'https://openai.com/searchbot.json',
    'perplexitybot': 'https://www.perplexity.ai/perplexitybot.json',
}
# The widest network a crawler's list may name: a /16 of IPv4 addresses, a /32 of IPv6.
WIDEST = {4: 16, 6: 32}


def too_wide(network) -> bool:
    return network.prefixlen < WIDEST[network.version]


def kept_file() -> Path:
    return Path(settings.CORPUS_DIR) / 'seo' / 'crawlers.json'


def source() -> Path:
    kept = kept_file()
    return kept if kept.exists() else BUNDLED


@lru_cache(maxsize=4)
def _networks(path: str, mtime: float) -> tuple:
    data = json.loads(Path(path).read_text())
    # Only the search engines named above, even from a list kept before; never a network wider than WIDEST.
    found = [(name, ipaddress.ip_network(p, strict=False)) for name, entry in data.items() if name in SOURCES
             for p in entry['prefixes']]
    found = [(name, network) for name, network in found if not too_wide(network)]
    return tuple(n for n in found if n[1].version == 4), tuple(n for n in found if n[1].version == 6)


def crawler(ip: str) -> str:
    """The crawler whose published list holds this address ('googlebot', 'bingbot', …), or ''."""
    try:
        address = ipaddress.ip_address((ip or '').strip())
    except ValueError:
        return ''
    path = source()
    v4, v6 = _networks(str(path), path.stat().st_mtime)
    for name, network in v4 if address.version == 4 else v6:
        if address in network:
            return name
    return ''


def of(request) -> str:
    """The verified crawler a request comes from, by the address Cloudflare saw."""
    from apps.opendata.throttles import address
    raw = getattr(request, '_request', request)
    if not hasattr(raw, '_crawler'):
        raw._crawler = crawler(address(raw))
    return raw._crawler
