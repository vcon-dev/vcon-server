#!/usr/bin/env bash
# Render every docs/diagrams/*.mmd to SVG.
#
# Usage: render_diagrams.sh [output-dir]
#
# Output defaults to the source folder.
#   MMDC              path to mmdc; unset runs mermaid-cli through npx
#   PUPPETEER_CONFIG  optional puppeteer config file passed to mmdc with -p
#   DIAGRAMS_DIR      source folder, default docs/diagrams
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo"

source_dir="${DIAGRAMS_DIR:-docs/diagrams}"
out_dir="${1:-$source_dir}"
theme="docs/diagrams/vconic-theme.json"
init_line="$(head -n 1 docs/diagrams/_init.txt)"

if [[ -n "${MMDC:-}" ]]; then
  mmdc=("$MMDC")
else
  mmdc=(npx --yes @mermaid-js/mermaid-cli@12.2.0)
fi

args=(--quiet -c "$theme" -b white)
if [[ -n "${PUPPETEER_CONFIG:-}" ]]; then
  args+=(-p "$PUPPETEER_CONFIG")
fi

shopt -s nullglob
sources=("$source_dir"/*.mmd)
if [[ ${#sources[@]} -eq 0 ]]; then
  echo "render_diagrams: no .mmd files in $source_dir"
  exit 0
fi

mkdir -p "$out_dir"
failed=()
for source in "${sources[@]}"; do
  name="$(basename "$source" .mmd)"
  if [[ "$(head -n 1 "$source")" != "$init_line" ]]; then
    echo "render_diagrams: $source: first line must match docs/diagrams/_init.txt" >&2
    failed+=("$name")
    continue
  fi
  if ! "${mmdc[@]}" "${args[@]}" -i "$source" -o "$out_dir/$name.svg"; then
    failed+=("$name")
  fi
done

if [[ ${#failed[@]} -gt 0 ]]; then
  echo "render_diagrams: failed: ${failed[*]}" >&2
  exit 1
fi
echo "render_diagrams: rendered ${#sources[@]} diagrams to $out_dir"
