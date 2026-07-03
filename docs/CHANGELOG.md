# Changelog

## 2026-07-01 - UX/quality hardening (launcher, guard soft-block, AUTO-HIGH-TRUST, collector)

Verified the diagnosis against OpenCode official docs (permissions, tools,
custom-tools, providers) and shipped concrete, offline-safe artifacts:

- `workspace-template/RUN_OPENCODE_LIG.bat.txt`: new hardened launcher. Forces
  `chcp 65001` on the child console (fixes Korean/mojibake, P1), opens maximized
  (`start /max`, P5), and points `OPENCODE_CONFIG`/`XDG_*` at
  `OpenCodeLIG_USERDATA` so memory/settings survive reinstall (P7). Defaults to
  `opencode --auto` (native auto-approve).
- `workspace-template/.opencode/plugins/command-guard.ts`: rewritten as a
  soft-block. Blocks only corrupted/leaked tool-call text, genuinely destructive
  commands, and malformed heredocs — each with a single-line message (no more
  multi-line English dump flooding the chat). No longer blocks legitimate shell
  file-writes (`echo>`, `python -c`, well-formed heredocs), which the agent needs
  as a fallback while native tool_calls are unreliable (P2/P4).
- `workspace-template/agent_ops/config/opencode.permission.example.json`:
  AUTO-HIGH-TRUST native permission profile. Destructive-command defense moves
  from the throwing plugin to native `permission.bash` deny patterns; safe tools
  allow; `question`/`external_directory`/`git push` gated.
- `workspace-template/COLLECT_LIG_PROXY_FILES.bat.txt`: read-only collector for
  the missing proxy/provider/model files needed to close the tool-call gap (P3).
- `docs/OPUS_UX_QUALITY_REVIEW_V2.md`: doc-verified review with model examples,
  30-min test checklist, PR sequence plan, and test plan. Supersedes v1.

Key doc facts confirmed: `--auto` is a native flag that auto-approves any
permission request not explicitly denied; `question` is a built-in,
permission-gated tool; `bash`/`edit` support native deny patterns; `websearch`
needs the OpenCode provider or `OPENCODE_ENABLE_EXA=1`. Not "complete": the
tool-call proxy files and Windows validation are still prerequisites for P3.

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
