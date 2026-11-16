#!/usr/bin/env bash
# Queries inside loops (nightly): the test suite run with the recorder of back/config/queryloops.py, which notes every
# line of the code that runs one SQL statement more than OVER times in one call from a test (a request, a command, a
# service). The functions found are compared with the kept list, back/config/queryloops-kept.txt: one that is not on
# it fails the run. The list holds the offenders known when it was written, by file and function, never by line.
#
#   tools/ci/loops.sh             run the suite and compare
#   tools/ci/loops.sh --update    run the suite and write the kept list again from what it found
#
# The run's whole list, with each line's query, its repeats and the tests that reach it, is back/.reports/loops.json.
#
# Environment: PYTHON (default back/.venv/bin/python), WORKERS (default auto), OVER (default 2: a test holds a few
# rows, so a query a row shows at three; the kept list was written at 2, and another OVER finds another list).
#
# Reading a failure: each «NEW apps/…::function» names the function, the line, how often one call ran the query, a
# test that reaches it, the query's shape and the lines that called it. Read the related rows in a fixed number of
# queries (select_related, prefetch_related, one `__in` query) and add a test that gives the code a few rows and ten
# times as many and asserts the same count (apps/*/tests/test_loops.py). If the loop must stay, run --update and
# say why in the commit. «no longer found» lines never fail: --update drops them.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python="${PYTHON:-back/.venv/bin/python}"
case "$python" in /*) ;; */*) python="$root/$python" ;; esac

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"; }
run() { printf '+'; printf ' %q' "$@"; printf '\n'; "$@"; }

action=check
case "${1:-}" in
  -h|--help|help) usage; exit 0 ;;
  --update) action=update ;;
  '') ;;
  *) usage >&2; exit 2 ;;
esac

echo "+ cd $root/back"
cd "$root/back"
mkdir -p .reports
rm -f .reports/loops.json
run env -u TEST_DATABASE_URL "$python" -m pytest --ds=config.settings.test -p no:cacheprovider -n "${WORKERS:-auto}" \
  --query-loops --query-loops-over="${OVER:-2}" --query-loops-json=.reports/loops.json
run "$python" -m config.queryloops "$action" .reports/loops.json
