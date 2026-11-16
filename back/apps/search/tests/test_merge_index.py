"""The search index merged where it can be (31 Oct 2026): on PostgreSQL alone, one rebuild at a time, what an
interrupted one left dropped first."""
from io import StringIO

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_the_search_index_is_merged_only_on_postgresql():
    from django.db import connection
    if connection.vendor == 'postgresql':
        # There the command rebuilds the index CONCURRENTLY, which PostgreSQL refuses inside a transaction: a test's.
        pytest.skip('the rebuild itself cannot run inside a test transaction')
    out = StringIO()
    call_command('merge_search_index', stdout=out)
    assert 'nothing to merge' in out.getvalue()


class Rebuild:
    """PostgreSQL as merge_search_index sees it: each statement kept, and an answer for those it reads."""

    vendor = 'postgresql'

    def __init__(self, **answers):
        self.answers, self.ran = answers, []
        self.ops = type('Ops', (), {'quote_name': staticmethod(lambda name: f'"{name}"')})

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.ran.append(sql)

    def fetchall(self):
        last = self.ran[-1]
        if 'pg_try_advisory_lock' in last:
            return [(self.answers.get('lock', True),)]
        if 'pg_stat_progress_create_index' in last:
            return [(self.answers.get('running', 0),)]
        if 'indisvalid' in last:
            return [(name,) for name in self.answers.get('left', [])]
        return [(4,)]

    def fetchone(self):
        return self.fetchall()[0]


def merged(monkeypatch, **answers):
    database = Rebuild(**answers)
    monkeypatch.setattr('apps.search.management.commands.merge_search_index.connection', database)
    out = StringIO()
    call_command('merge_search_index', stdout=out)
    return database.ran, out.getvalue()


def test_a_rebuild_leaves_the_index_to_the_one_already_running(monkeypatch):
    # Two concurrent rebuilds of one index deadlock, and the one PostgreSQL stops leaves an invalid copy (10 Nov 2026).
    ran, said = merged(monkeypatch, lock=False)
    assert 'another rebuild is running' in said and not any('REINDEX' in sql or 'DROP' in sql for sql in ran)
    # One typed into psql holds no lock: its progress is seen, nothing is touched, and the lock is given back.
    ran, said = merged(monkeypatch, running=1)
    assert 'another rebuild is running' in said and not any('REINDEX' in sql or 'DROP' in sql for sql in ran)
    assert 'pg_advisory_unlock' in ran[-1]


def test_a_rebuild_drops_what_an_interrupted_one_left_before_it_builds(monkeypatch):
    ran, said = merged(monkeypatch, left=['search_entry_bm25_ccnew', 'search_entry_bm25_ccnew1'])
    work = [sql for sql in ran if sql.startswith(('DROP', 'REINDEX'))]
    assert work == ['DROP INDEX CONCURRENTLY IF EXISTS "search_entry_bm25_ccnew"',
                    'DROP INDEX CONCURRENTLY IF EXISTS "search_entry_bm25_ccnew1"',
                    'REINDEX INDEX CONCURRENTLY search_entry_bm25']
    assert '4 segments → 4' in said and '2 interrupted rebuilds dropped first' in said
    assert 'pg_advisory_unlock' in ran[-1]
    ran, said = merged(monkeypatch)
    assert [sql for sql in ran if sql.startswith(('DROP', 'REINDEX'))] == ['REINDEX INDEX CONCURRENTLY search_entry_bm25']
    assert 'dropped' not in said
