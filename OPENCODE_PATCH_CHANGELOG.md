# OpenCode Permission Patch Changelog

This changelog summarizes the important repository changes related to the patched OpenCode offline package.

## Current source of truth

- Workflow: `.github/workflows/build-patched-opencode-offline.yml`
- Patch: `PROJECT_FULL_SOURCE_TO_EDIT/opencode_core_patch/opencode-permission-mode-toggle.patch`
- Handoff: `AI_REVIEW_HANDOFF.md`
- Agent rules: `AGENTS.md`

## Timeline

### 2026-07-01 — PR #4 hardened next-version package

Branch:

- `codex/permission-mode-next-version`

Important run:

- Run ID: `28496829694`
- Artifact: `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE`
- Artifact ID: `8001380720`
- Artifact digest: `sha256:97b001f05f1b88ae1e87c40e9c0ccd2647051e637feff5aabbcf12b815bd1733`

Summary:

- `/perm ...` aliases now use the same direct parser as `/permission ...`.
- AUTO duplicate reply protection now tracks `props.request.id` instead of using one boolean.
- Workflow uploads the package directory instead of a pre-built ZIP, avoiding ZIP-inside-ZIP artifact layout.
- Installer verifies `payload/opencode.exe` SHA256 with `certutil` before copying.
- Installer backs up existing `%USERPROFILE%\OpenCodeLIG` before overwriting.
- Workflow validates required package files and all SHA256SUMS entries.
- README documents `/perm`, `Shift+F3`, checksum behavior, backup behavior, and expected artifact layout.

Important review targets:

- Confirm `/perm` aliases actually follow the intended parser path.
- Confirm `autoRepliedRequestID` handles consecutive requests and does not create duplicate replies.
- Confirm installer checksum parsing works on Korean Windows CMD.
- Confirm backup behavior is safe enough for company PC use.

### 2026-07-01 — Finalized permission auto approval behavior

Commit:

- `81e0cbd1933aa95616291d5e905c2e32eaf2cede`
- Message: `Complete OpenCode permission auto approval patch`

Summary:

- Added actual AUTO permission reply behavior in `packages/tui/src/routes/session/permission.tsx`.
- Added `createEffect` and `useLocal`.
- Added `replyOnce()` helper that calls `sdk.client.permission.reply({ reply: "once", ... })`.
- AUTO mode replies once when `store.stage === "permission"` and `local.permission.mode === "auto"`.
- Existing manual "Allow once" path reuses `replyOnce()`.

Important review target:

- Confirm AUTO mode does not bypass explicit deny / command guard.
- Confirm reply failure behavior is acceptable.

### 2026-07-01 — Hardened offline workflow verification

Commit:

- `0b065c380b9ede7f9bd86c492e447e8511b94302`
- Message: `Harden offline OpenCode workflow verification`

Summary:

- Hardened PowerShell command failure handling with `$PSNativeCommandUseErrorActionPreference = $true`.
- Ensured native command failures do not silently pass.
- Strengthened workflow verification around patching/building/packaging.

Important review target:

- Confirm every native command step sets `$ErrorActionPreference = 'Stop'` and `$PSNativeCommandUseErrorActionPreference = $true` where needed.
- Confirm `git apply --recount --check` and `git apply --recount` failure stops the workflow.

### 2026-07-01 — Earlier successful offline package run

Run:

- Run ID: `28494990662`
- Workflow: `Build patched OpenCode offline package`
- Artifact: `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE`
- Artifact ID: `8000706677`
- Artifact digest: `sha256:14f4f9ba4144f5879fd5e2c49fefb0371ec415bf62baf50f057bfd75129f82b3`

Reported successful steps:

- patch check/apply success
- `bun install` success
- typecheck success
- build success
- Windows x64 binary smoke test success
- artifact ZIP verification success
- extracted `payload/opencode.exe --version` success

Version:

- `opencode.exe --version`: `0.0.0--202607010513`

### Earlier context — permission mode implementation

The patch implements:

- `Shift+Tab` -> `permission.mode`
- `agent_cycle_reverse` -> `Shift+F3`
- `PermissionMode = "ask" | "auto"`
- `/permission status`
- `/permission ask`
- `/permission auto`
- `/permission cycle`
- `/perm status`
- `/perm ask`
- `/perm auto`
- `/perm cycle`
- `PermissionModeBadge`
- offline package installer and README

## Current unresolved validation tasks

The build is successful, but the following should still be reviewed or manually tested:

1. Actual Windows terminal `Shift+Tab` key recognition.
2. TUI layout of `[PERM:ASK shift+tab]` / `[PERM:AUTO shift+tab]`.
3. `/permission` and `/perm` command behavior.
4. AUTO mode `reply: "once"` behavior with real permission requests.
5. Duplicate reply behavior across SolidJS reactivity/remounts.
6. ASK mode still showing the original prompt.
7. Reject/always/subagent reject flows remain intact.
8. Explicit deny / command guard remains intact.
9. Offline installer on company PC.
10. Installer checksum verification on Korean Windows CMD.
11. Existing installation backup/rollback.

## Do not regress

Future changes must not reintroduce:

- `Shift+Tab` agent cycling.
- Permission mode coupled to agent/persona/workflow/model state.
- AUTO using `reply: "always"`.
- Base64/self-extracting BAT installer.
- PowerShell `-ExecutionPolicy Bypass` in company-PC installer.
- Company-PC internet dependency.
- ZIP-inside-ZIP artifact layout.
