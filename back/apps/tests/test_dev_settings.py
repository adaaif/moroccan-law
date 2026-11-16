"""The development settings read their four switches as every other setting is read: «True» means on and «False»
means off, as back/.env.example writes them, and 1 and 0 still work. Each case runs in a process of its own, so the
development settings (and a developer's back/.env) never reach the suite's."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACK = Path(__file__).resolve().parents[2]
SWITCHES = ('REGISTRATION_OPEN', 'DISCUSSION_OPEN', 'DISCUSSION_MEDIA', 'SHOW_DEMO_PEOPLE')


def dev_settings(**env) -> dict:
    code = ('import json, config.settings.dev as s; '
            f'print(json.dumps({{name: getattr(s, name) for name in {SWITCHES!r}}}))')
    done = subprocess.run([sys.executable, '-c', code], cwd=BACK, env={**os.environ, **env}, capture_output=True,
                          text=True, timeout=60, check=True)
    return json.loads(done.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize('on, off', [('True', 'False'), ('1', '0')])
def test_each_switch_reads_true_and_false_as_the_example_writes_them(on, off):
    assert dev_settings(**dict.fromkeys(SWITCHES, on)) == dict.fromkeys(SWITCHES, True)
    assert dev_settings(**dict.fromkeys(SWITCHES, off)) == dict.fromkeys(SWITCHES, False)
