"""The public tree leaves some files out (.gitattributes, export-ignore): the pages of the Bulletin read again, the
moderation check's written test set, the run scripts' output. A command that reads one says plainly that it is not
there, and why, instead of a traceback."""
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def test_a_page_reading_that_is_not_there_is_said_with_where_it_comes_from(tmp_path):
    with pytest.raises(CommandError, match='data release'):
        call_command('apply_page_reading', str(tmp_path / 'pages_reread_2026-11-07_batch_1.yaml'))
    with pytest.raises(CommandError, match='no such file'):
        call_command('apply_page_reading', str(tmp_path / 'family.yaml'))


def test_the_pages_read_elsewhere_that_are_not_there_are_said(tmp_path):
    with pytest.raises(CommandError, match='private repository'):
        call_command('import_rereads', str(tmp_path / 'rereads.json'))


@pytest.mark.django_db
def test_the_checks_measure_runs_on_the_demo_alone_without_the_written_set(monkeypatch, capsys):
    from apps.discussion.management.commands import check_eval

    monkeypatch.setattr(check_eval, 'written', None)
    with pytest.raises(CommandError, match='private evaluation set'):
        call_command('check_eval')
    with pytest.raises(CommandError, match='private evaluation set'):
        call_command('check_eval', '--only', 'breaks')
    call_command('check_eval', '--only', 'demo')            # nothing sent without --write
    assert 'items, one request each' in capsys.readouterr().out


def test_a_search_set_that_is_not_there_is_said_and_never_read():
    from apps.mcp.management.commands import measure_mcp
    from apps.search.services.goldset import sets

    with pytest.raises(CommandError, match='No set named'):
        call_command('search_eval', '--set', 'a-set-kept-elsewhere')
    assert 'a-set-kept-elsewhere' not in {p.stem for p in sets()}
    # The assistants' measure takes questions from the sets it finds.
    with mock.patch.object(measure_mcp, 'SETS', ['a-set-kept-elsewhere', 'work']):
        assert {q['set'] for q in measure_mcp.Command._questions(2)} == {'work'}
