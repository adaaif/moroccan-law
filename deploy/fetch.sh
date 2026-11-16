#!/usr/bin/env bash
# The morning job (law-fetch.timer): the Arabic Bulletin's new issues fetched from the SGG and read
# (manage.py fetch_new_issues), with an API key of their own: the site itself runs without one. At most $1 a run;
# OCR_BUDGET_USD in ROOT/fetch.env caps the total. Both files are written on the server; without the key the run says
# so and fetches nothing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"          # this script is ROOT/app/deploy/fetch.sh
cd "$ROOT/app/back"
set -a; . "$ROOT/.env"; [ -f "$ROOT/fetch.env" ] && . "$ROOT/fetch.env"; set +a
[ -s "$ROOT/fetch.key" ] || { echo "no $ROOT/fetch.key: nothing fetched"; exit 0; }
ANTHROPIC_API_KEY="$(cat "$ROOT/fetch.key")" "$ROOT/venv/bin/python" manage.py fetch_new_issues --fetch --write --per-run 1
# The search's index merged after the fetch too: the night's merge runs before this fetch, and an issue loaded here
# would leave its replaced entries in the index for the whole day. Searches go on and kept answers stay while it runs
# (merge_search_index leaves the answers' generation alone).
"$ROOT/venv/bin/python" manage.py merge_search_index
