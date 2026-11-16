#!/usr/bin/env bash
# The web's CI jobs, one command each, the same on a developer's machine and in CI.
#
#   tools/ci/web.sh lint|types|test|build|budget|ssr|all
#
#   lint     eslint, with no warning allowed
#   types    TypeScript's project build (tsc -b)
#   test     the unit tests (Node's test runner) and the browser's reader against the shared vectors (crates/vectors)
#   build    the site's build into web/dist
#   budget   what a first visit downloads, against its budget (needs `build` first)
#   ssr      the renderer's build into web/dist-ssr, then loaded with Node alone
#   all      every job above, in that order
#
# It needs Node 22 and web/node_modules (`npm ci` in web/). It installs nothing and reaches no network. Each command is
# printed before it runs; the first that fails stops the script with its exit status.
set -euo pipefail

# The comment at the top of this file, as the help.
usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
web="$root/web"

run() {
  printf '+ %s\n' "$*"
  "$@"
}

need_modules() {
  if [ ! -d "$web/node_modules" ]; then
    echo "web.sh: web/node_modules is missing: run \`npm ci\` in web/ first" >&2
    exit 1
  fi
}

lint() { run npm run lint; }
types() { run npm run typecheck; }
unit() {
  run node --test --test-reporter=spec tests/*.test.ts
  run npm run test:ma-law
}
build() { run npm run build; }
budget() {
  if [ ! -f "$web/dist/index.html" ]; then
    echo "web.sh: no build in web/dist: run \`tools/ci/web.sh build\` first" >&2
    exit 1
  fi
  run npm run check:budget
}
ssr() {
  run npm run build:ssr
  # The renderer must load with Node alone (its packages are bundled: vite.config.ts, ssr.noExternal) and give `render`.
  run node --input-type=module -e "const m = await import('./dist-ssr/entry-server.js'); if (typeof m.render !== 'function') throw new Error('dist-ssr/entry-server.js gives no render()'); console.log('the renderer loads with Node alone')"
}

# One job, with its name and time around it.
job() {
  local name=$1 started=$SECONDS
  echo "== web: $name"
  case $name in
    lint) lint ;;
    types) types ;;
    test) unit ;;
    build) build ;;
    budget) budget ;;
    ssr) ssr ;;
  esac
  echo "== web: $name passed in $((SECONDS - started)) s"
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  lint|types|test|build|budget|ssr) [ $# -eq 1 ] || { usage >&2; exit 2; } ;;
  all) [ $# -eq 1 ] || { usage >&2; exit 2; } ;;
  *) usage >&2; exit 2 ;;
esac

need_modules
cd "$web"
if [ "$1" = all ]; then
  for name in lint types test build budget ssr; do job "$name"; done
else
  job "$1"
fi
