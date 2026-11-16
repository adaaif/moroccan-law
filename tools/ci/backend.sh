#!/usr/bin/env bash
# The backend's CI jobs. The same script runs on a developer's machine and on GitHub, so a red job is reproduced
# with the one command its log names.
#
#   tools/ci/backend.sh lint      ruff over back/, with the rules of back/ruff.toml
#   tools/ci/backend.sh check     Django's checks, migrations a model change still needs (none may be missing), and the
#                                 deploy checks on the production settings, warnings included
#   tools/ci/backend.sh test [ARGS]   the test suite on SQLite in memory, ARGS passed to pytest (a path, -k …);
#                                 a JUnit report in back/.reports/junit.xml (unless PYTEST_ADDOPTS names one) and
#                                 the twenty slowest steps
#   tools/ci/backend.sh sample    the sample corpus migrated and loaded into an empty temporary SQLite database
#   tools/ci/backend.sh all       lint, check, test and sample, in that order
#
# Environment: PYTHON (default back/.venv/bin/python, with the locked packages and the ma_law module installed);
# the system packages of back/requirements/apt.txt (a test that needs a missing one is skipped, except under CI=true,
# where the run stops and names it);
# WORKERS, pytest-xdist's process count for `test` (default auto). The search tests that need ParadeDB skip here:
# tools/ci/search.sh runs them. Nothing is installed and nothing outside this machine is reached: the deploy checks
# get a throwaway secret key, and a database and a cache at sockets that do not exist.
#
# Reading a failure: the last command printed (after «+») is the one that failed. `lint` names each file:line and
# rule (`ruff rule <code>` explains it): fix the code, or add `# noqa: <code> — why` where the code is right.
# `check` prints Django's message and its id. `test` ends with pytest's summary; run one failing test alone with
# `tools/ci/backend.sh test <path>::<name>`.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python="${PYTHON:-back/.venv/bin/python}"
case "$python" in /*) ;; */*) python="$root/$python" ;; esac

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"; }
run() { printf '+'; printf ' %q' "$@"; printf '\n'; "$@"; }
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT

lint() {
  local format=()
  if [ "${GITHUB_ACTIONS:-}" = true ]; then format=(--output-format=github); fi
  run "$python" -m ruff check --no-cache ${format[@]+"${format[@]}"} .
}

check() {
  # The suite's settings: nothing is read from a developer's .env, and the database is SQLite in memory.
  run env DJANGO_SETTINGS_MODULE=config.settings.test "$python" manage.py check --fail-level WARNING
  run env DJANGO_SETTINGS_MODULE=config.settings.test "$python" manage.py makemigrations --check --dry-run
  local key
  key="ci-$("$python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  # A server names its fetchers and its letters' sender (sources.E001, accounts.E002): CI gives them names of its own.
  echo "+ (config.settings.prod with a throwaway SECRET_KEY, ALLOWED_HOSTS=ci.invalid, a fetcher's name and a sender at" \
       "ci.invalid, PostgreSQL and Redis at sockets in an empty folder)"
  DJANGO_SETTINGS_MODULE=config.settings.prod SECRET_KEY="$key" ALLOWED_HOSTS=ci.invalid \
    FETCH_USER_AGENT='ci/1 (+https://ci.invalid)' DEFAULT_FROM_EMAIL='ci <noreply@ci.invalid>' \
    POSTGRES_HOST="$scratch" REDIS_URL="unix://$scratch/redis.sock" COUNTERS_REDIS_URL='' \
    run "$python" manage.py check --deploy --fail-level WARNING
}

tests() {
  mkdir -p .reports
  # SQLite in memory, as on GitHub, even where a developer's shell names a test server. The JUnit file goes first in
  # PYTEST_ADDOPTS, so a caller's own --junitxml there comes after it and wins.
  run env -u TEST_DATABASE_URL PYTEST_ADDOPTS="--junitxml=.reports/junit.xml${PYTEST_ADDOPTS:+ $PYTEST_ADDOPTS}" \
    "$python" -m pytest --ds=config.settings.test -p no:cacheprovider -n "${WORKERS:-auto}" --durations=20 "$@"
}

sample() (
  # The development settings on a database of its own; REDIS_URL empty keeps a developer's cache out of it.
  export DJANGO_SETTINGS_MODULE=config.settings.dev DATABASE_URL="sqlite:///$scratch/sample.sqlite3" REDIS_URL=''
  echo "+ (DATABASE_URL=$DATABASE_URL)"
  run "$python" manage.py migrate -v 0
  run "$python" manage.py load_sample
)

job="${1:-}"
[ $# -gt 0 ] && shift
case "$job" in
  -h|--help|help) usage; exit 0 ;;
  lint|check|sample|all) if [ $# -gt 0 ]; then echo "backend.sh $job takes no arguments" >&2; exit 2; fi ;;
  test) ;;
  *) usage >&2; exit 2 ;;
esac

echo "+ cd $root/back"
cd "$root/back"
case "$job" in
  lint) lint ;;
  check) check ;;
  test) tests "$@" ;;
  sample) sample ;;
  all) lint; check; tests; sample ;;
esac
