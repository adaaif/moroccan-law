"""Copy every row of the SQLite dev database into Postgres, keeping ids, then reset Postgres's sequences.

Run from back/, after `migrate` on the Postgres database, naming it (it must be the database DATABASE_URL points at):
    DATABASE_URL=postgres://… DJANGO_SETTINGS_MODULE=config.settings.pgcopy \
        .venv/bin/python scripts/copy_sqlite_to_postgres.py --yes-on <its name>

Postgres's tables are emptied first (their content types and permissions too, so the copied ids line up).
The SQLite file is only read; with runners writing to it, the copy is a snapshot of each table in turn.
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.pgcopy')

import django

django.setup()

from django.apps import apps  # noqa: E402
from django.core.management.color import no_style  # noqa: E402
from django.core.management.base import CommandError  # noqa: E402
from django.db import connections, transaction  # noqa: E402

from config import confirm  # noqa: E402

CHUNK = 2000


def models_in_order():
    """Every table once, each after the tables its foreign keys point to (a self-reference waits for nothing)."""
    models = [m for m in apps.get_models(include_auto_created=True) if m._meta.managed and not m._meta.proxy]
    deps = {m: {f.related_model._meta.concrete_model for f in m._meta.concrete_fields
                if f.is_relation and f.related_model and f.related_model._meta.concrete_model is not m}
            for m in models}
    ordered, placed = [], set()
    while len(ordered) < len(models):
        ready = [m for m in models if m not in placed and deps[m] <= placed]
        if not ready:
            raise RuntimeError('foreign keys in a cycle: ' + ', '.join(m._meta.label for m in models if m not in placed))
        for m in ready:
            ordered.append(m)
            placed.add(m)
    return ordered


def main(argv=None):
    parser = argparse.ArgumentParser(description='Copy the SQLite dev database into Postgres, emptying Postgres first.')
    confirm.add_argument(parser)
    args = parser.parse_args(argv)
    try:
        confirm.confirm(args.yes_on, what='The copy (every table emptied, then filled from SQLite)')
    except CommandError as exc:
        sys.exit(str(exc))
    pg = connections['default']
    assert pg.vendor == 'postgresql', 'default must be Postgres'  # noqa: S101 — a developer's script, run by hand
    models = models_in_order()
    tables = [m._meta.db_table for m in models]
    with pg.cursor() as cur:
        cur.execute('TRUNCATE ' + ', '.join(pg.ops.quote_name(t) for t in tables) + ' RESTART IDENTITY CASCADE')
    started = time.monotonic()
    for model in models:
        rows, batch = 0, []
        with transaction.atomic(using='default'):
            for obj in model._base_manager.using('sqlite').order_by('pk').iterator(chunk_size=CHUNK):
                batch.append(obj)
                if len(batch) == CHUNK:
                    model._base_manager.using('default').bulk_create(batch)
                    rows += len(batch)
                    batch = []
            if batch:
                model._base_manager.using('default').bulk_create(batch)
                rows += len(batch)
        if rows:
            print(f'{model._meta.label}: {rows}', flush=True)
    with pg.cursor() as cur:
        for sql in pg.ops.sequence_reset_sql(no_style(), models):
            cur.execute(sql)
    print(f'done in {time.monotonic() - started:.0f} s')


if __name__ == '__main__':
    main()
