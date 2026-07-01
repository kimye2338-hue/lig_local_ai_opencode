# Current release

Status date: 2026-07-01

## Decision

Latest validated pre-cleanup artifact: usable as the current fixed package.

After the repository cleanup lands, prefer the next successful `Build LIG OpenCode offline package` artifact because it uses the clearer repository layout and includes `docs/` plus `patches/` in the installed workspace.

## Latest validated artifact before cleanup

- Workflow run: `28504106004`
- Artifact: `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE`
- Artifact ID: `8004407134`
- Artifact digest: `sha256:e29ce2e8238352e2f6dd4f3953204d48f53a3b88a1ef48d0d5722a43dc8ec1b3`
- `payload/opencode.exe` SHA256: `7a322c3f62c1190f11d4a22a482fb9edf02f11a6749a6177160a23895c0d4b51`
- Source merge commit: `bde4cc036d091bb35971999faf7a4394b8865ddf`

## Verified

- GitHub Actions completed successfully.
- Patch apply succeeded.
- Dependency install succeeded.
- OpenCode package typecheck succeeded.
- Windows binary build succeeded.
- Package assembly succeeded.
- Package required-file verification succeeded.
- Artifact upload succeeded.
- Downloaded artifact ZIP SHA256 matched GitHub artifact digest.
- `SHA256SUMS.txt` checked `91` files with `0` mismatches.
- Hidden files were present after extraction:
  - `workspace/.gitignore`
  - `workspace/.opencode/commands/permission.md`
  - `workspace/.opencode/commands/agentmode.md`
  - `workspace/.opencode/agents/agentops-supervisor.md`
- `payload/opencode.exe --version` exited successfully in local validation.

## Fixes included

- `/perm` alias now follows the same parser as `/permission`.
- AUTO duplicate-reply protection tracks request id.
- Artifact is no longer ZIP-inside-ZIP.
- Installer verifies `payload/opencode.exe` checksum.
- Installer backs up an existing `%USERPROFILE%\OpenCodeLIG`.
- Hidden `.opencode` files are included in artifacts.
- Direct `<spinner>` render paths are removed to avoid OpenTUI reconciler crash.

## Install note

Do not use artifacts older than run `28504106004` for the spinner crash fix. Older artifacts can still crash with `unknown component type spinner` or miss hidden `.opencode` files.
