"""The registry as the web reads it (web/src/shared/analytics/measures.ts, `manage.py write_measure_types`): the committed
file is what the command writes from the registry today."""
import re
from io import StringIO

import pytest
from django.core.management import call_command

import manage
from apps.analytics import registry
from apps.analytics.services import typescript

pytestmark = pytest.mark.skipif(not typescript.TARGET.parent.parent.is_dir(), reason='the web is not beside the back')


def test_the_webs_file_is_the_registrys_as_it_is_today():
    assert typescript.TARGET.read_text(encoding='utf-8') == typescript.render(), \
        'the registry changed: run manage.py write_measure_types and commit web/src/shared/analytics/measures.ts'


def test_the_file_says_it_is_written_and_holds_every_name_kind_and_property():
    written = typescript.render()
    assert written.startswith('// Written by `manage.py write_measure_types`')
    for name, measure in registry.MEASURES.items():
        assert f"'{name}': {{" in written
        for prop in measure.props:
            assert re.search(rf'^    {prop}\?: ', written, re.M), (name, prop)
    assert "export const KINDS = ['home', 'law', 'article'," in written
    assert "step?: 'opened' | 'answered' |" in written
    assert "lcp: { type: 'number', lo: 0, hi: 60000, step: 50 }" in written
    assert "ref: { type: 'pattern', pattern: '^[a-z0-9-]+(\\\\.[a-z0-9-]+)+$', most: 60, lower: true }" in written


def test_the_command_writes_the_file(tmp_path, monkeypatch):
    target = tmp_path / 'web' / 'measures.ts'
    monkeypatch.setattr(typescript, 'TARGET', target)
    out = StringIO()
    call_command('write_measure_types', stdout=out)
    assert target.read_text(encoding='utf-8') == typescript.render() and str(target) in out.getvalue()


def test_writing_the_file_never_empties_the_kept_answers():
    """It writes no row an answer reads: after any command not in READ_ONLY, manage.py empties every kept answer."""
    assert 'write_measure_types' in manage.READ_ONLY
