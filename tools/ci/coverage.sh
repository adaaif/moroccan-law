#!/usr/bin/env bash
# The test suite under coverage (nightly): which lines and branches of back/apps and back/config the tests run.
#
#   tools/ci/coverage.sh [ARGS]      ARGS go to pytest
#
# The settings, the floor among them, are in back/.coveragerc: migrations and tests are left out, branches count.
# Reports: back/.reports/coverage.xml (Cobertura XML, for a CI's viewer) and a terminal table of every file not
# fully covered, then each app's figure, least covered first. The run fails when a test fails or when the total falls
# under the floor; the apps' figures are printed either way.
#
# Environment: PYTHON (default back/.venv/bin/python, with pytest-cov), WORKERS (default auto).
#
# Reading a failure: «Required test coverage of N% not reached» means the total fell under the floor: a change
# added code no test runs. Add the tests, or (only when the floor was set too high) lower fail_under in
# back/.coveragerc in a commit that says why.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python="${PYTHON:-back/.venv/bin/python}"
case "$python" in /*) ;; */*) python="$root/$python" ;; esac

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"; }
run() { printf '+'; printf ' %q' "$@"; printf '\n'; "$@"; }

case "${1:-}" in -h|--help|help) usage; exit 0 ;; esac

echo "+ cd $root/back"
cd "$root/back"
mkdir -p .reports
rm -f .reports/.coverage .reports/.coverage.*
status=0
run env -u TEST_DATABASE_URL "$python" -m pytest --ds=config.settings.test -p no:cacheprovider -n "${WORKERS:-auto}" \
  --cov=apps --cov=config --cov-config=.coveragerc --cov-branch \
  --cov-report=term:skip-covered --cov-report=xml "$@" || status=$?

echo "+ (each app's coverage, from back/.reports/.coverage)"
"$python" - <<'EOF'
import io
from pathlib import Path

import coverage

cov = coverage.Coverage(config_file='.coveragerc')
cov.load()
rows = []
for app in sorted(p.name for p in Path('apps').iterdir() if (p / '__init__.py').exists()):
    try:
        rows.append((cov.report(include=[f'apps/{app}/*'], file=io.StringIO()), app))
    except coverage.exceptions.NoDataError:
        continue
for percent, app in sorted(rows):
    print(f'{percent:6.1f} %  apps/{app}')
EOF
exit "$status"
