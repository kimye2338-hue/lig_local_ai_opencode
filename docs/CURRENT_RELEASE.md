# Current release

Status date: 2026-07-01

## Decision

Use the latest successful `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE` artifact from the `Build LIG OpenCode offline package` workflow on `main`.

Verified cleanup baseline:

- Commit: `2ac5d4aa99476fe80a44ba5b42391747aee3de11`
- Workflow run: `28505265540`
- Artifact: `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE`
- Artifact ID: `8004882821`
- Artifact digest: `sha256:2d52e390461b732491eadafcde025ec7f329577d40e7e1f52618be6aab991115`
- `payload/opencode.exe` SHA256: `5fa524bbddb547fcbc776bf15c824945dcdd538b6aaccc077db4b47ff521545e`

If a newer successful run exists on `main`, use that newer artifact. This file records the last manually downloaded and checksum-verified baseline.

## Verified

- GitHub Actions completed successfully.
- Patch apply succeeded from the new `patches/` path.
- Dependency install succeeded.
- OpenCode package typecheck succeeded.
- Windows binary build succeeded.
- Package assembly succeeded from `workspace-template/`.
- Package required-file verification succeeded.
- Artifact upload succeeded.
- Downloaded artifact ZIP SHA256 matched GitHub artifact digest.
- `SHA256SUMS.txt` checked `81` files with `0` mismatches.
- Hidden files were present after extraction:
  - `workspace/.opencode/commands/permission.md`
  - `workspace/.opencode/commands/agentmode.md`
  - `workspace/.opencode/agents/agentops-supervisor.md`
  - `workspace/.opencode/plugins/command-guard.ts`
- Context files were present after extraction:
  - `workspace/docs/AI_HANDOFF.md`
  - `workspace/docs/REPOSITORY_MAP.md`
  - `workspace/patches/opencode-permission-mode-toggle.patch`

## Fixes included

- `/perm` alias now follows the same parser as `/permission`.
- AUTO duplicate-reply protection tracks request id.
- Artifact is no longer ZIP-inside-ZIP.
- Installer verifies `payload/opencode.exe` checksum.
- Installer backs up an existing `%USERPROFILE%\OpenCodeLIG`.
- Hidden `.opencode` files are included in artifacts.
- Direct `<spinner>` render paths are removed to avoid OpenTUI reconciler crash.
- GitHub repository structure is cleaned around `docs/`, `patches/`, and `workspace-template/`.

## Install note

Do not use artifacts older than run `28505265540` for the cleaned repository layout. Do not use artifacts older than run `28504106004` for the spinner crash fix.
