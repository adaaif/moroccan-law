"""What search engines are given (the search-engines review, 9 Nov 2026): the crawlers known by their makers' addresses (IX10),
robots.txt (IX5, C4), the sitemaps in waves (IX4, IX13), IndexNow (IX14)."""
import json
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from unittest import mock

import pytest
from django.core.cache import cache
from django.core.management import call_command

from apps.corpus.models import Article, Text, Version
from apps.seo.services import crawlers, indexnow, sitemaps

pytestmark = pytest.mark.django_db
NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}


def test_a_crawler_is_known_by_its_makers_addresses():
    assert crawlers.crawler('66.249.66.1') == 'googlebot'
    assert crawlers.crawler('2001:4860:4801:10::5') == 'googlebot'
    assert crawlers.crawler('157.55.39.12') == 'bingbot'
    assert crawlers.crawler('203.0.113.9') == '' and crawlers.crawler('not an address') == ''


def test_a_verified_crawler_is_not_held_by_the_public_limit(api, settings):
    # Google renders a law's page with the answers a browser asks for, from a few addresses, all day.
    settings.PUBLIC_API_RATES = {'anonymous': '2/min', 'keyed': '2/min'}
    cache.clear()
    asked = [api.get('/api/corpus/shelf/', HTTP_CF_CONNECTING_IP='203.0.113.9', HTTP_X_FORWARDED_FOR='203.0.113.9').status_code
             for _ in range(3)]
    assert asked[-1] == 429
    google = [api.get('/api/corpus/shelf/', HTTP_CF_CONNECTING_IP='66.249.66.1', HTTP_X_FORWARDED_FOR='66.249.66.1').status_code
              for _ in range(3)]
    assert google == [200, 200, 200]


def test_robots_opens_the_law_and_closes_peoples_words(api, settings):
    settings.SITE_URL = 'https://3adala.com'
    txt = api.get('/robots.txt').content.decode()
    star = txt.split('# Crawlers that train')[0]
    assert 'User-agent: *\nAllow: /' in star
    for closed in ('/api/discussion/', '/api/explain/', '/api/media/', '/api/follows/', '/api/auth/', '/admin/', '/mcp',
                   '/api/measure/', '/pages/'):
        assert f'Disallow: {closed}\n' in star
    # The discussion's pages are crawlable, so their noindex is seen (nginx); the law's answers too, for rendering.
    assert 'Disallow: /discussion' not in txt and 'Disallow: /api/corpus' not in txt and 'Disallow: /api/\n' not in txt
    training = txt.split('# Crawlers that train')[1]
    for name in ('GPTBot', 'ClaudeBot', 'CCBot', 'Google-Extended', 'Applebot-Extended'):
        assert f'User-agent: {name}\n' in training
    assert 'Disallow: /\n' in training and 'OAI-SearchBot' not in txt and 'PerplexityBot' not in txt
    assert txt.rstrip().endswith('Sitemap: https://3adala.com/sitemap.xml')


@pytest.fixture
def corpus(tmp_path, settings):
    settings.SITE_URL = 'https://3adala.com'
    settings.SITEMAPS_DIR = str(tmp_path / 'sitemaps')
    settings.WEB_DIST = str(tmp_path / 'dist')
    (tmp_path / 'dist' / 'topics' / 'work').mkdir(parents=True)
    (tmp_path / 'dist' / 'topics' / 'work' / 'index.html').write_text('<html></html>')
    made = {}
    for uri, kind, n in [('/akn/ma/act/loi/65-99', 'law', 3), ('/akn/ma/act/decret/2-73-176', 'decree', 2),
                         ('/akn/ma/act/arrete/1455-26', 'order', 1), ('/akn/ma/act/dahir/1-58-250', 'dahir', 1)]:
        text = Text.objects.create(akn_uri=uri, type=kind, title_ar=uri)
        v = Version.objects.create(text=text, language='ar', valid_from=date(2020, 1, 1))
        for i in range(n):
            Article.objects.create(version=v, order=i, label=f'المادة {i + 1}', number=str(i + 1), eid=f'art_{i + 1}', body='نص.')
        made[kind] = text
    Text.objects.create(akn_uri='/akn/ma/act/loi/1-01', type='law', title_ar='نص لا نملك كلماته')   # no version: not listed
    return made


def urls(path) -> list[str]:
    return [u.text for u in ET.parse(path).getroot().findall('.//s:loc', NS)]


def test_the_sitemaps_name_every_address_and_open_in_waves(corpus, settings, tmp_path):
    done = sitemaps.write(today=date(2026, 11, 23))
    d = tmp_path / 'sitemaps'
    every = {u for f in (d / 'sitemaps').glob('*.xml') for u in urls(f)}
    site = 'https://3adala.com'
    assert {f'{site}/ma/loi/65-99', f'{site}/ma/loi/65-99/art_1', f'{site}/ma/decret/2-73-176/art_2',
            f'{site}/ma/arrete/1455-26', f'{site}/ma/dahir/1-58-250', f'{site}/', f'{site}/topics/work',
            f'{site}/words/nafaqa', f'{site}/open-source'} <= every
    # One article is its text's page; a text the site does not hold has no page to give.
    assert f'{site}/ma/arrete/1455-26/art_1' not in every and f'{site}/ma/loi/1-01' not in every
    assert all('/pages/' not in u and '/search' not in u for u in every)
    # Before the site opens, and on its first two weeks, the index lists the first wave alone.
    assert done['wave'] == 1
    listed = urls(d / 'sitemap.xml')
    assert f'{site}/sitemaps/laws-1.xml' in listed and f'{site}/sitemaps/decrees-1.xml' not in listed
    assert f'{site}/ma/decret/2-73-176' in urls(d / 'sitemaps' / 'decrees-1.xml')
    settings.INDEXING_OPENED = '2026-11-23'
    assert sitemaps.wave(date(2026, 12, 6)) == 1 and sitemaps.wave(date(2026, 12, 7)) == 2
    assert sitemaps.wave(date(2026, 12, 21)) == 3 and sitemaps.wave(date(2027, 6, 1)) == 3
    sitemaps.write(today=date(2026, 12, 21))
    listed = urls(d / 'sitemap.xml')
    assert f'{site}/sitemaps/decrees-1.xml' in listed and f'{site}/sitemaps/articles-1.xml' in listed
    settings.SITEMAP_WAVE = 2
    assert sitemaps.wave(date(2027, 6, 1)) == 2


def test_lastmod_is_the_day_the_text_changed(corpus, tmp_path):
    Text.objects.filter(pk=corpus['law'].pk).update(updated_at=datetime(2026, 7, 16, 10, tzinfo=UTC))
    sitemaps.write(today=date(2026, 11, 23))
    root = ET.parse(tmp_path / 'sitemaps' / 'sitemaps' / 'laws-1.xml').getroot()
    days = {u.find('s:loc', NS).text: getattr(u.find('s:lastmod', NS), 'text', None) for u in root.findall('s:url', NS)}
    assert days['https://3adala.com/ma/loi/65-99'] == '2026-07-16'
    assert 'priority' not in (tmp_path / 'sitemaps' / 'sitemaps' / 'laws-1.xml').read_text()


def test_the_sitemaps_ask_a_fixed_number_of_questions(corpus, django_assert_num_queries):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as few:
        sitemaps.entries()
    for i in range(30):
        text = Text.objects.create(akn_uri=f'/akn/ma/act/decret/2-26-{i}', type='decree', title_ar='م')
        v = Version.objects.create(text=text, language='ar', valid_from=date(2020, 1, 1))
        Article.objects.bulk_create([Article(version=v, order=j, label='م', number=str(j), eid=f'art_{j}', body='.')
                                     for j in range(3)])
    with django_assert_num_queries(len(few)):
        sitemaps.entries()


def test_the_sitemaps_are_served(api, corpus):
    call_command('write_sitemaps')
    r = api.get('/sitemap.xml')
    assert r.status_code == 200 and r['Content-Type'].startswith('application/xml')
    assert b'https://3adala.com/sitemaps/laws-1.xml' in b''.join(r.streaming_content)
    assert api.get('/sitemaps/laws-1.xml').status_code == 200
    assert api.get('/sitemaps/../settings.py').status_code == 404 and api.get('/sitemaps/nope-1.xml').status_code == 404


def test_indexnow_tells_nothing_while_the_site_is_closed(corpus, settings, tmp_path):
    with mock.patch('urllib.request.urlopen') as sent:
        assert indexnow.submit(['/ma/loi/65-99']) == 0
        call_command('indexnow')
    assert not sent.called and not (tmp_path / 'indexnow.json').exists()


def test_indexnow_tells_the_texts_that_changed(api, corpus, settings, tmp_path):
    settings.INDEXING = 'open'
    answer = mock.MagicMock(status=202)
    answer.__enter__.return_value = answer
    with mock.patch('urllib.request.urlopen', return_value=answer) as sent:
        call_command('indexnow')                       # the first run: the sitemaps carry the site
        assert not sent.called
        state = tmp_path / 'indexnow.json'
        since = datetime.fromisoformat(json.loads(state.read_text())['since'])
        Text.objects.filter(pk=corpus['decree'].pk).update(updated_at=since + timedelta(minutes=1))
        call_command('indexnow')
    body = json.loads(sent.call_args.args[0].data)
    assert body['host'] == '3adala.com' and body['keyLocation'] == 'https://3adala.com/indexnow.txt'
    assert set(body['urlList']) == {'https://3adala.com/ma/decret/2-73-176', 'https://3adala.com/ma/decret/2-73-176/art_1',
                                    'https://3adala.com/ma/decret/2-73-176/art_2'}
    assert api.get('/indexnow.txt').content.decode() == body['key'] == indexnow.key()


def test_only_the_search_engines_read_past_the_limits(api, settings):
    """OP17: the fetchers an assistant's user drives (ChatGPT's, Perplexity's) are anyone's to send."""
    assert crawlers.crawler('104.208.184.193') == '' and crawlers.crawler('18.97.43.80') == ''
    settings.PUBLIC_API_RATES = {'anonymous': '2/min', 'keyed': '2/min'}
    cache.clear()
    asked = [api.get('/api/corpus/shelf/', HTTP_CF_CONNECTING_IP='104.208.184.193',
                     HTTP_X_FORWARDED_FOR='104.208.184.193').status_code for _ in range(3)]
    assert asked[-1] == 429
    cache.clear()


def test_a_list_wider_than_a_crawler_is_given_is_never_read(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    kept = crawlers.kept_file()
    kept.parent.mkdir(parents=True)
    kept.write_text(json.dumps({'googlebot': {'prefixes': ['0.0.0.0/0', '66.249.66.0/27']},
                                'chatgpt-user': {'prefixes': ['203.0.113.0/24']}}))
    assert crawlers.crawler('203.0.113.9') == ''              # neither the whole internet nor a user's fetcher
    assert crawlers.crawler('66.249.66.1') == 'googlebot'


def test_refresh_refuses_a_list_that_names_too_wide_a_network(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    lists = {url: [('2026-11-12', ['66.249.66.0/27'])] for url in crawlers.SOURCES.values()}
    lists[crawlers.SOURCES['bingbot']] = [('2026-11-12', ['40.0.0.0/8'])]

    def fetch(url):
        as_of, prefixes = lists[url][0]
        from apps.seo.management.commands import refresh_crawlers
        return refresh_crawlers.checked(as_of, prefixes)
    with mock.patch('apps.seo.management.commands.refresh_crawlers.fetch', side_effect=fetch):
        call_command('refresh_crawlers')
    written = json.loads(crawlers.kept_file().read_text())
    assert written['googlebot']['prefixes'] == ['66.249.66.0/27']
    assert written['bingbot']['prefixes'] != ['40.0.0.0/8']        # the last good copy stays
    assert set(written) == set(crawlers.SOURCES)


def test_security_txt_names_where_to_report_a_flaw(client, settings):
    settings.SITE_URL = 'https://3adala.com'
    settings.CONTACT_EMAIL = ''
    assert client.get('/.well-known/security.txt').status_code == 404       # no address, no file
    settings.CONTACT_EMAIL = 'contact@3adala.com'
    r = client.get('/.well-known/security.txt')
    assert r.status_code == 200 and r['Content-Type'] == 'text/plain; charset=utf-8'
    fields = dict(line.split(': ', 1) for line in r.content.decode().splitlines())
    assert fields['Contact'] == 'mailto:contact@3adala.com'
    assert fields['Canonical'] == 'https://3adala.com/.well-known/security.txt'
    expires = datetime.strptime(fields['Expires'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)
    now = datetime.now(UTC)
    assert now + timedelta(days=362) < expires < now + timedelta(days=365)  # under a year, as RFC 9116 asks


def test_security_txt_is_read_while_the_gate_is_closed(client, settings):
    settings.CONTACT_EMAIL = 'contact@3adala.com'
    settings.GATE_PASSWORD = 'closed'
    assert client.get('/.well-known/security.txt').status_code == 200
