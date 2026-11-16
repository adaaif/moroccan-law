#!/usr/bin/env bash
# The tests that need ParadeDB: search, the assistants' server (MCP) and the topics, which read the search index.
# They skip on SQLite (tools/ci/backend.sh test); here they run against a PostgreSQL server with ParadeDB's pg_search.
#
#   TEST_DATABASE_URL=postgres://user:password@host:port/name tools/ci/search.sh [ARGS]
#
# pytest-django makes its own databases from that address, `test_<name>_gw0`, `test_<name>_gw1`, …, one a worker,
# and drops them at the end: choose a name no database of yours has (`law_ci_t`, say). The server's user must be
# allowed to create databases. ARGS go to pytest (a path, -k …). A JUnit report is written to
# back/.reports/search-junit.xml, unless PYTEST_ADDOPTS names one.
#
# Environment: PYTHON (default back/.venv/bin/python), WORKERS (default 2: each worker migrates a database of its own).
#
# Reading a failure: «connection refused» or an authentication error is the server, not the code; «extension
# pg_search is not available» means a PostgreSQL without ParadeDB. Otherwise pytest's summary names the tests; run
# one alone with `tools/ci/search.sh <path>::<name>`.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python="${PYTHON:-back/.venv/bin/python}"
case "$python" in /*) ;; */*) python="$root/$python" ;; esac

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"; }
run() { printf '+'; printf ' %q' "$@"; printf '\n'; "$@"; }

case "${1:-}" in -h|--help|help) usage; exit 0 ;; esac
case "${TEST_DATABASE_URL:-}" in
  postgres://*|postgresql://*) ;;
  '') echo "search.sh: TEST_DATABASE_URL is not set; without it these tests skip (see --help)" >&2; exit 2 ;;
  *) echo "search.sh: TEST_DATABASE_URL must name a PostgreSQL server (postgres://…)" >&2; exit 2 ;;
esac

echo "+ cd $root/back"
cd "$root/back"
mkdir -p .reports
# The three apps, unless an argument names tests of its own.
paths=(apps/search apps/mcp apps/topics)
for arg in "$@"; do case "$arg" in apps/*) paths=() ;; esac; done
# The address is printed without its password.
echo "+ (TEST_DATABASE_URL=$(sed -E 's#(://[^:/@]+):[^@]*@#\1:***@#' <<<"$TEST_DATABASE_URL"))"
# The JUnit file goes first in PYTEST_ADDOPTS, so a caller's own --junitxml there comes after it and wins.
run env PYTEST_ADDOPTS="--junitxml=.reports/search-junit.xml${PYTEST_ADDOPTS:+ $PYTEST_ADDOPTS}" \
  "$python" -m pytest --ds=config.settings.test -p no:cacheprovider -n "${WORKERS:-2}" -rs \
  ${paths[@]+"${paths[@]}"} "$@"
