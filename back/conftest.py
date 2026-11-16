import json
import os
import re
import shutil
import traceback
from datetime import date, timedelta
from urllib.parse import quote

import pytest
from PIL import features
from rest_framework.test import APIClient

pytest_plugins = ('config.queryloops',)     # `--query-loops`: the SQL a line of the code repeats in a test

# What some tests need from the system beside the Python packages; back/requirements/apt.txt names the packages.
# A test says so with `@pytest.mark.needs('ffmpeg')`, one name or several. On a developer's machine without one, the
# test is skipped and says what is missing. CI installs them all, so under CI=true (GitHub and most services set it) a
# missing one stops the run before its first test: a green run there never hides a check that did not run.
NEEDS = {
    'ffmpeg': lambda: shutil.which('ffmpeg') is not None,
    'tesseract': lambda: shutil.which('tesseract') is not None,
    'fribidi': lambda: features.check('raqm'),      # Pillow shapes Arabic only where it could load FriBiDi
}


def _missing() -> set[str]:
    return {name for name, there in NEEDS.items() if not there()}


def pytest_sessionstart(session):
    missing = _missing()
    if missing and os.environ.get('CI') == 'true' and not hasattr(session.config, 'workerinput'):
        pytest.exit(f'CI lacks {", ".join(sorted(missing))}: install the packages of back/requirements/apt.txt '
                    'before the tests', returncode=1)


def pytest_collection_modifyitems(items):
    missing = _missing()
    for item in items:
        asked = {name for mark in item.iter_markers('needs') for name in mark.args}
        if asked - NEEDS.keys():
            raise pytest.UsageError(f'{item.nodeid}: needs({", ".join(sorted(asked - NEEDS.keys()))}) is not one of '
                                    f'{", ".join(NEEDS)} (back/conftest.py)')
        if asked & missing:
            item.add_marker(pytest.mark.skip(
                reason=f'{", ".join(sorted(asked & missing))} not installed (back/requirements/apt.txt)'))


@pytest.fixture(scope='session', autouse=True)
def own_corpus_dir(tmp_path_factory):
    """The suite's own corpus folder. CORPUS_DIR, and every folder worked out from it when the settings were read
    (the places' databases, the open data, the sitemaps; the ledger and the kept lists live under it), point into a
    temporary folder for the whole session, and so do the readers' uploads: no test reads or writes the real data/ (a
    test that forgot to point it elsewhere once wrote there), and the suite runs on a machine with no data/ at all. A
    test that needs a file writes its own, there or under tmp_path."""
    from django.test import override_settings

    root = tmp_path_factory.mktemp('corpus')
    with override_settings(CORPUS_DIR=root, UPLOADS_DIR=root / 'uploads', GEOIP_DIR=str(root / 'geo'),
                           OPEN_DATA_DIR=str(root / 'open'), SITEMAPS_DIR=str(root / 'seo' / 'sitemaps')):
        yield root


@pytest.fixture(autouse=True)
def settings_as_they_were():
    """Each test ends with the settings it began with. A test that sets a value through pytest-django's `settings` while
    an @override_settings decorator is on ends the two out of order, and the decorator's values (a proxy count, a
    model allow-list, a reading budget) stayed for the next tests in the worker. Set up before every other fixture of a
    test, this one is torn down after them all and puts back what changed, with the signal Django sends for each."""
    from django.conf import settings
    from django.test.signals import setting_changed

    before = settings._wrapped
    yield
    after = settings._wrapped
    if after is before:
        return
    settings._wrapped = before
    for name in (n for n in dir(after) if n.isupper()):
        if getattr(after, name, None) is not getattr(before, name, None):
            setting_changed.send(sender=type(before), setting=name, value=getattr(before, name, None), enter=False)


@pytest.fixture(autouse=True)
def clear_caches():
    """Each test starts with empty caches: a value one test kept (for minutes, as the discussion's liveness) never
    changes what the next test in the same worker sees."""
    yield
    from django.core.cache import caches
    for cache in caches.all():
        cache.clear()


@pytest.fixture
def api():
    return APIClient()


# ── malformed requests (OP53 of the open-source audit) ─────────────────────────────────────────────────────────────
#
# Each app's tests hold one test taking `knock` and `malformed`: every address of the app, every method its view takes,
# signed in as staff and not, is sent each malformed shape, and none may answer 500. A new view that reads a list as
# words, a word as a number, or puts a NUL into a query is caught there.

# Every name the API reads from a query or a body, so each shape reaches each view's fields.
NAMES = ('page', 'path', 'q', 'from', 'to', 'count', 'window', 'on', 'year', 'month', 'day', 'after', 'since', 'kind',
         'text', 'item', 'place', 'sort', 'period', 'around', 'r', 'token', 't', 'scope', 'code', 'body', 'title', 'ms',
         'rank', 'log', 'seconds', 'event', 'refs', 'by', 'citations', 'paths', 'details', 'contact', 'username',
         'password', 'email', 'login', 'note', 'days', 'locked', 'act', 'rule', 'register', 'answer', 'w', 'label', 'id',
         'parent', 'voice', 'pictures', 'peaks', 'insist', 'reason', 'message', 'quote', 'about', 'lang', 'outcome',
         'places', 'text_paths', 'everywhere', 'client_id', 'grant_type', 'redirect_uri', 'refresh_token',
         'redirect_uris', 'response_type', 'code_challenge', 'code_challenge_method', 'state', 'resource', 'named', 'g',
         'type', 'repealed', 'any', 'headline', 'sources', 'consent', 'tab', 'helped', 'check', 'uid', 'new_password',
         'email_confirmed', 'refresh', 'credential', 'nonce', 'revision', 'contribution', 'pause', 'of', 'spans',
         'moment_ms', 'shape', 'with', 'article', 'text_kind', 'text_number', 'issue', 'nav', 'width', 'lcp', 'says',
         'not')

# A shape: where it goes ('query' for every method, 'body' for those that take one, 'address' into the path's own
# words) and what it is. A body shape is raw JSON or a value given to every name.
MALFORMED = {
    'a JSON list for the body': ('body', '[{"path": "/talk/housing"}]'),
    'a JSON string for the body': ('body', '"x"'),
    'a JSON null for the body': ('body', 'null'),
    'JSON nested past what Python reads': ('body', '[' * 5000),
    'a body that is not JSON': ('body', '{"path": 1'),
    'a NUL in every field': ('body', {'value': 'a\x00b'}),
    'half a UTF-16 pair in every field': ('body', {'raw': '{' + ', '.join(f'"{n}": "\\ud800"' for n in NAMES) + '}'}),
    'a list in every field': ('body', {'value': ['a']}),
    'an object in every field': ('body', {'value': {'a': 1}}),
    'a number past any column in every field': ('body', {'value': 10**40}),
    'true in every field': ('body', {'value': True}),
    'other digits in every field': ('body', {'value': '²'}),
    'an impossible date in every field': ('body', {'value': '2024-99-99'}),
    'an over-long string in every field': ('body', {'value': 'x' * 5000}),
    'a broken link in every field': ('body', {'value': 'https://['}),
    'a NUL in the query': ('query', '\x00'),
    'other digits in the query': ('query', '²'),
    'an impossible date in the query': ('query', '2024-99-99'),
    'a number past any column in the query': ('query', '9' * 40),
    'an over-long query': ('query', 'x' * 3000),
    'a broken link in the query': ('query', 'https://['),
    'a NUL in the address': ('address', 'a\x00b'),
    'a number past any column in the address': ('address', '9' * 40),
}


# Answered by ParadeDB's index alone: in SQLite (the suite's database unless TEST_DATABASE_URL is set) it cannot run.
NEEDS_PARADEDB = {'api/search/'}


def pytest_generate_tests(metafunc):
    if 'malformed' in metafunc.fixturenames:
        metafunc.parametrize('malformed', list(MALFORMED), ids=list(MALFORMED))


def _routes(patterns, prefix=''):
    from django.urls import URLResolver
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _routes(p.url_patterns, prefix + str(p.pattern))
        else:
            yield prefix + str(p.pattern), p.callback


# The words each kind of path part is given: the world's rows (its first post, text, issue and topic).
_PARTS = {'edition': 'general_ar', 'key': '6208', 'username': 'nadia', 'verb': 'apply', 'size': 'full', 'kind': 'doors',
          'slug': 'housing', 'name': 'x', 'address': 'ma/loi/2013/67-12'}
_CONVERTED = {'int': '1', 'uuid': '00000000-0000-0000-0000-000000000001', 'path': 'ma/loi/2013/67-12'}


def _fill(route: str, odd: str | None) -> str | None:
    """The route with its parts filled; `odd` in place of each part a reader types (None when the route has none)."""
    route = route.lstrip('^').rstrip('$')
    route = re.sub(r'\(\?P<edition>[^)]*\)', '<str:edition>', route)
    route = re.sub(r'\(\?P<key>\[0-9\]\+\(\?:-\[a-z\]\+\)\?\)', '<str:key>', route)
    seen = []

    def part(m):
        kind, name = m.group(1) or 'str', m.group(2)
        if odd is not None and kind in ('str', 'path', 'int') and (kind != 'int' or odd.isdigit()):
            seen.append(name)
            return quote(odd, safe='')
        return _CONVERTED.get(kind) or _PARTS.get(name, 'x')
    url = '/' + re.sub(r'<(?:(\w+):)?(\w+)>', part, route)
    return None if odd is not None and not seen else url


@pytest.fixture
def knock(db, settings, tmp_path, monkeypatch):
    """`knock(app, shape)`: every address of `apps.<app>` sent the malformed shape; what answered 500, as lines."""
    from django.db import connection
    from django.urls import get_resolver
    from django.utils import timezone
    from rest_framework.views import APIView

    from apps.accounts.models import User
    from apps.corpus.models import Article, Consolidation, Text, Version
    from apps.discussion.models import Contribution, Discussion
    from apps.sources.models import Document, Edition, Issue

    (tmp_path / 'index.html').write_text('<!doctype html><html><head><title>قانون</title></head><body></body></html>')
    settings.WEB_DIST, settings.UPLOADS_DIR, settings.READING_BUDGET = str(tmp_path), tmp_path / 'uploads', 0
    monkeypatch.setattr(APIView, 'check_throttles', lambda self, request: None)
    people = {}
    for name, staff in (('nadia', False), ('hamid', False), ('boss', True)):
        people[name] = User.objects.create_user(username=name, email=f'{name}@example.ma', password='a long secret 2026',
                                                is_staff=staff, is_superuser=staff)
        people[name].date_joined = people[name].email_proven_at = timezone.now() - timedelta(days=30)
        people[name].save()
    place = Discussion.objects.create(path='/talk/housing', text_path='/talk/housing')
    post = Contribution.objects.create(discussion=place, author=people['nadia'], kind='question',
                                       title='سؤال عن الكراء الطويل', body='نص')
    Contribution.objects.create(discussion=place, author=people['hamid'], kind='comment', parent=post, body='رد')
    document = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='6208'.ljust(64, '0'),
                                       path='BO_6208_ar.pdf', mime='application/pdf', language='ar', bytes=1,
                                       fetched_at=timezone.now())
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=6208, date=date(2013, 11, 28), document=document)
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/2013/67-12', type='law', number='67-12',
                               number_as_printed='67.12', title_ar='القانون رقم 67.12', first_published_in=issue)
    version = Version.objects.create(text=text, language='ar', valid_from=date(2013, 11, 28),
                                     consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=version, order=1, label='المادة 34', number='34', eid='art_34', body='نص المادة',
                           printed_page=10)
    anonymous, staff = APIClient(), APIClient()
    staff.force_authenticate(people['boss'])

    def send(client, method, url, where, what):
        if where == 'query':
            url += '?' + '&'.join(f'{n}={quote(what, safe="")}' for n in NAMES)
        if method == 'get' or where != 'body':
            return getattr(client, method)(url)
        if isinstance(what, str):
            body = what
        elif 'raw' in what:
            body = what['raw']
        else:
            body = json.dumps(dict.fromkeys(NAMES, what['value']))
        return getattr(client, method)(url, body, content_type='application/json')

    def run(app: str, shape: str) -> list[str]:
        where, what = MALFORMED[shape]
        failed = []
        for route, view in _routes(get_resolver().url_patterns):
            if not view.__module__.startswith(f'apps.{app}.') or route.startswith('admin/'):
                continue
            if route in NEEDS_PARADEDB and connection.vendor != 'postgresql':
                continue
            url = _fill(route, what if where == 'address' else None)
            if url is None:
                continue
            cls = getattr(view, 'view_class', None) or getattr(view, 'cls', None)
            methods = [m for m in ('get', 'post', 'put', 'patch', 'delete') if cls is None or hasattr(cls, m)]
            for client, who in ((anonymous, 'anonymous'), (staff, 'staff')):
                for method in methods:
                    try:
                        r = send(client, method, url, where, what)
                    except Exception as exc:  # noqa: BLE001 (what the test reports)
                        frames = [f for f in traceback.extract_tb(exc.__traceback__) if '/apps/' in f.filename]
                        at = f' at {frames[-1].filename.rsplit("/back/", 1)[-1]}:{frames[-1].lineno}' if frames else ''
                        failed.append(f'{method.upper()} {route} ({who}): {type(exc).__name__}{at}')
                        continue
                    house = r.get('Content-Type', '').startswith('application/json') and 'errors' in r.json()
                    if r.status_code >= 500 and not house:
                        failed.append(f'{method.upper()} {route} ({who}): {r.status_code}')
                    elif where in ('query', 'address') and '\x00' in what and r.status_code != 400:
                        failed.append(f'{method.upper()} {route} ({who}): {r.status_code} for a NUL, not 400')
        return failed
    return run
