#!/usr/bin/env bash
# The night's job (law-nightly.timer): the retention table /privacy promises (keep_promises, and the searches' words
# after 90 days), the search index merged, then the database dumped beside the app and the last 14 dumps kept. A copy
# off the machine is the operator's to make.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"          # this script is ROOT/app/deploy/nightly.sh
cd "$ROOT/app/back"
set -a; . "$ROOT/.env"; set +a
"$ROOT/venv/bin/python" manage.py keep_promises
"$ROOT/venv/bin/python" manage.py prune_search_logs
"$ROOT/venv/bin/python" manage.py prune_oauth
"$ROOT/venv/bin/python" manage.py end_accesses            # accesses past their date, the letters 30 days before
"$ROOT/venv/bin/python" manage.py refresh_platforms       # OpenAI's connector ranges (the MCP server's shared limits)
# Yesterday's measures into day counts, and the events past ANALYTICS_DAYS out. A fold that fails is said and the night
# goes on: under `set -e` it would stop the jobs after it and the database's dump, and its day can be folded again.
"$ROOT/venv/bin/python" manage.py fold_events || echo 'fold_events failed' >&2
# Search engines: their crawlers' published addresses, the sitemaps (a wave more every two weeks from
# INDEXING_OPENED), and IndexNow told of the day's texts once INDEXING is open.
"$ROOT/venv/bin/python" manage.py refresh_crawlers
"$ROOT/venv/bin/python" manage.py write_sitemaps
"$ROOT/venv/bin/python" manage.py indexnow
# The search's BM25 index merged concurrently: the day's loads leave replaced entries in its segments, and every search
# pays for them until they are merged.
"$ROOT/venv/bin/python" manage.py merge_search_index
# Yesterday's machines, counted from nginx's access log (by family of User-Agent, kind of address and status: no
# address, User-Agent or path is written). Its failure never stops the night: the dump comes next.
"$ROOT/venv/bin/python" manage.py count_machines || echo 'count_machines failed' >&2
# A dump holds every account's password hash, e-mail address and tokens: written readable by this account alone
# (umask 077), and the dumps written before that line made so too.
(umask 077; mkdir -p "$ROOT/backups")
find "$ROOT/backups" -maxdepth 1 -type f -name '*.dump' -perm /go=rwx -exec chmod go= {} +
# The measures' events are left out of the dump, their table's shape kept: they live ANALYTICS_DAYS days on the server
# only. Their day counts (analytics_daycount) go in the dump whole.
(
  umask 077
  docker exec law-pg-1 pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --exclude-table-data=analytics_event \
    > "$ROOT/backups/law-$(date +%F).dump.part"
)
mv "$ROOT/backups/law-$(date +%F).dump.part" "$ROOT/backups/law-$(date +%F).dump"
# Only the nights' own dumps (law-YYYY-MM-DD.dump) are counted and the last 14 kept: one made by hand before an
# operation (law-YYYY-MM-DD-before-….dump) stays until a person removes it.
ls -1t "$ROOT"/backups/law-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].dump | tail -n +15 | xargs -r rm --
