#!/usr/bin/env bash
# Materialize demo/land-title/ as a fresh git repo with no ontology and no hooks,
# the "existing codebase" the talk starts from. Re-running it starts over.
#
#   demo/reset.sh                 -> ~/Projects/land-title
#   DEMO_DIR=/tmp/lt demo/reset.sh
#
# The copy is its own repo on purpose: the ontology checker roots on the
# nearest .git, so a copy nested inside this plugin repo would install its
# hooks and ontology/ here instead.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/land-title"
DEST="${DEMO_DIR:-$HOME/Projects/land-title}"
MARK=".git/land-title-demo"

if [ -e "$DEST" ]; then
  if [ ! -f "$DEST/$MARK" ]; then
    echo "refusing to delete $DEST: it is not a copy this script made" >&2
    exit 1
  fi
  (cd "$DEST" && docker compose down -v >/dev/null 2>&1 || true)
  rm -rf "$DEST"
fi

mkdir -p "$(dirname "$DEST")"
rsync -a --exclude .venv --exclude __pycache__ --exclude .pytest_cache "$SRC/" "$DEST/"
cd "$DEST"
git init -q -b main
git add -A
git commit -q -m "Title chain, ownership traversal, lease and well queries"
touch "$MARK"
uv sync -q

cat <<MSG
land-title is at $DEST (fresh repo, 1 commit, no ontology)

next:
  cd $DEST
  docker compose up -d --wait
  uv run pytest
then open $DEST in Claude Code and follow demo/README.md
MSG
