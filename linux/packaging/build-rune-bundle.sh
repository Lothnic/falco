#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
out_dir="${FALCO_RUNE_OUT:-$source_dir/dist}"
version="$(sed -n 's/^version = "\([0-9.]*\)"$/\1/p' "$source_dir/pyproject.toml")"
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 && -n "$version" ]]
cargo build --release --locked --manifest-path "$source_dir/rune-overlay/Cargo.toml"
built="$source_dir/rune-overlay/target/release"
[[ "$("$built/phonon-window" --version)" == "$version" ]]
printf '%s\n' "$version" > "$built/VERSION"
mkdir -p "$out_dir"
archive="falco-rune-v$version-linux-x86_64.tar.gz"
tar -czf "$out_dir/$archive" -C "$built" phonon-window phonon-overlay VERSION
(cd "$out_dir" && sha256sum "$archive" > SHA256SUMS.txt)
printf 'Rune bundle: %s/%s\n' "$out_dir" "$archive"
