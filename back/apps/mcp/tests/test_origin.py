"""Where a call comes from without an account: an assistant's platform by its published ranges, or an address."""
import json

from apps.mcp.services import origin


def test_the_platforms_are_known_by_their_published_ranges(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path                    # no nightly copy: the bundled list
    assert origin.platform('160.79.104.9') == 'claude' and origin.platform('160.79.111.255') == 'claude'
    first = json.loads(origin.BUNDLED.read_text())['chatgpt']['prefixes'][0]
    assert origin.platform(first.split('/')[0]) == 'chatgpt'
    assert origin.platform('8.8.8.8') == '' and origin.platform('not an address') == ''


def test_the_nightly_copy_replaces_the_bundled_list(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    (tmp_path / 'mcp').mkdir()
    (tmp_path / 'mcp' / 'platforms.json').write_text(json.dumps({'chatgpt': {'prefixes': ['198.51.100.0/24']}}))
    assert origin.platform('198.51.100.7') == 'chatgpt' and origin.platform('160.79.104.9') == ''


def test_an_ipv6_caller_counts_by_its_64_and_a_client_by_its_name():
    assert origin.bucket('2001:db8:1:2:3:4:5:6') == '2001:db8:1:2::/64'
    assert origin.bucket('203.0.113.9') == '203.0.113.9'
    assert origin.client_name('python-httpx/0.28.1') == 'python-httpx' and origin.client_name('') == 'unknown'
