# LIG local AI OpenCode offline package

This repository builds and documents the LIG patched OpenCode offline package for a Windows company PC.

Current focus: a patched OpenCode TUI where permission approval mode is separate from agent/persona/workflow/model selection.

## Latest validated package

Use the latest successful `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE` artifact from GitHub Actions. The verified cleanup baseline is:

- Commit: `2ac5d4aa99476fe80a44ba5b42391747aee3de11`
- Workflow run: `28505265540`
- Artifact: `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE`
- Artifact ID: `8004882821`
- Artifact digest: `sha256:2d52e390461b732491eadafcde025ec7f329577d40e7e1f52618be6aab991115`
- `payload/opencode.exe` SHA256: `5fa524bbddb547fcbc776bf15c824945dcdd538b6aaccc077db4b47ff521545e`
- Validation: GitHub Actions success, downloaded artifact SHA matched, `SHA256SUMS.txt` checked 81 files with 0 mismatches, hidden `.opencode` files plus `workspace/docs` and `workspace/patches` present.

If a newer successful workflow run exists on `main`, use that newer artifact; it should be equivalent or newer than this baseline.

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
