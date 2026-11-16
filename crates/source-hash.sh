#!/usr/bin/env bash
# One line that names what the citation reader is built from: the crates' code, their test vectors and the lock, as
# committed at HEAD. crates/build.sh writes it beside the browser's reader (web/src/shared/wasm/ma_law/SOURCE);
# deploy/deploy.sh compares the two, so a deploy stops when the committed reader was not built from these sources.
set -euo pipefail
cd "$(dirname "$0")/.."
git ls-files -z -- crates/ma-text/src crates/ma-cite/src crates/ma-wasm/src crates/vectors crates/Cargo.lock \
  | LC_ALL=C sort -z | xargs -0 git hash-object | sha256sum | cut -d' ' -f1
