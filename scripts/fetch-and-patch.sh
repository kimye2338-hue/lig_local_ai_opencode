#!/usr/bin/env bash
#
# Reproduce the patched OpenCode build with the Claude-Code-like session
# permission mode toggle.
#
# Usage:
#   ./scripts/fetch-and-patch.sh [target-dir]
#
# Default target-dir: vendor/opencode-source
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-$REPO_ROOT/vendor/opencode-source}"
# OpenCode moved from sst/opencode to anomalyco/opencode (repo id 975734319).
BRANCH="dev"
TARBALL_URL="https://codeload.github.com/anomalyco/opencode/tar.gz/refs/heads/${BRANCH}"

echo ">> Fetching OpenCode source (${BRANCH}) ..."
mkdir -p "$TARGET"
tmp="$(mktemp -d)"
curl -sSL -o "$tmp/opencode.tar.gz" "$TARBALL_URL"
tar xzf "$tmp/opencode.tar.gz" -C "$TARGET" --strip-components=1
rm -rf "$tmp"

echo ">> Applying new files ..."
cp "$REPO_ROOT/patches/new/packages/core/src/permission/mode.ts" \
   "$TARGET/packages/core/src/permission/mode.ts"
mkdir -p "$TARGET/packages/core/test/permission"
cp "$REPO_ROOT/patches/new/packages/core/test/permission/mode.test.ts" \
   "$TARGET/packages/core/test/permission/mode.test.ts"

echo ">> Applying patch to existing files ..."
( cd "$TARGET" && git apply -p1 "$REPO_ROOT/patches/permission-mode.patch" 2>/dev/null \
  || patch -p1 < "$REPO_ROOT/patches/permission-mode.patch" )

echo ">> Installing dependencies (this can take a while) ..."
( cd "$TARGET" && bun install )

cat <<EOF

>> Done. To run the patched OpenCode:
     cd "$TARGET"
     bun run dev

>> To verify:
     bun test packages/core/test/permission/mode.test.ts
     bun run --cwd packages/core typecheck

>> Keybind: shift+tab cycles NORMAL -> AUTO -> PLAN (fallback <leader>p).
>> Slash:   /permission, /permission-plan, /permission-normal,
            /permission-auto, /permission-status
EOF
