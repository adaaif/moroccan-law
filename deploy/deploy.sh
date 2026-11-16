#!/usr/bin/env bash
# Deploy the site to its server: the commit at HEAD, never uncommitted work. The web is built here; the server gets the
# code, the built pages and the Rust wheel, installs, migrates, and restarts.
#
#   deploy/deploy.sh [--system] [--host HOST]
#
#   --system   also nginx and its log's rotation, the systemd units and the tunnel's config (sudo on the server)
#   --host     the server, as ssh names it (or HOST in the environment)
#
# Four values, none with a default, from the environment or from deploy/private/site.sh when that file is there (a
# private file: the public tree leaves deploy/private/ out):
#   HOST       the server, as ssh names it
#   RUN_USER   the account the services run as
#   ROOT       the folder on the server that holds everything (below)
#   DOMAIN     the site's address, without https:// (example.org)
# The units, nginx.conf and tunnel.yml in deploy/ are templates: @USER@, @ROOT@ and @DOMAIN@ are written in on the
# server before they are installed. deploy/private/ may add nginx-*.conf (more server blocks, such as other names that
# lead to the site) and its own tunnel.yml (used in place of deploy/tunnel.yml).
#
# The server's layout, ROOT: app/ (back/, deploy/, web/dist/), venv/, .env (secrets, mode 600, written on the server),
# data/ (CORPUS_DIR), models/, uploads/, pg/ (compose.yml's Postgres), compose.yml.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f deploy/private/site.sh ] && . deploy/private/site.sh

system=
while [ $# -gt 0 ]; do
  case $1 in
    --system) system=--system ;;
    --host) HOST=${2:?--host needs a name}; shift ;;
    *) echo "usage: $0 [--system] [--host HOST]" >&2; exit 2 ;;
  esac
  shift
done
for name in HOST RUN_USER ROOT DOMAIN; do
  [ -n "${!name:-}" ] || { echo "== $name is not set (environment, --host, or deploy/private/site.sh)" >&2; exit 2; }
done

commit=$(git rev-parse --short HEAD)
echo "== $commit to $HOST"
# ROOT is the folder that already holds the server's .env: a deploy never makes a new one beside it (a ROOT naming the
# wrong folder would get a fresh venv and stop at .env, with the site's units still pointing at the right one).
ssh "$HOST" "test -f $ROOT/.env" || { echo "== $HOST has no $ROOT/.env: ROOT names no deployed folder" >&2; exit 2; }
# back/ and deploy/ whole, as committed: archived as subtrees, so the root .gitattributes (which keeps private paths
# out of the public tree) does not apply to the server's copy.
pack=$(mktemp -d)
trap 'rm -rf "$pack"' EXIT
git archive --format=tar --prefix=back/ -o "$pack/app.tar" HEAD:back
git archive --format=tar --prefix=deploy/ -o "$pack/deploy.tar" HEAD:deploy
tar -A -f "$pack/app.tar" "$pack/deploy.tar"
ssh "$HOST" "rm -rf $ROOT/app.new && mkdir -p $ROOT/app.new && tar -x -C $ROOT/app.new" < "$pack/app.tar"
(cd web && npm run build >/dev/null)
# The renderer, with its packages: the prerender below and the law-ssr service, which draws every other law's page for
# Django, run it with node alone.
(cd web && npm run build:ssr >/dev/null)
# The named texts' pages with their words, read from the server's own answers: a few minutes; a failure leaves
# Django's heads alone in place of them. Asked of its nginx over ssh (one shared connection; the server's sshd need
# forward no port): a request from the machine itself is the server's own.
link="$pack/ssh.sock"
if ssh -fN -M -S "$link" "$HOST"; then
  (cd web && NAMED=1 API_SSH=$HOST API_SSH_SOCKET=$link SITE_URL=https://$DOMAIN \
    node scripts/prerender.mjs) || echo "== prerender skipped: Django answers every law's address with its head"
  ssh -S "$link" -O exit "$HOST" 2>/dev/null || true
else
  echo "== prerender skipped (no ssh): Django answers every law's address with its head"
fi

rsync -az --delete --mkpath web/dist/ "$HOST:$ROOT/app.new/web/dist/"
rsync -az --mkpath web/dist-ssr/entry-server.js web/dist-ssr/assets "$HOST:$ROOT/app.new/web/dist-ssr/"
rsync -az --mkpath web/scripts/ssr-server.mjs "$HOST:$ROOT/app.new/web/scripts/"
# The last build's files stay a week beside the new ones: a tab or the installed app opened before the deploy still
# finds the page it asks for; a file newer than the week is never removed.
ssh "$HOST" "[ -d $ROOT/app/web/dist/assets ] && rsync -a --ignore-existing $ROOT/app/web/dist/assets/ $ROOT/app.new/web/dist/assets/ \
  && find $ROOT/app.new/web/dist/assets -type f -mtime +7 -delete || true"
# The Rust reader the server runs (ma_law: folding, citations), built here from the crates at HEAD, so that the server
# and the browser read citations alike. The browser's reader is committed (web/src/shared/wasm) with a line naming
# the sources it was built from (crates/source-hash.sh: the crates' code, their vectors and the lock; a manifest's
# licence line changes no build): built from other sources, the deploy stops; crates/build.sh builds both, checks
# them against crates/vectors and writes the line.
git diff --quiet HEAD -- crates web/src/shared/wasm || { echo "== crates/ or the browser's reader has uncommitted changes: commit them first"; exit 1; }
if [ "$(crates/source-hash.sh)" != "$(cat web/src/shared/wasm/ma_law/SOURCE 2>/dev/null)" ]; then
  echo "== the browser's reader (web/src/shared/wasm) was not built from crates/ as committed: run crates/build.sh and commit it"; exit 1
fi
rm -f crates/target/wheels/ma_law-*.whl
PATH="$HOME/.cargo/bin:$PATH" back/.venv/bin/maturin build --release -q -m crates/ma-py/Cargo.toml -o crates/target/wheels >/dev/null
rsync -a crates/target/wheels/ma_law-*.whl "$HOST:$ROOT/app.new/"
echo "$commit" | ssh "$HOST" "cat > $ROOT/app.new/COMMIT"

ssh "$HOST" "ROOT=$(printf %q "$ROOT") RUN_USER=$(printf %q "$RUN_USER") DOMAIN=$(printf %q "$DOMAIN") SYSTEM=$system bash -s" <<'EOF'
set -euo pipefail
cd "$ROOT"
[ -d venv ] || python3 -m venv venv
# base.txt builds ma_law from ../crates; the server takes the wheel built with it. prod.txt adds the server's own
# packages (gunicorn).
grep -hv -e '^\.\./crates' -e '^-r ' app.new/back/requirements/base.txt app.new/back/requirements/prod.txt \
  > app.new/requirements.txt
venv/bin/pip install -q -r app.new/requirements.txt
venv/bin/pip install -q --force-reinstall --no-deps app.new/ma_law-*.whl
rm -rf app.old
[ -d app ] && mv app app.old
mv app.new app
cd app/back
set -a; . "$ROOT/.env"; set +a
"$ROOT/venv/bin/python" manage.py migrate --noinput
"$ROOT/venv/bin/python" manage.py collectstatic --noinput -v 0
"$ROOT/venv/bin/python" manage.py check --deploy --fail-level ERROR
# The issues' Hijri dates from their mastheads: only those without one, free.
"$ROOT/venv/bin/python" manage.py read_hijri_dates --write
# The discussions counted from what a reader may see.
"$ROOT/venv/bin/python" manage.py recount_discussions
# Words a stray space cut in two, proposed for a person on /corrections; never applied here.
"$ROOT/venv/bin/python" manage.py proofread --split
chmod 711 "$ROOT"           # nginx passes through to app/web/dist and app/back/staticfiles; .env stays 600
# A template from deploy/, with this server's values written in.
render() { sed -e "s|@USER@|$RUN_USER|g" -e "s|@ROOT@|$ROOT|g" -e "s|@DOMAIN@|$DOMAIN|g" "$1"; }
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# What nginx says to search engines: "noindex, nofollow" on every page until INDEXING=open in .env; deploy/nginx.conf
# includes the file. Reloaded only when it changed.
idx='noindex, nofollow'; [ "${INDEXING:-closed}" = open ] && idx=''
printf 'map $host $law_index { default "%s"; }\n' "$idx" > "$work/indexing.conf"
indexing_changed=
if ! sudo cmp -s "$work/indexing.conf" /etc/nginx/law-indexing.conf; then
  sudo install -m 644 "$work/indexing.conf" /etc/nginx/law-indexing.conf
  indexing_changed=1
fi
# Whether nginx asks Django's gate before a file: never while GATE_PASSWORD is empty, so the files and the prepared
# pages are served while Django restarts; deploy/nginx.conf includes the file. Reloaded only when it changed.
gate=open; [ -n "${GATE_PASSWORD:-}" ] && gate=closed
printf 'map $host $law_gate { default "%s"; }\n' "$gate" > "$work/gate.conf"
gate_changed=
if ! sudo cmp -s "$work/gate.conf" /etc/nginx/law-gate.conf; then
  sudo install -m 644 "$work/gate.conf" /etc/nginx/law-gate.conf
  gate_changed=1
fi
if [ "$SYSTEM" = --system ]; then
  # Tesseract finds an article's place on its printed page.
  command -v tesseract >/dev/null || sudo apt-get install -y -q tesseract-ocr tesseract-ocr-ara tesseract-ocr-fra
  sudo install -m 644 ../deploy/nginx-headers.conf /etc/nginx/law-headers.conf     # the headers every answer carries
  render ../deploy/nginx.conf > "$work/nginx.conf"
  sudo install -m 644 "$work/nginx.conf" /etc/nginx/sites-available/law
  # More server blocks of this server's own (deploy/private/nginx-*.conf), included by nginx.conf.
  sudo mkdir -p /etc/nginx/law-sites
  sudo find /etc/nginx/law-sites -maxdepth 1 -name '*.conf' -delete
  for extra in ../deploy/private/nginx-*.conf; do
    [ -f "$extra" ] || continue
    render "$extra" > "$work/$(basename "$extra")"
    sudo install -m 644 "$work/$(basename "$extra")" /etc/nginx/law-sites/
  done
  sudo ln -sf /etc/nginx/sites-available/law /etc/nginx/sites-enabled/law
  sudo rm -f /etc/nginx/sites-enabled/default
  # The site's access log (log_format law in nginx.conf: no query string) in a folder of its own, rotated by its own rule
  # and kept 7 days (deploy/logrotate-nginx); the stock rule (/var/log/nginx/*.log, 14 days) does not reach into it.
  # The folder has the stock one's rights: nginx's master, as root, makes the file and logrotate, as root, renames it;
  # the workers and the adm group (the nightly count, as the site's account) pass through to the file, 0640 www-data:adm.
  sudo install -d -o root -g adm -m 755 /var/log/nginx/law
  # The file made before nginx first opens it: nginx's master would make it root's and readable by every account of the
  # machine until the first rotation gave it the rule's rights.
  sudo test -e /var/log/nginx/law/access.log || sudo install -o www-data -g adm -m 640 /dev/null /var/log/nginx/law/access.log
  sudo install -m 644 ../deploy/logrotate-nginx /etc/logrotate.d/law-nginx
  # nginx sends the database's files from the editions' folder (location /_open/ in nginx.conf, OPEN_DATA_ACCEL in
  # .env): it passes through data/ without listing it, and reads the folders and files the export makes readable.
  mkdir -p "$ROOT/data/open"
  chmod 711 "$ROOT/data"
  chmod 755 "$ROOT/data/open"
  sudo nginx -t
  mkdir "$work/units"
  for unit in ../deploy/*.service ../deploy/*.timer; do render "$unit" > "$work/units/$(basename "$unit")"; done
  sudo install -m 644 "$work"/units/* /etc/systemd/system/
  # The tunnel's names (tunnel.yml, or this server's own in deploy/private/): written, and the tunnel restarted, only
  # when they changed (a few seconds without it).
  tunnel=../deploy/tunnel.yml; [ -f ../deploy/private/tunnel.yml ] && tunnel=../deploy/private/tunnel.yml
  id=$(sudo sed -n 's/^tunnel: //p' /etc/cloudflared/law.yml 2>/dev/null || true)
  tunnel_changed=
  if [ -n "$id" ]; then
    render "$tunnel" | sed "s/TUNNEL_ID/$id/g" > "$work/tunnel.yml"
    if ! sudo cmp -s "$work/tunnel.yml" /etc/cloudflared/law.yml; then
      sudo install -m 644 "$work/tunnel.yml" /etc/cloudflared/law.yml
      tunnel_changed=1
    fi
  fi
  sudo systemctl daemon-reload
  sudo systemctl enable -q law-models law-web law-mcp law-ssr nginx
  # The tunnel's unit, once its file holds the tunnel's id (written when the tunnel was made).
  if [ -n "$id" ]; then sudo systemctl enable -q cloudflared-law; fi
  sudo systemctl enable -q --now law-regions.timer      # the pages' word boxes at night
  sudo systemctl enable -q --now law-nightly.timer      # what /privacy promises to erase, and the database dumped
  sudo systemctl enable -q --now law-digest.timer       # the moderators' letter about what waited
  sudo systemctl enable -q --now law-fetch.timer        # the Bulletin's new issues fetched and read
  sudo systemctl enable -q --now law-letters.timer      # the discussion's letters, sent by a job, never in a request
  # The Monday letter of the week's counts: on only while ANALYTICS_LETTER_TO names an address in .env (off since
  # 16 Nov 2026). With none, its timer is stopped, so a deploy never turns the letter back on.
  if [ -n "${ANALYTICS_LETTER_TO:-}" ]; then sudo systemctl enable -q --now law-analytics-letter.timer
  else sudo systemctl disable -q --now law-analytics-letter.timer; fi
  sudo systemctl enable -q --now law-edition.timer      # the database's edition, on the first day of each month
  sudo systemctl reload nginx
  if [ -n "$tunnel_changed" ]; then sudo systemctl restart cloudflared-law; echo "== the tunnel's names changed: restarted"
  elif [ -n "$id" ]; then sudo systemctl start cloudflared-law; fi
elif [ -n "$indexing_changed$gate_changed" ]; then
  sudo nginx -t && sudo systemctl reload nginx
fi
[ -n "$indexing_changed" ] && echo "== search engines: ${INDEXING:-closed}"
[ -n "$gate_changed" ] && echo "== the gate: $gate"
sudo systemctl restart law-models law-web
# The law's pages' renderer, once its unit is installed (deploy.sh --system).
if [ -f /etc/systemd/system/law-ssr.service ]; then sudo systemctl restart law-ssr; fi
# The assistants' MCP server, once its unit is installed (deploy.sh --system).
if [ -f /etc/systemd/system/law-mcp.service ]; then sudo systemctl restart law-mcp; fi
for i in $(seq 1 30); do curl -s -o /dev/null http://127.0.0.1:8040/gate/check/ && break; sleep 1; done
echo "web: $(curl -s -o /dev/null -w '%{http_code}' -H "Host: $DOMAIN" http://127.0.0.1:8041/)"
# Its workers warm their search before they answer (config/mcp_asgi.py), and refuse until then.
for i in $(seq 1 90); do
  mcp=$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "Host: $DOMAIN" -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' -H 'MCP-Protocol-Version: 2025-06-18' \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' http://127.0.0.1:8041/mcp)
  { [ "$mcp" = 200 ] || [ "$mcp" = 401 ]; } && break
  sleep 1
done
echo "mcp: $mcp after ${i} s (200 expected; 401 when MCP_AUTH=required)"
# The detached jobs below write their logs here.
mkdir -p "$ROOT/logs"
# The week's most shown pages asked again before readers ask, detached: a few minutes.
setsid nice -n 10 "$ROOT/venv/bin/python" manage.py warm_answers >> "$ROOT/logs/warm.log" 2>&1 < /dev/null &
# The search's index merged after whatever was loaded since the night, detached; searches go on and kept answers stay.
setsid nice -n 10 "$ROOT/venv/bin/python" manage.py merge_search_index >> "$ROOT/logs/merge_index.log" 2>&1 < /dev/null &
# The search engines' published crawlers, then the sitemaps (nightly too), detached: a minute or two.
setsid nice -n 10 sh -c '"$ROOT/venv/bin/python" manage.py refresh_crawlers; "$ROOT/venv/bin/python" manage.py write_sitemaps' \
  >> "$ROOT/logs/sitemaps.log" 2>&1 < /dev/null &
# The named texts' printed pages drawn ahead of their first reader, detached and at the lowest priority: long the first
# time, then only what is new. One run at a time: a deploy while the last one still draws leaves it to finish.
if ! { [ -f "$ROOT/logs/draw_pages.pid" ] && kill -0 "$(cat "$ROOT/logs/draw_pages.pid")" 2>/dev/null; }; then
  setsid nice -n 19 "$ROOT/venv/bin/python" manage.py draw_pages >> "$ROOT/logs/draw_pages.log" 2>&1 < /dev/null &
  echo $! > "$ROOT/logs/draw_pages.pid"
fi
EOF
echo "== $commit is on $HOST"
