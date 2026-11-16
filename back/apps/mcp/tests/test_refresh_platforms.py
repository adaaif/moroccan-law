"""`refresh_platforms` (nightly): OpenAI's published ChatGPT connector ranges, kept under CORPUS_DIR/mcp/ beside
Anthropic's; a fetch that fails or a list that does not parse leaves the last good copy as it was. The network is
OpenAI's file as it publishes it (chatgpt-connectors.json)."""
import io
import json
import urllib.error
import urllib.request

import pytest
from django.core.management import call_command

from apps.mcp.services import origin

OPENAI = 'https://openai.com/chatgpt-connectors.json'


class Published:
    """urlopen as the standard library gives it: a response read up to the size asked, or the error it raises."""

    def __init__(self, body=None, error=None):
        self.body, self.error, self.asked = body, error, []

    def __call__(self, request, timeout=None):
        self.asked.append((request.full_url, dict(request.header_items()), timeout))
        if self.error:
            raise self.error
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, amount=-1):
        return self.body[:amount] if amount >= 0 else self.body


def openai(*prefixes, created='2026-11-12T21:31:01.000000'):
    """The file in OpenAI's own shape: its creation time and an object a prefix, IPv4 or IPv6."""
    return json.dumps({'creationTime': created, 'prefixes': [
        {'ipv6Prefix': p} if ':' in p else {'ipv4Prefix': p} for p in prefixes]}).encode()


@pytest.fixture
def kept(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    return tmp_path / 'mcp' / 'platforms.json'


def refresh(monkeypatch, published) -> str:
    monkeypatch.setattr(urllib.request, 'urlopen', published)
    out = io.StringIO()
    call_command('refresh_platforms', stdout=out)
    return out.getvalue().strip()


def test_openais_ranges_are_kept_beside_anthropics_and_read_at_once(monkeypatch, settings, kept):
    published = Published(openai('198.51.100.0/24', '2001:db8:42::/48'))
    said = refresh(monkeypatch, published)
    assert said == 'chatgpt: 2 prefixes as of 2026-11-12'
    assert published.asked == [(OPENAI, {'User-agent': settings.FETCH_USER_AGENT, 'Accept': 'application/json'}, 15)]
    data = json.loads(kept.read_text())
    assert data['chatgpt'] == {'source': OPENAI, 'as_of': '2026-11-12', 'prefixes': ['198.51.100.0/24', '2001:db8:42::/48']}
    assert data['claude'] == json.loads(origin.BUNDLED.read_text())['claude']
    assert not kept.with_suffix('.tmp').exists()
    assert origin.platform('198.51.100.20') == 'chatgpt' and origin.platform('2001:db8:42::9') == 'chatgpt'
    assert origin.platform('160.79.104.9') == 'claude'
    # The next night starts from the copy kept, not the bundled list: what was added to it stays.
    data['claude']['prefixes'].append('192.0.2.0/24')
    kept.write_text(json.dumps(data))
    refresh(monkeypatch, Published(openai('203.0.113.0/24', created='2026-11-13T21:30:00.000000')))
    data = json.loads(kept.read_text())
    assert data['claude']['prefixes'] == ['160.79.104.0/21', '192.0.2.0/24']
    assert (data['chatgpt']['prefixes'], data['chatgpt']['as_of']) == (['203.0.113.0/24'], '2026-11-13')


@pytest.mark.parametrize('published, said', [
    (Published(error=urllib.error.URLError('timed out')), 'kept the last list: <urlopen error timed out>'),
    (Published(b'<html>Just a moment...</html>'), 'kept the last list: '),
    (Published(openai('198.51.100.0/24', '198.51.100.300/24')), 'kept the last list: '),
    (Published(json.dumps({'creationTime': '2026-11-12', 'prefixes': [{'service': 'chatgpt'}]}).encode()),
     'kept the last list: '),
    (Published(openai()), 'kept the last list: OpenAI published no prefix'),
    # More than the two million bytes read: what was read does not parse.
    (Published(openai(*[f'10.{n // 256}.{n % 256}.0/24' for n in range(60_000)])), 'kept the last list: '),
])
def test_a_list_that_does_not_come_or_does_not_parse_leaves_the_last_one(monkeypatch, kept, published, said):
    kept.parent.mkdir(parents=True)
    kept.write_text('{"chatgpt": {"prefixes": ["192.0.2.0/24"]}}')
    assert refresh(monkeypatch, published).startswith(said)
    assert kept.read_text() == '{"chatgpt": {"prefixes": ["192.0.2.0/24"]}}'
