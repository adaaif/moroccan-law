"""/privacy is what the code does: its numbers and names are read here from the same settings, constants and deploy
scripts the code runs by, in both languages. A change to one without the other fails here."""
import json
import re

import pytest
from django.conf import settings
from django.utils import timezone

from apps.analytics import registry
from apps.corpus.services import reading
from apps.discussion.management.commands.keep_promises import KEEP_DAYS
from apps.mcp.services import quotas
from apps.search.services.events import KEEP_DAYS as SEARCH_WORDS_DAYS

LOCALES = settings.BASE_DIR.parent / 'web' / 'src' / 'features' / 'discussion' / 'locales'
DEPLOY = settings.BASE_DIR.parent / 'deploy'
YEAR = {'ar': 'عام', 'fr': '1 an'}
TWO_HOURS = {'ar': 'بعد ساعتين', 'fr': 'au bout de deux heures'}

pytestmark = pytest.mark.skipif(not LOCALES.is_dir(), reason='the web is not beside the back')


def page(lang: str) -> dict:
    return json.loads((LOCALES / f'{lang}.json').read_text(encoding='utf-8'))['privacy']


def kept(script: str) -> int:
    """How many dumps a deploy script keeps: its `ls -1t … | tail -n +N | … rm`."""
    found = re.search(r'tail -n \+(\d+) \| xargs -r rm', (DEPLOY / script).read_text(encoding='utf-8'))
    return int(found.group(1)) - 1


def number(text: str, n: int) -> bool:
    return re.search(rf'(?<![\d.,]){n}(?![\d.,])', text) is not None


@pytest.mark.parametrize('lang', ['ar', 'fr'])
def test_the_assistants_counts_live_as_long_as_the_quotas_keep_them(lang):
    """A direct caller's day is counted under its address, a ChatGPT user's hour under a key of its own: the page says
    how long each count lives."""
    said = page(lang)['acts']['read']['items']['assistants']['d']
    now = timezone.localtime()
    assert number(said, quotas._window('day', now)[1] // 3600), lang
    assert quotas._window('hour', now)[1] == 2 * 3600 and TWO_HOURS[lang] in said, lang


@pytest.mark.parametrize('lang', ['ar', 'fr'])
def test_the_backups_are_counted_as_the_scripts_keep_them(lang):
    on_server = kept('nightly.sh')
    # The copy kept off the server is made by a script of the private repository: checked where that script is.
    elsewhere = kept('pull-backup.sh') if (DEPLOY / 'pull-backup.sh').exists() else None
    p = page(lang)
    for text in (' '.join(p['rows']['backups']), p['acts']['read']['items']['backups']['d']):
        assert number(text, on_server) and (elsewhere is None or number(text, elsewhere)), (lang, text)


@pytest.mark.parametrize('lang', ['ar', 'fr'])
def test_the_cookies_are_named(lang):
    p = page(lang)
    for text in (p['plaque'], p['acts']['read']['items']['day']['d'], p['acts']['read']['not']):
        assert reading.READER in text and reading.COOKIE in text, (lang, text)
    assert number(p['acts']['read']['items']['day']['d'], settings.READING_BUDGET)


@pytest.mark.parametrize('lang', ['ar', 'fr'])
def test_the_retention_rows_are_the_nightly_jobs(lang):
    rows = page(lang)['rows']
    assert number(rows['words'][1], SEARCH_WORDS_DAYS)
    for row, key in (('notices', 'notices'), ('edits', 'edits'), ('check', 'checks'), ('removed', 'removed'),
                     ('reports', 'reports')):
        assert number(rows[row][1], KEEP_DAYS[key]), (lang, row)
    assert KEEP_DAYS['ledger'] == 365 and rows['ledger'][1] == YEAR[lang]


@pytest.mark.parametrize('lang', ['ar', 'fr'])
def test_sign_up_is_said_as_the_setting_has_it(lang):
    # The page picks the sentence by the server's REGISTRATION_OPEN (useRegistration): both must be there.
    write = page(lang)['acts']['write']
    assert write['answer'] and write['answerClosed'] and write['answer'] != write['answerClosed']


@pytest.mark.parametrize('lang', ['ar', 'fr'])
def test_every_measure_is_said(lang):
    """/privacy lists the measures as GET /api/measure/ gives them, each with its sentence (privacy.measures, its name
    with «_» for «.») under its category's words: a measure the registry gains fails here until a reader can read it."""
    p = page(lang)
    for name in registry.MEASURES:
        assert p['measures'].get(name.replace('.', '_'), '').strip(), (lang, name)
    for category in registry.CATEGORIES:
        assert p['counted']['categories'].get(category, '').strip(), (lang, category)


@pytest.mark.parametrize('lang', ['ar', 'fr'])
def test_the_events_are_kept_as_long_as_the_server_says(lang):
    """How long an event is kept comes from the server (ANALYTICS_DAYS, in GET /api/measure/'s `days`), never written in
    the words."""
    p = page(lang)
    assert '{{days}}' in p['rows']['measured'][1] and '{{days}}' in p['counted']['kept'], lang
    assert registry.public()['days'] == settings.ANALYTICS_DAYS
