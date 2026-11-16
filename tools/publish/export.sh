#!/usr/bin/env bash
# Write the public tree of a commit into a directory, then check it. Nothing is pushed and no remote is made: what
# happens to the directory afterwards is a person's decision.
#
#   tools/publish/export.sh [--draft] <commit> <target dir>
#
# The tree is `git archive` of the commit: every path the commit's .gitattributes marks export-ignore is left out
# (the working notes, operations scripts, private test sets, the private deploy values, this tool's word list). Two
# gates then read the result:
#   1. tools/publish/scan.py: no line of a `fail` class from the private word list (names of people, machines, paths,
#      secrets' places…). It needs that list, so the export refuses to run where the list is absent.
#   2. No placeholder left: a name or an address still to be decided, written in capitals between double square
#      brackets.
# A gate that fails removes the directory and the export answers 1. With --draft the directory is kept whatever the
# gates say (to build and test the tree before it is ready); a draft is never published.
#
# To start the public repository from the tree, as one commit (after reading it):
#   cd <target dir> && git init -b main && git add -A && git commit -m "First public version"
set -euo pipefail

draft=
if [ "${1:-}" = --draft ]; then draft=1; shift; fi
if [ $# -ne 2 ]; then
  echo "usage: $0 [--draft] <commit> <target dir>" >&2
  exit 2
fi
commit=$1
target=$2
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(git -C "$here" rev-parse --show-toplevel)"

[ -f "$here/private-words.txt" ] || { echo "export: no private word list beside scan.py: the tree cannot be checked" >&2; exit 1; }
sha=$(git -C "$repo" rev-parse --verify --quiet "$commit^{commit}") || { echo "export: $commit is not a commit" >&2; exit 2; }
git -C "$repo" cat-file -e "$sha:.gitattributes" 2>/dev/null \
  || { echo "export: $commit has no .gitattributes, so nothing would be left out" >&2; exit 1; }
if [ -e "$target" ] && [ -n "$(ls -A "$target" 2>/dev/null)" ]; then
  echo "export: $target is not empty" >&2
  exit 2
fi

mkdir -p "$target"
target="$(cd "$target" && pwd)"
git -C "$repo" archive --format=tar "$sha" | tar -x -C "$target"
echo "export: $(git -C "$repo" rev-parse --short "$sha") written to $target ($(find "$target" -type f | wc -l) files)"

failed=
# What the archive must have left out, said again: a commit whose .gitattributes lost a line fails here.
for private in CLAUDE.md HANDOFF.md back/CLAUDE.md web/CLAUDE.md back/scripts_run_queue.sh \
    deploy/pull-backup.sh deploy/private back/apps/discussion/checkset back/apps/search/goldset/road.json \
    back/apps/analytics/data/past_counts.json .github/dependabot.yml \
    tools/publish/private-words.txt .gitattributes; do
  if [ -e "$target/$private" ]; then echo "export: $private is in the tree" >&2; failed=1; fi
done
if compgen -G "$target/back/apps/quality/data/pages_reread_*" >/dev/null; then
  echo "export: the pages read again are in the tree" >&2; failed=1
fi

python3 "$here/scan.py" --list --root "$target" "$target" || failed=1

placeholders=$(grep -rIlE '\[\[[A-Z][A-Z0-9 _-]+\]\]' "$target" || true)
if [ -n "$placeholders" ]; then
  echo "export: placeholders still to fill, in:" >&2
  sed "s|^$target/|  |" <<<"$placeholders" >&2
  failed=1
fi

if [ -n "$failed" ]; then
  if [ -n "$draft" ]; then
    echo "export: DRAFT kept at $target: not for publishing until the lines above are gone" >&2
    exit 0
  fi
  rm -rf "$target"
  echo "export: refused; nothing kept" >&2
  exit 1
fi
echo "export: the tree passed both gates"
