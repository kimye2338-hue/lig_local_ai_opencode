# Changelog

## 2026-07-01 - Repository cleanup and source-of-truth reset

- Merged PR #4 into `main`.
- Replaced the scattered old layout with clear top-level areas:
  - `.github/workflows/`
  - `patches/`
  - `workspace-template/`
  - `docs/`
- Condensed old Claude/Opus/Codex prompt bundles into `docs/ARCHIVE_SUMMARY.md`.
- Moved the installed workspace source from `PROJECT_FULL_SOURCE_TO_EDIT/` to `workspace-template/`.
- Moved the OpenCode source patch to `patches/opencode-permission-mode-toggle.patch`.
- Renamed the package workflow to `.github/workflows/build-offline-package.yml`.
- Added a single shared handoff file at `docs/AI_HANDOFF.md`.

## 2026-07-01 - Spinner crash fix

User report:

```text
reconciler unknown component type spinner
```

Decision:

The offline Windows TUI must not render direct custom `<spinner>` JSX unless the renderable is proven registered in that exact runtime.

Changes:

- `packages/tui/src/component/spinner.tsx` renders text fallback.
- `packages/opencode/src/cli/cmd/run/footer.subagent.tsx` uses status text/icon.
- `packages/opencode/src/cli/cmd/run/footer.view.tsx` removes direct busy footer spinner block.

User impact:

- The tiny loading animation is replaced with stable text/status output.
- OpenCode should no longer crash when asked to work.

## 2026-07-01 - Offline artifact hardening

- Artifact upload now uses the package directory instead of ZIP-inside-ZIP.
- `include-hidden-files: true` keeps `.opencode` files in the artifact.
- Workflow validates required files before upload.
- Workflow verifies every `SHA256SUMS.txt` entry.
- Installer checks `payload/opencode.exe` checksum before copying.
- Installer backs up existing `%USERPROFILE%\OpenCodeLIG` before overwrite.

## 2026-07-01 - Permission mode hardening

- `/perm` aliases now use the same direct parser as `/permission`.
- AUTO duplicate-reply protection tracks request id.
- Windows x64 binary selection fails if no matching `opencode.exe` is found.
- Branch pushes under `codex/**` and PRs trigger the package workflow.

## Earlier retained context

The old review bundles identified these important AgentOps runtime themes, retained in summarized form:

- Windows-safe file locks.
- Command guard must be in the OpenCode tool execution path.
- Parallel orchestrator must atomically claim tasks.
- Internal LLM gateway may be keyless.
- Memory should dedupe/cap lessons and error patterns.
- Status should remain read-only.
- Offline plugins should avoid npm imports.

See `docs/ARCHIVE_SUMMARY.md` for the condensed archive notes.
