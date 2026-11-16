"""Commands a stranger could run by mistake: those that rewrite every row ask for the database's name, those that pay
ask for --write. No test here sends a request to the model or to a site."""
import importlib.util
import io
import re
from pathlib import Path

import pytest
from django.core.management import call_command, get_commands, load_command_class
from django.core.management.base import CommandError
from django.db import connection

from apps.sources.services import ocr

APPS = Path(__file__).resolve().parents[2]
ARCHIVE_RUN = APPS / 'corpus' / 'services' / 'archive_run'      # the archive command's parts
# What sends a paid request: the batch and call helpers, the clients, the post check's model call.
PAID = re.compile(r'\b(run_batch|ocr_claude_batch|ocr_claude_now|ocr_readings_batch|ocr_columns_batch|ocr_strips_batch|'
                  r'_client\(\)|check\.ask|ocr_issue|read_toc|extract_texts|situations import draft|structure import|'
                  r"call_command\('process_issue')")


@pytest.fixture
def unarmed(monkeypatch, settings, tmp_path):
    monkeypatch.setattr(ocr.guard, '_SPENDING', False)
    settings.ANTHROPIC_API_KEY = 'sk-ant-not-a-key'
    settings.CORPUS_DIR = tmp_path          # being let spend reads the ledger first: never the real one


@pytest.mark.django_db
def test_no_paid_request_leaves_a_process_whose_command_was_not_given_write(unarmed):
    from apps.corpus.services import llm
    with pytest.raises(ocr.SpendingNotAllowed, match='--write'):
        ocr._client()
    with pytest.raises(ocr.SpendingNotAllowed, match='--write'):
        llm._client()
    ocr.allow_spending(False)
    with pytest.raises(ocr.SpendingNotAllowed):
        ocr._client()
    ocr.allow_spending()
    assert ocr._client().api_key == 'sk-ant-not-a-key'      # made, nothing sent


def test_every_command_that_can_pay_takes_write():
    names = get_commands()
    paid, missing = [], []
    for name, app in names.items():
        if not app.startswith('apps.'):
            continue
        path = APPS / app.removeprefix('apps.') / 'management' / 'commands' / f'{name}.py'
        if not path.exists():
            continue
        source = path.read_text(encoding='utf-8')
        if name == 'archive':           # the archive command's parts are a package of their own
            source += ''.join(p.read_text(encoding='utf-8') for p in sorted(ARCHIVE_RUN.glob('*.py')))
        if not PAID.search(source):
            continue
        paid.append(name)
        parser = load_command_class(app, name).create_parser('manage.py', name)
        if not any('--write' in a.option_strings for a in parser._actions):
            missing.append(name)
    assert {'process_issue', 'fetch_new_issues', 'read_memoranda', 'repair_tables', 'read_unclear', 'draft_vocab',
            'check_eval', 'measure_mcp', 'structure_trial', 'sweep_contents', 'fetch_conventions', 'archive'} <= set(paid)
    assert missing == []


@pytest.mark.django_db
def test_read_unclear_and_check_eval_send_nothing_without_write(unarmed, monkeypatch):
    from apps.discussion.services import check
    monkeypatch.setattr(check, 'ask', lambda text: pytest.fail('sent'))
    out = io.StringIO()
    call_command('check_eval', only='demo', stdout=out)       # the demo's words: in every copy of the repository
    assert '--write sends them' in out.getvalue()
    call_command('read_unclear', stdout=io.StringIO())       # counts and prices; the client would refuse anyway


def test_a_worker_run_without_write_stops_and_marks_no_chunk(unarmed):
    """The archive's workers set a failed chunk aside and go on; a refusal to spend is not a failure of the chunk."""
    source = (ARCHIVE_RUN / 'work.py').read_text()
    assert source.index('except SpendingNotAllowed') < source.index('except Exception:     # noqa: BLE001 — the chunk is set aside')


# ── --yes-on ─────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_consolidate_rewrites_nothing_unless_told_which_database(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    with pytest.raises(CommandError, match='--yes-on'):
        call_command('consolidate', stdout=io.StringIO())
    with pytest.raises(CommandError, match='--yes-on'):
        call_command('consolidate', yes_on='another_database', stdout=io.StringIO())
    assert not (tmp_path / 'reports').exists()


@pytest.mark.django_db
def test_keep_best_readings_over_every_page_asks_for_the_database_and_named_issues_do_not():
    with pytest.raises(CommandError, match='--yes-on'):
        call_command('keep_best_readings', stdout=io.StringIO())
    with pytest.raises(CommandError, match='--yes-on'):
        call_command('keep_best_readings', '--recount', stdout=io.StringIO())
    call_command('keep_best_readings', yes_on=connection.settings_dict['NAME'], stdout=io.StringIO())


def test_the_copy_into_postgres_empties_nothing_unless_told_which_database(monkeypatch):
    path = APPS.parent / 'scripts' / 'copy_sqlite_to_postgres.py'
    spec = importlib.util.spec_from_file_location('copy_sqlite_to_postgres', path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    monkeypatch.setattr(script, 'connections', None)        # any use of the database before the check fails loudly
    with pytest.raises(SystemExit, match='--yes-on'):
        script.main([])
    with pytest.raises(SystemExit, match='--yes-on'):
        script.main(['--yes-on', 'some_other_database'])
