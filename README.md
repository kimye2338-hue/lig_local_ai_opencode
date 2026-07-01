# LIG local AI OpenCode offline package

This repository builds and documents the LIG patched OpenCode offline package for a Windows company PC.

Current focus: a patched OpenCode TUI where permission approval mode is separate from agent/persona/workflow/model selection.

## Latest validated package

Use the latest successful artifact from GitHub Actions, not old attached ZIPs or archived instruction bundles.

- Merge commit: `bde4cc036d091bb35971999faf7a4394b8865ddf`
- Source branch merged: `codex/permission-mode-next-version`
- Workflow run: `28504106004`
- Artifact: `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE`
- Artifact ID: `8004407134`
- Artifact digest: `sha256:e29ce2e8238352e2f6dd4f3953204d48f53a3b88a1ef48d0d5722a43dc8ec1b3`
- `payload/opencode.exe` SHA256: `7a322c3f62c1190f11d4a22a482fb9edf02f11a6749a6177160a23895c0d4b51`
- Validation: GitHub Actions success, downloaded artifact SHA matched, `SHA256SUMS.txt` checked 91 files with 0 mismatches, hidden `.opencode` files present.

## Repository map

```text
.github/workflows/build-offline-package.yml  Build the Windows offline package.
patches/opencode-permission-mode-toggle.patch  Patch applied to pinned upstream OpenCode.
workspace-template/                         Files copied into the installed workspace.
docs/AI_HANDOFF.md                          Shared context for Codex, Claude Code, and reviewers.
docs/CURRENT_RELEASE.md                     Current artifact and install decision.
docs/INSTALL.md                             Offline install steps.
docs/VALIDATION.md                          Runtime/manual test checklist.
docs/CHANGELOG.md                           Important changes and decisions.
docs/ARCHIVE_SUMMARY.md                     Condensed summary of removed legacy instruction bundles.
AGENTS.md                                   Short rules for AI agents working in this repo.
```

## Build

Run the `Build LIG OpenCode offline package` workflow from GitHub Actions.

The workflow:

1. Clones upstream `anomalyco/opencode` at pinned commit `afff74eb2c9fc3808a9795f365707f32853099e9`.
2. Applies `patches/opencode-permission-mode-toggle.patch`.
3. Runs dependency install, typecheck, and Windows binary build.
4. Assembles an offline package with `payload`, `workspace`, `README_OFFLINE_INSTALL.md`, installer BAT text, and `SHA256SUMS.txt`.
5. Verifies required files and every SHA256 entry before upload.

## Install

See `docs/INSTALL.md`.

Short version:

1. Download `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE` from the latest successful workflow run.
2. Extract it once.
3. Rename `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt` to `INSTALL_OFFLINE_LIG_OPENCODE.bat`.
4. Run it on the offline Windows PC.
5. Start with `%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat`.

## Current user-facing behavior

- `Shift+Tab` toggles `[PERM:ASK]` / `[PERM:AUTO]` only.
- `Shift+F3` keeps the previous-agent shortcut.
- `/permission status|ask|auto|cycle` works.
- `/perm status|ask|auto|cycle` works.
- AUTO replies with `reply: "once"`, not `always`.
- Spinner crash mitigation removes direct `<spinner>` render paths from the offline TUI build.

## Collaboration rule

For Codex, Claude Code, and other AI reviewers: read `AGENTS.md` and `docs/AI_HANDOFF.md` first. Keep source-of-truth changes centered on the workflow, patch, workspace template, and docs above. Do not recreate old parallel instruction bundles.
