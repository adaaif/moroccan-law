"""The BM25 index rebuilt, concurrently: searches go on while it is built (31 Oct 2026). Every load replaces its texts'
entries, and ParadeDB keeps the replaced ones in its segments until a rebuild: as the segments pile up, a one-word
search spends most of its time opening them; rebuilt, it is quick again. Run after each archive
replay, each night (deploy/nightly.sh), before the morning's fetch and after a deploy. Nothing to do on SQLite (the
tests).

One rebuild at a time (11 Nov 2026). Two concurrent rebuilds of one index deadlock: PostgreSQL stops one, which leaves
its half-built copy behind, invalid, written by every load and never read. On 10 Nov the night's rebuild met a
deploy's twice: two copies of 527 MB stayed, and the night's job died before its dump. So a run takes a lock first and
leaves the work to a rebuild already running, one started by hand included; and it drops what an interrupted rebuild
left before it builds."""
import time

from django.core.management.base import BaseCommand
from django.db import connection

TABLE = 'search_entry'
INDEX = 'search_entry_bm25'
LOCK = 0x626D3235        # «bm25»: a session's advisory lock, gone with its connection whatever happens to the run
# What PostgreSQL names the copy a concurrent rebuild builds, and the old index it has yet to drop.
LEFT = rf'^{INDEX}_cc(new|old)\d*$'


class Command(BaseCommand):
    help = "Rebuild the search's BM25 index concurrently, leaving the entries the loads replaced behind."

    def handle(self, *args, **opts):
        if connection.vendor != 'postgresql':
            self.stdout.write('not PostgreSQL: nothing to merge')
            return
        with connection.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(%s)', [LOCK])
            if not cur.fetchone()[0]:
                self.stdout.write(f'{INDEX}: another rebuild is running: left to it')
                return
            try:
                self.rebuild(cur)
            finally:
                cur.execute('SELECT pg_advisory_unlock(%s)', [LOCK])

    def rebuild(self, cur):
        # A rebuild typed into psql holds no lock of ours: PostgreSQL's own progress says it is there.
        cur.execute('SELECT count(*) FROM pg_stat_progress_create_index WHERE relid = %s::regclass', [TABLE])
        if cur.fetchone()[0]:
            self.stdout.write(f'{INDEX}: another rebuild is running: left to it')
            return
        cur.execute('SELECT c.relname FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid '
                    'WHERE i.indrelid = %s::regclass AND NOT i.indisvalid AND c.relname ~ %s ORDER BY 1', [TABLE, LEFT])
        left = [name for (name,) in cur.fetchall()]
        for name in left:
            cur.execute(f'DROP INDEX CONCURRENTLY IF EXISTS {connection.ops.quote_name(name)}')
        cur.execute('SELECT count(*) FROM paradedb.index_info(%s)', [INDEX])
        before = cur.fetchone()[0]
        started = time.monotonic()
        cur.execute(f'REINDEX INDEX CONCURRENTLY {INDEX}')
        cur.execute('SELECT count(*) FROM paradedb.index_info(%s)', [INDEX])
        after = cur.fetchone()[0]
        dropped = f", {len(left)} interrupted rebuild{'s' if len(left) > 1 else ''} dropped first" if left else ''
        self.stdout.write(f'{INDEX}: {before} segments → {after} in {time.monotonic() - started:.0f} s{dropped}')
