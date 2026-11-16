#!/usr/bin/env bash
# Build the browser's reader (web/src/shared/wasm/ma_law) from crates/ma-wasm. Needs Rust (rustup) and wasm-pack.
# The compiler writes the path of every source file into the module (where a panic was). Those paths are remapped,
# so the file is the same on every machine that builds it and names nobody's home folder.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.cargo/bin:$PATH"
export RUSTFLAGS="${RUSTFLAGS:-} --remap-path-prefix=${CARGO_HOME:-$HOME/.cargo}=/cargo --remap-path-prefix=$here=/crates"
out="$here/../web/src/shared/wasm/ma_law"
(cd "$here/ma-wasm" && wasm-pack build --release --target web --out-dir "$out" --out-name ma_law --no-pack "$@")
rm -f "$out/.gitignore"
