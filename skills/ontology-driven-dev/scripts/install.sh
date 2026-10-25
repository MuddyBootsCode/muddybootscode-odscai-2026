#!/usr/bin/env bash
# Install the ontology-driven-dev skill into the current repo:
#   1. copy this skill to .claude/skills/ontology-driven-dev/
#   2. merge hooks into .claude/settings.json (preserves existing hooks)
#   3. install a git pre-commit hook that validates and runs --changed --staged
#   4. seed ontology/ from the template if it doesn't exist
#
# Run from anywhere inside the repo:  bash <path-to-skill>/scripts/install.sh
set -euo pipefail

SKILL_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
DEST="$REPO/.claude/skills/ontology-driven-dev"
SETTINGS="$REPO/.claude/settings.json"

echo "repo:  $REPO"
echo "skill: $DEST"

# 1. copy skill
mkdir -p "$DEST"
if [ "$SKILL_SRC" != "$DEST" ]; then
  cp -R "$SKILL_SRC"/. "$DEST"/
fi
chmod +x "$DEST"/scripts/*.py "$DEST"/scripts/*.sh 2>/dev/null || true

# 2. merge hooks (python so we don't need jq)
mkdir -p "$REPO/.claude"
python3 - "$SETTINGS" "$DEST/assets/hooks.settings.json" <<'PY'
import json, sys, pathlib
settings_path, hooks_path = map(pathlib.Path, sys.argv[1:3])
settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
new = json.loads(hooks_path.read_text())["hooks"]
hooks = settings.setdefault("hooks", {})
# Older installs ran the Stop hook without --stop, which can block Claude from
# stopping forever. Drop that entry so the new one replaces it.
OLD_STOP = "python3 .claude/skills/ontology-driven-dev/scripts/ontology_check.py --changed"
if "Stop" in hooks:
    hooks["Stop"] = [e for e in hooks["Stop"] if not any(h.get("command") == OLD_STOP for h in e.get("hooks", []))]
for event, entries in new.items():
    existing = hooks.setdefault(event, [])
    for entry in entries:
        marker = entry["hooks"][0]["command"]
        if not any(marker == h.get("command") for e in existing for h in e.get("hooks", [])):
            existing.append(entry)
settings_path.write_text(json.dumps(settings, indent=2) + "\n")
print(f"hooks: merged into {settings_path}")
PY

# 3. git hooks: pre-commit validates structure; commit-msg runs the change gate
#    (commit-msg, not pre-commit, because it receives the message file and can
#    honor an `ontology-skip: <reason>` line)
#    Ask git for the hooks folder instead of assuming .git/hooks: this honors
#    core.hooksPath, and in a worktree .git is a file, not a folder. Every
#    worktree shares that folder, so each hook skips itself on a branch that
#    doesn't carry the checker instead of failing the commit.
HOOKS_DIR="$(git -C "$REPO" rev-parse --path-format=absolute --git-path hooks 2>/dev/null)" \
  || { echo "git:   not a git repo, git hooks NOT installed" >&2; exit 1; }
mkdir -p "$HOOKS_DIR"
MARK="# ontology-driven-dev"
CHECK=".claude/skills/ontology-driven-dev/scripts/ontology_check.py"
# Put a block into a hook file. A hook that hands off to a framework
# (`exec pre-commit hook-impl ...`) or bails early (`exit 0`) never reaches
# text appended after that line, so the block goes before the first `exec`
# or `exit`. When that line is indented (inside an `if`), the block goes
# before the unindented statement that encloses it, so it runs whether or
# not the condition holds. With neither, the block is appended.
install_block() {  # $1 hook path, $2 block text
  [ -f "$1" ] || echo '#!/usr/bin/env bash' > "$1"
  python3 - "$1" "$2" <<'PY'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1]); block = sys.argv[2].rstrip("\n") + "\n"
lines = p.read_text().splitlines(keepends=True)
hit = next((i for i, l in enumerate(lines) if re.match(r"^\s*(exec|exit)(\s|$)", l)), None)
if hit is not None:
    i = hit
    if lines[i][0] in " \t":  # indented: back up to the enclosing top-level statement
        while i > 0 and (lines[i][0] in " \t" or not lines[i].strip() or lines[i].startswith("#")):
            i -= 1
    while i > 0 and lines[i-1].startswith("#"):  # keep a comment with its statement
        i -= 1
    lines[i:i] = [block, "\n"]
    p.write_text("".join(lines))
    print(f"git:   {p.name}: block inserted before line {i+1} (`{lines[i+2].strip()[:50]}` encloses `{lines[hit+2].strip()[:40]}`)" if i != hit else f"git:   {p.name}: block inserted before line {i+1} (`{lines[hit+2].strip()[:50]}`)")
else:
    p.write_text("".join(lines).rstrip("\n") + "\n\n" + block)
    print(f"git:   {p.name}: block appended")
PY
  chmod +x "$1"
}

HOOK="$HOOKS_DIR/pre-commit"
if [ -f "$HOOK" ] && grep -q "$MARK" "$HOOK"; then
  echo "git:   pre-commit already installed"
else
  install_block "$HOOK" "$MARK
if [ -f $CHECK ]; then
  python3 $CHECK --validate || exit 1
else
  echo \"ontology: checker not on this branch, skipped\" >&2
fi"
  echo "git:   pre-commit installed (validate)"
fi
HOOK="$HOOKS_DIR/commit-msg"
if [ -f "$HOOK" ] && grep -q "$MARK" "$HOOK"; then
  echo "git:   commit-msg already installed"
else
  install_block "$HOOK" "$MARK
if [ -f $CHECK ]; then
  python3 $CHECK --changed --staged --msg-file \"\$1\" || exit 1
else
  echo \"ontology: checker not on this branch, skipped\" >&2
fi"
  echo "git:   commit-msg installed (change gate)"
fi
echo "git:   hooks folder is $HOOKS_DIR"
if [ -f "$REPO/.git" ]; then
  echo "git:   this is a worktree; these hooks apply to every worktree and the main checkout"
fi

# 4. seed ontology/
if [ ! -d "$REPO/ontology" ]; then
  mkdir -p "$REPO/ontology"
  cp "$DEST/assets/ONTOLOGY.template.md" "$REPO/ontology/EXAMPLE.md"
  cat > "$REPO/ontology/README.md" <<'EOF'
# Ontology

One file per domain. Each file tells the model what the system is for, what
exists, how it connects, what must always hold, what words mean here, and
what is out of scope. The model reads it before writing code; hooks stop a
change to a governed path that doesn't also update it.

| Domain | File | Governs |
|---|---|---|
| (example) | EXAMPLE.md | see front matter |

Replace EXAMPLE.md with your real domain(s). Run
`python3 .claude/skills/ontology-driven-dev/scripts/ontology_check.py --validate`
after editing.
EOF
  echo "seed:  ontology/EXAMPLE.md + README.md (replace with your domain)"
else
  echo "seed:  ontology/ already exists, left alone"
fi

echo
echo "done. next: open Claude Code in this repo and run the ontology-driven-dev skill (Phase 1) to write the real ontology."
