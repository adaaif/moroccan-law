#!/usr/bin/env bash
# Build ma_law for the server (a wheel installed into back/.venv) and for the browser (web/src/shared/wasm),
# then check both against crates/vectors. Needs Rust (rustup), maturin (in back/.venv) and wasm-pack.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.cargo/bin:$PATH"
cargo test -q --manifest-path "$here/Cargo.toml" -p ma-text -p ma-cite
wheels="$(mktemp -d)"
"$here/../back/.venv/bin/maturin" build --release -q -m "$here/ma-py/Cargo.toml" -o "$wheels"
"$here/../back/.venv/bin/pip" install -q --force-reinstall "$wheels"/ma_law-*.whl
rm -rf "$wheels"
"$here/build-wasm.sh" >/dev/null     # its errors still show
# What the reader was built from, for the deploy's check (a change that leaves the built files as they were, such as a
# comment's, still moves this line).
"$here/source-hash.sh" > "$here/../web/src/shared/wasm/ma_law/SOURCE"
(cd "$here/../web" && node scripts/check-ma-law.mjs)
(cd "$here/../back" && .venv/bin/python -m pytest apps/search/tests/test_ma_law.py -q -n0 | tail -1)
