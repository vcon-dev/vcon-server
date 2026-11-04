#!/usr/bin/env bash
# Check the docs against the code. CI runs this, and it is safe to run locally.
#
# 1. Runs the generators and fails if a generated page differs from git.
# 2. Renders every diagram to a temp folder to catch syntax errors. It does not
#    compare SVG bytes, since mermaid-cli output is not stable between runs.
# 3. Builds the site with mkdocs build --strict.
#
# A regenerated page stays on disk. Stage or commit it and the check passes.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo"

generators=(gen_env.py gen_ports.py gen_routes.py gen_metrics.py)
pages=(
  docs/reference/environment.md
  docs/reference/ports.md
  docs/reference/api-routes.md
  docs/reference/metrics.md
)

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "== generators"
for generator in "${generators[@]}"; do
  uv run -q --no-project --python 3.12 --with pyyaml python "scripts/docs/$generator"
done

if ! git diff --exit-code --stat -- "${pages[@]}"; then
  echo "check: generated pages are out of date. Review and commit them." >&2
  exit 1
fi

untracked="$(git ls-files --others --exclude-standard -- "${pages[@]}")"
if [[ -n "$untracked" ]]; then
  if [[ -n "${CI:-}" ]]; then
    echo "check: generated pages are not committed:" >&2
    echo "$untracked" >&2
    exit 1
  fi
  echo "check: note, generated pages are not in git yet, so no diff was checked:"
  echo "$untracked"
fi

echo "== diagrams"
scripts/docs/render_diagrams.sh "$tmp/diagrams"

echo "== mkdocs"
NO_MKDOCS_2_WARNING=1 uvx --with mkdocs-material mkdocs build --strict -q -d "$tmp/site"

echo "check: passed"
