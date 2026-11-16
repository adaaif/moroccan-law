"""The fetchers ask other sites under the project's own name, read each host's robots.txt once and obey it, wait when
asked to, and stop on a refusal. No test here reaches a real site: a fake opener stands for the network."""
import io
import json
import urllib.error
from datetime import date
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.sources.services import fetch

APPS = Path(__file__).resolve().parents[2]


class Site:
    """The network as a dict: url → bytes, or an HTTP status to answer with (and its headers)."""

    def __init__(self, pages: dict):
        self.pages, self.asked = pages, []

    def open(self, request, timeout=None):
        url = request.full_url
        self.asked.append((url, dict(request.header_items())))
        answer = self.pages.get(url, 404)
        if callable(answer):
            answer = answer()
        if isinstance(answer, tuple):
            status, headers = answer
            raise urllib.error.HTTPError(url, status, 'refused', headers, None)
        if isinstance(answer, int):
            raise urllib.error.HTTPError(url, answer, 'refused', {}, None)
        return io.BytesIO(answer)

    def urls(self):
        return [u for u, _ in self.asked]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test here reaches a real site, whatever state the code is in: an opener the fake site did not replace fails."""
    def refuse(*handlers):
        raise AssertionError('a test reached for the network')
    monkeypatch.setattr(fetch.urllib.request, 'build_opener', refuse)
    monkeypatch.setattr(fetch.urllib.request, 'urlopen', refuse)


@pytest.fixture
def site(monkeypatch):
    fetch._ROBOTS.clear()
    fetch._LAST.clear()
    slept = []
    monkeypatch.setattr(fetch.time, 'sleep', slept.append)
    holder = Site({})
    holder.slept = slept
    monkeypatch.setattr(fetch.urllib.request, 'build_opener', lambda *handlers: holder)
    yield holder
    fetch._ROBOTS.clear()
    fetch._LAST.clear()


def test_no_fetcher_gives_a_browser_s_name():
    sources = [p for p in APPS.rglob('*.py') if '/tests/' not in str(p)]
    named = [str(p.relative_to(APPS)) for p in sources if 'Mozilla' in p.read_text(encoding='utf-8')]
    assert named == []
    queue = APPS.parent / 'scripts_run_queue.sh'       # the private repository's run queue; not in the public tree
    assert not queue.exists() or 'Mozilla' not in queue.read_text()


def test_every_request_carries_the_project_s_name_from_the_settings(site, settings):
    settings.FETCH_USER_AGENT = 'example/1 (+https://example.test/about)'
    site.pages = {'https://www.sgg.gov.ma/robots.txt': b'User-agent: *\nDisallow:\n',
                  'https://www.sgg.gov.ma/BO/a.pdf': b'%PDF-1.4'}
    assert fetch.get('https://www.sgg.gov.ma/BO/a.pdf') == b'%PDF-1.4'
    assert [h['User-agent'] for _, h in site.asked] == ['example/1 (+https://example.test/about)'] * 2


def test_robots_txt_is_read_once_a_host_and_obeyed(site):
    site.pages = {'https://www.sgg.gov.ma/robots.txt': b'User-agent: *\nDisallow: /DesktopModules/\n',
                  'https://www.sgg.gov.ma/BO/a.pdf': b'%PDF a', 'https://www.sgg.gov.ma/BO/b.pdf': b'%PDF b',
                  'https://www.sgg.gov.ma/DesktopModules/MVC/x': b'[]'}
    assert fetch.get('https://www.sgg.gov.ma/BO/a.pdf') == b'%PDF a'
    assert fetch.get('https://www.sgg.gov.ma/BO/b.pdf') == b'%PDF b'
    with pytest.raises(fetch.Refused, match=r'robots\.txt'):
        fetch.get('https://www.sgg.gov.ma/DesktopModules/MVC/x')
    assert site.urls() == ['https://www.sgg.gov.ma/robots.txt', 'https://www.sgg.gov.ma/BO/a.pdf',
                           'https://www.sgg.gov.ma/BO/b.pdf']


def test_a_rule_for_our_fetcher_by_name_is_obeyed(site, settings):
    settings.FETCH_USER_AGENT = 'example/1 (+https://example.test/about)'
    site.pages = {'https://adala.justice.gov.ma/robots.txt': b'User-agent: example\nDisallow: /\n\nUser-agent: *\nAllow: /\n'}
    with pytest.raises(fetch.Refused):
        fetch.get('https://adala.justice.gov.ma/api/uploads/a.pdf')


def test_no_robots_txt_allows_everything_and_one_that_cannot_be_read_allows_nothing(site):
    site.pages = {'https://www.sgg.gov.ma/a.pdf': b'%PDF', 'https://adala.justice.gov.ma/robots.txt': 503,
                  'https://www.chambredesrepresentants.ma/robots.txt': 403}
    assert fetch.get('https://www.sgg.gov.ma/a.pdf') == b'%PDF'           # robots.txt answers 404
    with pytest.raises(fetch.Refused, match='could not be read'):
        fetch.get('https://adala.justice.gov.ma/a.pdf')
    with pytest.raises(fetch.Refused, match='refuses'):
        fetch.get('https://www.chambredesrepresentants.ma/a.pdf')
    assert 'https://adala.justice.gov.ma/a.pdf' not in site.urls()


def test_a_site_that_asks_us_to_wait_is_waited_for_a_bounded_time(site):
    answers = iter([(429, {'Retry-After': '7'}), (503, {}), b'%PDF late'])
    site.pages = {'https://www.sgg.gov.ma/a.pdf': lambda: next(answers)}
    assert fetch.get('https://www.sgg.gov.ma/a.pdf') == b'%PDF late'
    assert site.slept == [7.0, fetch.WAIT_DEFAULT]


def test_a_wait_longer_than_a_run_s_patience_or_a_third_429_stops_the_run(site):
    site.pages = {'https://www.sgg.gov.ma/a.pdf': (429, {'Retry-After': '3600'}),
                  'https://www.sgg.gov.ma/b.pdf': (429, {'Retry-After': '2'})}
    with pytest.raises(fetch.Refused, match='wait'):
        fetch.get('https://www.sgg.gov.ma/a.pdf')
    assert site.slept == []
    with pytest.raises(fetch.Refused, match='wait'):
        fetch.get('https://www.sgg.gov.ma/b.pdf')
    assert site.slept == [2.0, 2.0]
    assert site.urls().count('https://www.sgg.gov.ma/b.pdf') == fetch.TRIES


def test_a_refusal_stops_and_is_never_an_error_a_fetcher_passes(site):
    site.pages = {'https://www.sgg.gov.ma/a.pdf': 403}
    with pytest.raises(fetch.Refused, match='refused'):
        fetch.get('https://www.sgg.gov.ma/a.pdf')
    assert not issubclass(fetch.Refused, (OSError, ValueError))     # the fetchers pass those, one file at a time


def test_a_crawl_delay_longer_than_the_fetchers_pause_is_waited(site, monkeypatch):
    clock = iter([100.0, 101.0, 101.0])
    monkeypatch.setattr(fetch.time, 'monotonic', lambda: next(clock))
    site.pages = {'https://www.sgg.gov.ma/robots.txt': b'User-agent: *\nCrawl-delay: 10\n',
                  'https://www.sgg.gov.ma/a.pdf': b'%PDF', 'https://www.sgg.gov.ma/b.pdf': b'%PDF'}
    fetch.get('https://www.sgg.gov.ma/a.pdf')
    fetch.get('https://www.sgg.gov.ma/b.pdf')
    assert site.slept == [9.0]


# ── the commands list by default and fetch with --fetch ─────────────────────────────────────────────────────────────

def sgg_row(number: str, day: str, edition: str = 'AR') -> dict:
    ms = int((date.fromisoformat(day) - date(1970, 1, 1)).days * 86_400_000)
    return {'BoNum': number, 'BoDate': f'/Date({ms})/',
            'BoUrl': f'https://www.sgg.gov.ma/BO/{edition}/{day[:4]}/BO_{number}_{edition}.pdf'}


ENDPOINT = 'https://www.sgg.gov.ma/DesktopModules/MVC/TableListBO/BO/AjaxMethod'
TOKEN_PAGE = b'<input name="__RequestVerificationToken" type="hidden" value="tok" />'


def test_fetch_bo_french_lists_by_default_and_fetches_with_fetch(site, settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    rows = [sgg_row('7400', '2025-01-02', 'FR')]
    site.pages = {'https://www.sgg.gov.ma/BulletinOfficiel.aspx': TOKEN_PAGE, ENDPOINT: json.dumps(rows).encode(),
                  rows[0]['BoUrl']: b'%PDF-1.7 fr'}
    call_command('fetch_bo_french', stdout=io.StringIO())
    assert rows[0]['BoUrl'] not in site.urls()
    assert not (tmp_path / 'issues' / 'bo_fr' / 'BO_7400_fr.pdf').exists()
    # The list is asked as the page's own script asks it: the page's token, under our name.
    _, headers = next(a for a in site.asked if a[0] == ENDPOINT)
    assert headers['Requestverificationtoken'] == 'tok' and headers['User-agent'] == settings.FETCH_USER_AGENT
    call_command('fetch_bo_french', '--fetch', '--pause', '0', stdout=io.StringIO())
    assert (tmp_path / 'issues' / 'bo_fr' / 'BO_7400_fr.pdf').read_bytes() == b'%PDF-1.7 fr'


def test_a_robots_txt_that_closes_the_list_stops_the_command_with_its_reason(site, settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    site.pages = {'https://www.sgg.gov.ma/robots.txt': b'User-agent: *\nDisallow: /DesktopModules/\n',
                  'https://www.sgg.gov.ma/BulletinOfficiel.aspx': TOKEN_PAGE}
    with pytest.raises(CommandError, match=r'robots\.txt'):
        call_command('fetch_bo_french', stdout=io.StringIO())
    assert ENDPOINT not in site.urls()


@pytest.mark.django_db
def test_fetch_new_issues_lists_by_default(site, settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    rows = [sgg_row('7600', '2026-11-02')]
    site.pages = {'https://www.sgg.gov.ma/arabe/BulletinOfficiel.aspx': TOKEN_PAGE, ENDPOINT: json.dumps(rows).encode(),
                  rows[0]['BoUrl']: b'%PDF ar'}
    out = io.StringIO()
    call_command('fetch_new_issues', stdout=out)
    assert '7600' in out.getvalue()
    assert rows[0]['BoUrl'] not in site.urls()
    assert not (tmp_path / 'issues' / 'bo_ar').exists()


@pytest.mark.django_db
def test_fetch_conventions_kept_asks_the_sgg_nothing(site, settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    (tmp_path / 'sources' / 'sgg_bo').mkdir(parents=True)
    (tmp_path / 'sources' / 'sgg_bo' / 'index_ar_3110_2026-11-01T000000Z.json').write_text(
        json.dumps([sgg_row('12', '2026-10-01')]))
    call_command('fetch_conventions', '--kept', stdout=io.StringIO())
    assert site.asked == []


def test_the_kept_list_is_offered_as_what_it_is_never_as_a_way_round_a_refusal():
    from apps.sources.management.commands.fetch_conventions import Command
    parser = Command().create_parser('manage.py', 'fetch_conventions')
    kept = next(a for a in parser._actions if '--kept' in a.option_strings)
    assert 'refuse' not in kept.help and 'elsewhere' not in kept.help


@pytest.mark.django_db
def test_fetch_sgg_consolidated_lists_by_default_and_registers_nothing(site, settings, tmp_path):
    from apps.sources.models import Document
    settings.CORPUS_DIR = tmp_path
    page = b'<a href="https://www.sgg.gov.ma/arabe/textesconsolides/2_00.pdf">2.00</a>'
    site.pages = {'https://www.sgg.gov.ma/arabe/textesconsolides.aspx': page,
                  'https://www.sgg.gov.ma/arabe/textesconsolides/2_00.pdf': b'%PDF-1.4'}
    out = io.StringIO()
    call_command('fetch_sgg_consolidated', stdout=out)
    assert 'to fetch' in out.getvalue()
    assert site.urls() == ['https://www.sgg.gov.ma/robots.txt', 'https://www.sgg.gov.ma/arabe/textesconsolides.aspx']
    assert not Document.objects.exists()


@pytest.mark.django_db
def test_fetch_bills_without_fetch_asks_the_chamber_nothing(site):
    call_command('fetch_bills', stdout=io.StringIO())
    assert site.asked == []


def test_fetch_adala_without_fetch_says_what_it_would_fetch(site, settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    out = io.StringIO()
    call_command('fetch_adala', 'https://adala.justice.gov.ma/api/uploads/a.pdf', '--name', 'a', stdout=out)
    assert 'would fetch' in out.getvalue() and site.asked == []


@pytest.mark.django_db
def test_fetch_new_issues_fetch_without_write_keeps_the_file_and_reads_nothing(site, settings, tmp_path, monkeypatch):
    from apps.sources.management.commands import fetch_new_issues
    monkeypatch.setattr(fetch_new_issues, 'call_command', lambda *a, **k: pytest.fail('read without --write'))
    monkeypatch.setattr(fetch_new_issues.time, 'sleep', lambda s: None)
    settings.CORPUS_DIR = tmp_path
    rows = [sgg_row('7600', '2026-11-02')]
    site.pages = {'https://www.sgg.gov.ma/arabe/BulletinOfficiel.aspx': TOKEN_PAGE, ENDPOINT: json.dumps(rows).encode(),
                  rows[0]['BoUrl']: b'%PDF ar'}
    out = io.StringIO()
    call_command('fetch_new_issues', '--fetch', stdout=out)
    assert (tmp_path / 'issues' / 'bo_ar' / 'BO_7600_ar.pdf').read_bytes() == b'%PDF ar'
    assert '--write reads it' in out.getvalue()


# ── one list of hosts for every fetcher, and names that stay in their folder ────────────────────────────────────────

@pytest.mark.parametrize('url', ['http://www.sgg.gov.ma/BO/a.pdf', 'https://127.0.0.1/a.pdf', 'file:///etc/passwd',
                                 'https://www.sgg.gov.ma.example.test/a.pdf', 'https://user@www.sgg.gov.ma/a.pdf',
                                 'https://www.sgg.gov.ma:8443/a.pdf', '/BO/a.pdf'])
def test_an_address_off_the_list_of_hosts_is_never_asked(site, url):
    with pytest.raises(fetch.Outside):
        fetch.get(url)
    assert site.asked == []
    assert issubclass(fetch.Outside, ValueError)        # one bad address in a list is passed, the run goes on


def test_the_hosts_the_fetchers_ask_are_on_the_list():
    for url in ['https://www.sgg.gov.ma/BO/a.pdf', 'https://adala.justice.gov.ma/api/uploads/a.pdf',
                'https://www.chambredesrepresentants.ma/ar/DossierPLF2027', 'https://www.hespress.com/feed']:
        assert fetch.check(url) == url


def test_a_redirect_off_the_list_or_closed_by_robots_txt_is_not_followed(site):
    import urllib.request
    site.pages = {'https://adala.justice.gov.ma/robots.txt': b'User-agent: *\nDisallow: /private/\n'}
    request = urllib.request.Request('https://www.sgg.gov.ma/a.pdf')
    with pytest.raises(fetch.Outside):
        fetch._Redirects().redirect_request(request, None, 302, 'Found', {}, 'https://elsewhere.example/a.pdf')
    with pytest.raises(fetch.Refused):
        fetch._Redirects().redirect_request(request, None, 302, 'Found', {}, 'https://adala.justice.gov.ma/private/a')
    assert fetch._Redirects().redirect_request(request, None, 302, 'Found', {}, 'https://adala.justice.gov.ma/a.pdf')


@pytest.mark.parametrize('name', ['../../adala/x.pdf', '/home/x.pdf', '..', '.hidden.pdf', 'a/b.pdf', 'a\\b.pdf', ''])
def test_a_name_from_a_link_is_kept_only_as_a_plain_file_name(name):
    with pytest.raises(fetch.Outside):
        fetch.safe_name(name)
    assert fetch.safe_name('01-Projet_loi_de_Finances_2027_Ar.pdf') == '01-Projet_loi_de_Finances_2027_Ar.pdf'


def test_the_finance_bill_s_watcher_keeps_no_file_outside_its_folder(tmp_path, settings, monkeypatch):
    from apps.budget.management.commands import watch_finance_bill as watch
    settings.CORPUS_DIR = tmp_path
    page = ('<a href="/sites/default/files/..%2F..%2Fadala%2Fx.pdf">مشروع</a>'
            '<a href="https://elsewhere.example/y.pdf">ملحق</a>'
            '<a href="/sites/default/files/02-note.pdf">مذكرة</a>').encode()

    def get(url):
        if 'elsewhere' in url:
            raise fetch.Outside(url)
        return page if 'Dossier' in url else b'<rss></rss>' if url.endswith('rss') else b'%PDF-1.7'
    monkeypatch.setattr(watch, 'get', get)
    monkeypatch.setattr(watch.time, 'sleep', lambda s: None)
    out = io.StringIO()
    call_command('watch_finance_bill', '--year', '2027', '--fetch', stdout=out)
    assert 'not a plain file name' in out.getvalue()
    assert not (tmp_path / 'sources' / 'adala').exists()
    kept = sorted(p.name for p in (tmp_path / 'sources' / 'parliament' / 'plf2027').iterdir())
    assert '02-note.pdf' in kept and not any('x.pdf' in k or 'y.pdf' in k for k in kept)


def test_fetch_adala_keeps_its_file_and_its_kept_files_under_the_corpus(site, settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    with pytest.raises(CommandError, match='plain file name'):
        call_command('fetch_adala', 'https://adala.justice.gov.ma/api/uploads/a.pdf', '--name', '../../x', '--fetch')
    with pytest.raises(CommandError, match='under CORPUS_DIR'):
        call_command('fetch_adala', 'https://adala.justice.gov.ma/api/uploads/a.pdf', '--kept', '../../etc/x.pdf')
    assert site.asked == []


@pytest.mark.django_db
def test_an_issue_no_night_can_read_is_said_and_the_issues_after_it_are_read(site, settings, tmp_path, monkeypatch):
    from decimal import Decimal

    from apps.sources.management.commands import fetch_new_issues
    from apps.sources.services import ocr
    monkeypatch.setattr(ocr.guard, '_SPENDING', False)
    monkeypatch.setattr(fetch_new_issues, 'index_texts', lambda keys: 0)
    monkeypatch.setattr(fetch_new_issues.time, 'sleep', lambda s: None)
    settings.CORPUS_DIR = tmp_path
    rows = [sgg_row('7600', '2026-11-02'), sgg_row('7601', '2026-11-05'), sgg_row('7602', '2026-11-09')]
    site.pages = {'https://www.sgg.gov.ma/arabe/BulletinOfficiel.aspx': TOKEN_PAGE, ENDPOINT: json.dumps(rows).encode(),
                  **{r['BoUrl']: b'%PDF ar' for r in rows}}
    read = []

    def process_issue(name, key, **kw):
        read.append(key)
        if key == '7600':
            raise ocr.OverBudget('texts:7600: worst case $3.10', Decimal('3.10'))
        if key == '7602':
            raise ocr.OverBudget('page 4: worst case $0.0068', Decimal('0.0068'))
    monkeypatch.setattr(fetch_new_issues, 'call_command', process_issue)
    out, err = io.StringIO(), io.StringIO()
    call_command('fetch_new_issues', '--fetch', '--write', '--per-run', '1', stdout=out, stderr=err)
    assert read == ['7600', '7601', '7602']
    assert 'needs a higher --per-run' in err.getvalue() and 'read on from there' in out.getvalue()
    state = json.loads((tmp_path / 'reports' / 'fetch_new_issues.json').read_text())
    assert set(state['finished']) == {'7601'} and state['too_big'] == {'7600': '3.10'}


def test_without_a_name_of_its_own_nothing_is_asked(site, settings):
    """FETCH_USER_AGENT has no default: a copy of this code that never set it would otherwise speak under the name of
    the site it was copied from, and that site would answer for it."""
    settings.FETCH_USER_AGENT = '  '
    site.pages = {'https://www.sgg.gov.ma/robots.txt': b'User-agent: *\nDisallow:\n'}
    with pytest.raises(fetch.Unnamed, match='FETCH_USER_AGENT is empty'):
        fetch.get('https://www.sgg.gov.ma/BO/a.pdf')
    assert site.asked == []
    assert issubclass(fetch.Unnamed, fetch.Refused)      # every fetcher stops on it, as on a refusal


@pytest.mark.parametrize('command, args', [
    ('fetch_new_issues', []),
    ('fetch_bo_french', []),
    ('fetch_sgg_consolidated', []),
    ('fetch_adala', ['https://adala.justice.gov.ma/api/uploads/a.pdf', '--name', 'a', '--fetch']),
    ('watch_finance_bill', ['--year', '2027', '--press']),
    ('refresh_crawlers', []),
    ('refresh_platforms', []),
    ('fetch_geoip', []),
])
def test_every_fetcher_refuses_to_start_without_a_name(site, settings, tmp_path, monkeypatch, command, args):
    settings.FETCH_USER_AGENT = ''
    settings.CORPUS_DIR = tmp_path
    settings.GEOIP_DIR = tmp_path / 'geo'
    with pytest.raises(CommandError, match='FETCH_USER_AGENT is empty'):
        call_command(command, *args, stdout=io.StringIO(), stderr=io.StringIO())
    assert site.asked == []


def _deploy_errors():
    from django.core.checks import run_checks
    return [e for e in run_checks(include_deployment_checks=True) if e.id == 'sources.E001']


@pytest.mark.django_db
def test_a_deploy_refuses_a_server_whose_fetchers_have_no_name(settings):
    settings.FETCH_USER_AGENT = 'example/1 (+https://example.org/about)'
    assert _deploy_errors() == []
    settings.FETCH_USER_AGENT = ''
    [error] = _deploy_errors()
    assert error.level >= 40 and 'FETCH_USER_AGENT' in error.msg
