#!/usr/bin/env bash
# The site on the sample, end to end, in one command.
#
#   tools/ci/smoke.sh
#
# It builds the web and the renderer into a temporary folder, makes a new SQLite database there and loads the sample
# into it (the 2011 Constitution and Bulletin issue 7278: manage.py load_sample), then starts the drawing service
# (web/scripts/ssr-server.mjs) and Django (runserver, told where the service is). It asks Django for the
# Constitution's page and for one of its articles, twice each: the law's words must be drawn in the page both times.
# Then web/e2e/smoke.e2e.mjs serves the built web (Vite's preview, the addresses nginx sends to Django sent to Django)
# and walks it in headless Chromium: the home, the law, an article and its French, the issue, a sign-up with the code
# from its letter (written to a file: no mail leaves), a sign-out and a sign-in, with no error in the console.
# Search needs PostgreSQL with ParadeDB and is not part of it.
#
# It needs curl, Node 22 with web/node_modules (`npm ci` in web/) and Playwright's Chromium (`npx playwright install
# chromium` in web/), and the Python environment with the Rust module ma_law (README, «Quick start»), at
# back/.venv/bin/python or $PYTHON. It installs nothing and reaches no network: the ports are free ones chosen when it
# runs, every process it starts is stopped by its id when it ends (on a failure too), and its folder (under $TMPDIR,
# /tmp by default) is removed unless it failed: then the logs' last lines are printed and the folder is kept, with a
# screenshot of each step the browser took and of the page where it failed. Each command is printed before it runs.
set -euo pipefail

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }
case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  '') ;;
  *) usage >&2; exit 2 ;;
esac

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
web="$root/web"
back="$root/back"
PYTHON="${PYTHON:-back/.venv/bin/python}"
case $PYTHON in /*) ;; */*) PYTHON="$root/$PYTHON" ;; esac
started=$SECONDS

run() {
  printf '+ %s\n' "$*"
  "$@"
}

# What it needs, said before anything starts.
[ -d "$web/node_modules" ] || { echo "smoke: web/node_modules is missing: run \`npm ci\` in web/" >&2; exit 1; }
"$PYTHON" -c 'import django, ma_law' 2>/dev/null \
  || { echo "smoke: $PYTHON cannot import django and ma_law: see README, «Quick start»" >&2; exit 1; }
(cd "$web" && node --input-type=module -e "import { chromium } from 'playwright'; await (await chromium.launch()).close();") \
  2>/dev/null || { echo "smoke: Playwright's Chromium does not start: run \`npx playwright install chromium\` in web/" >&2; exit 1; }

work="$(mktemp -d "${TMPDIR:-/tmp}/smoke.XXXXXX")"
pids=''                         # every process started, by id
stop() {
  local status=$? pid
  for pid in $pids; do kill -TERM "$pid" 2>/dev/null || true; done
  for pid in $pids; do
    for _ in $(seq 50); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
    kill -KILL "$pid" 2>/dev/null || true
  done
  if [ "$status" -ne 0 ]; then
    for log in ssr django; do
      [ -f "$work/$log.log" ] && { echo "--- the last lines of $log.log"; tail -n 40 "$work/$log.log"; }
    done
    echo "smoke: FAILED after $((SECONDS - started)) s; its folder is kept: $work" >&2
  else
    rm -rf "$work"
  fi
  exit "$status"
}
trap stop EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Two free ports, both held while they are chosen so that they differ.
free_ports() {
  "$PYTHON" -c 'import socket; s = [socket.socket() for _ in range(2)]; [x.bind(("127.0.0.1", 0)) for x in s]; print(*[x.getsockname()[1] for x in s])'
}

# Until the command after `$1` succeeds, `$1` seconds at most, and only while every process started is alive.
until_ok() {
  local seconds=$1 pid; shift
  for _ in $(seq $((seconds * 5))); do
    "$@" 2>/dev/null && return 0
    for pid in $pids; do kill -0 "$pid" 2>/dev/null || { echo "smoke: process $pid has stopped" >&2; return 1; }; done
    sleep 0.2
  done
  echo "smoke: no answer after $seconds s: $*" >&2
  return 1
}

# Django's environment: each setting that could reach beyond this run is set here, so a developer's .env cannot point
# it at their database, cache, mail service or a paid API.
export DJANGO_SETTINGS_MODULE=config.settings.dev
export DATABASE_URL="sqlite:///$work/db.sqlite3" REDIS_URL= COUNTERS_REDIS_URL=
export CORPUS_DIR="$work/data" UPLOADS_DIR="$work/uploads" WEB_DIST="$work/dist"
export EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend EMAIL_FILE_PATH="$work/letters" RESEND_API_KEY=
export ANTHROPIC_API_KEY= DISCUSSION_CHECK=pass SEARCH_MEANING=False GATE_PASSWORD= REGISTRATION_OPEN=1
export GOOGLE_OAUTH_CLIENT_ID= TURNSTILE_SITE_KEY= TURNSTILE_SECRET_KEY=
mkdir -p "$CORPUS_DIR" "$UPLOADS_DIR" "$EMAIL_FILE_PATH"

echo "== smoke: the web and the renderer, built into $work"
cd "$web"
run node_modules/.bin/vite build --outDir "$work/dist" --emptyOutDir --logLevel warn
run node_modules/.bin/vite build --ssr src/entry-server.tsx --outDir "$work/dist-ssr" --emptyOutDir --logLevel warn

echo "== smoke: a new database, with the sample"
cd "$back"
run "$PYTHON" manage.py migrate -v 0
run "$PYTHON" manage.py load_sample

echo "== smoke: the drawing service and Django"
cd "$web"
printf '+ %s\n' "SSR_PORT=0 SSR_ENTRY=$work/dist-ssr/entry-server.js node scripts/ssr-server.mjs &"
SSR_PORT=0 SSR_ENTRY="$work/dist-ssr/entry-server.js" node scripts/ssr-server.mjs > "$work/ssr.log" 2>&1 &
pids="$pids $!"
until_ok 30 grep -q '^ssr on ' "$work/ssr.log"
ssr_port=$(sed -n 's/^ssr on 127\.0\.0\.1:\([0-9]*\)$/\1/p' "$work/ssr.log")
read -r django_port web_port < <(free_ports)
export SSR_URL="http://127.0.0.1:$ssr_port" SITE_URL="http://127.0.0.1:$web_port"
django="http://127.0.0.1:$django_port"
cd "$back"
printf '+ %s\n' "SSR_URL=$SSR_URL $PYTHON manage.py runserver 127.0.0.1:$django_port --noreload &"
"$PYTHON" manage.py runserver "127.0.0.1:$django_port" --noreload > "$work/django.log" 2>&1 &
pids="$pids $!"
until_ok 60 curl -fsS -o /dev/null "$django/api/auth/register/"

echo "== smoke: Django draws the law's pages through the service"
# The words must be inside the app's root, as drawn: a page's head quotes them too.
drawn() {
  local path=$1 words=$2 html
  html=$(curl -fsS --max-time 30 "$django$path")
  case $html in *'<div id="root" data-prerendered>'*) ;; *) echo "smoke: $path came without its drawing" >&2; return 1 ;; esac
  case ${html#*<div id=\"root\" data-prerendered>} in
    *"$words"*) echo "ok   $path is drawn with «$words»" ;;
    *) echo "smoke: $path is drawn without «$words»" >&2; return 1 ;;
  esac
}
for _ in 1 2; do
  run drawn /ma/dahir/1-11-91 'نظام الحكم بالمغرب نظام ملكية دستورية'
  run drawn /ma/dahir/1-11-91/art_41 'الملك، أمير المؤمنين وحامي حمى الملة والدين'
done

echo "== smoke: the site in a browser"
cd "$web"
mkdir -p "$work/shots"
printf '+ %s\n' "DJANGO=$django LETTERS=$work/letters WEB_DIST=$work/dist WEB_PORT=$web_port SHOTS=$work/shots node e2e/smoke.e2e.mjs"
DJANGO="$django" LETTERS="$work/letters" WEB_DIST="$work/dist" WEB_PORT="$web_port" SHOTS="$work/shots" \
  node e2e/smoke.e2e.mjs &
browser=$!
pids="$pids $browser"
wait "$browser"

echo "== smoke: passed in $((SECONDS - started)) s"
