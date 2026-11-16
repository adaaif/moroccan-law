"""The server's units and dump scripts (deploy/), read as files: production's settings named in every unit that runs
Django, no unit able to raise its rights, its /tmp its own, and a database dump readable by its owner alone. Beside the
nginx tests (test_addresses.py), which read deploy/nginx.conf the same way."""
import re
from pathlib import Path

import pytest
from django.conf import settings

REPO = Path(settings.BASE_DIR).parent
DEPLOY = REPO / 'deploy'
# The scripts that write a database dump: the nightly one.
DUMPS = [DEPLOY / 'nightly.sh']

pytestmark = pytest.mark.skipif(not DEPLOY.exists(), reason='the repository is not beside the app')


def _units() -> dict[str, str]:
    return {p.name: p.read_text(encoding='utf-8') for p in sorted(DEPLOY.glob('*.service'))}


def test_every_unit_that_runs_django_names_the_production_settings():
    django = {name for name, text in _units().items() if re.search(r'manage\.py|gunicorn|uvicorn|nightly\.sh|fetch\.sh', text)}
    assert len(django) == 10
    for name in django:
        assert 'Environment=DJANGO_SETTINGS_MODULE=config.settings.prod\n' in _units()[name], name


def test_no_unit_can_raise_its_rights_and_each_keeps_its_own_tmp():
    for name, text in _units().items():
        assert 'NoNewPrivileges=yes\n' in text and 'PrivateTmp=yes\n' in text, name


def test_a_database_dump_is_readable_by_its_owner_alone():
    for script in DUMPS:
        text = script.read_text(encoding='utf-8')
        for line in (line for line in text.splitlines() if 'pg_dump' in line and not line.lstrip().startswith('#')):
            # The dump's line runs under umask 077, or inside a ( umask 077 … ) block.
            block = text[:text.index(line)]
            opened = block.rfind('(\n  umask 077')
            assert line.lstrip().startswith('(umask 077;') or (opened != -1 and ')' not in block[opened + 1:]), script.name


def test_a_job_run_more_often_than_daily_never_empties_the_kept_answers():
    """manage.py bumps the answers' generation after any command not in READ_ONLY: a timer that runs such a command
    every few minutes, or every hour, would empty every kept answer each time."""
    import manage

    often = [p for p in sorted(DEPLOY.glob('*.timer'))
             if re.search(r'^OnCalendar=(hourly|\*:\S+)\s*$', p.read_text(encoding='utf-8'), re.M)]
    assert often, 'no frequent timer found: the pattern no longer reads the units'
    for timer in often:
        unit = (DEPLOY / timer.name.replace('.timer', '.service')).read_text(encoding='utf-8')
        command = re.search(r'^ExecStart=.*manage\.py (\w+)', unit, re.M)
        assert command and command.group(1) in manage.READ_ONLY, timer.name
