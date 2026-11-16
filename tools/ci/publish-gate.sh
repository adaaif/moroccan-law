#!/usr/bin/env bash
# The publishing gate, in the private repository only: the public tree of a commit is written as a draft into a
# temporary folder (tools/publish/export.sh --draft) and scanned for private material (tools/publish/scan.py).
#
#   tools/ci/publish-gate.sh [commit]        the commit defaults to HEAD
#
# It stops with a failure when the export itself fails, when a private path reached the tree, or when the scan finds
# a line of a `fail` class. The placeholders still to fill ([[…]] in capitals: the copyright holder, the contacts)
# are expected until the public repository opens: they are listed, and do not fail it.
#
# It needs the private word list (tools/publish/private-words.txt), which a public clone does not have. It installs
# nothing and needs no network. PYTHON names the interpreter for the scan (default back/.venv/bin/python); the scan
# uses the standard library only.
set -euo pipefail

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"; }
run() { printf '+'; printf ' %q' "$@"; printf '\n'; "$@"; }

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  -*) usage >&2; exit 2 ;;
esac
[ $# -le 1 ] || { usage >&2; exit 2; }

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "+ cd $root"
cd "$root"
commit=${1:-HEAD}
python=${PYTHON:-back/.venv/bin/python}

command -v "$python" > /dev/null || {
  echo "publish-gate: no Python at $python: set PYTHON (any Python 3: the scan needs only the standard library)" >&2
  exit 1
}

tree="$(mktemp -d)"
log="$(mktemp)"
trap 'rm -rf "$tree" "$log"' EXIT

# 1. The draft export. With --draft, export.sh keeps the tree whatever its own gates say and answers 0, so its
#    verdicts are read from what it prints; it answers non-zero only when it could not write the tree at all.
run tools/publish/export.sh --draft "$commit" "$tree/public" 2>&1 | tee "$log"

# export.sh names each private path it finds in the tree («… is in the tree», «… are in the tree»).
if grep -qE '^export: .* (is|are) in the tree$' "$log"; then
  echo "publish-gate: private paths reached the public tree (above): .gitattributes must mark them export-ignore" >&2
  exit 1
fi

# 2. The scan, run again on the tree for its exit status (1 when a line of a `fail` class is there); the export's run
#    above has listed every line it found.
status=0
run "$python" tools/publish/scan.py --root "$tree/public" "$tree/public" || status=$?
case $status in
  0) ;;
  1) echo "publish-gate: the scan found lines that must change before publishing (listed above)" >&2; exit 1 ;;
  *) echo "publish-gate: the scan did not run to its end (exit status $status)" >&2; exit "$status" ;;
esac

# 3. The placeholders: expected for now, listed so that none is forgotten.
placeholders=$(grep -rIlE '\[\[[A-Z][A-Z0-9 _-]+\]\]' "$tree/public" | sed "s|^$tree/public/||" | sort || true)
if [ -n "$placeholders" ]; then
  echo "publish-gate: placeholders still to fill before the public repository opens (expected for now):"
  while IFS= read -r file; do echo "  $file"; done <<<"$placeholders"
fi

echo "publish-gate: the public tree of $(git rev-parse --short "$commit") passed"
