# Changelog

## 2026-07-05 - agent_ops runtime rebuild + company validation

### Final polish (same day, ultracode full review)

- One-click install: bundle-root `설치.bat` + interactive gateway setup + desktop
  [AI비서] menu; all launcher BATs CRLF + shared Python 3.11 resolver (_py.bat).
- `work --mode real` now actually fills artifact content via the gateway LLM
  (quality-gated enrich, scaffold fallback); `work --execute` actually runs safe
  adapter mappings (matlab/.m, document->.hwp, macro->input .xlsx copy,
  autocad with input .dwg) and reports unmapped kinds honestly as no-auto-run.
- 'HWP/Word 변환' routes to document generation (no more stray AutoCAD/VBA kinds).
- Clear Korean guidance on missing gateway config and total-gateway-failure paths.
- 22 verified findings (10 must / 12 should) from a 42-agent review, all fixed;
  regression 20 green + new dispatch tests; docs (INSTALL/VALIDATION/
  REPOSITORY_MAP/AI_HANDOFF/launch README) aligned to the validated state.

Major milestone: the `agent_ops` office-automation runtime was rebuilt on the
`rebuild/fable5-open-architecture` branch and validated on the company PC.

- **Runtime**: stdlib-only core (weak-model tool-call recovery parser, LIG provider
  fallback, resilient LLM runtime with injectable transport, sandboxed file tools,
  mock/real agent loop, checkpoint/resume), keyword-routed capability planner with a
  NEGATIVE_CORPUS bench guard, input-grounded artifact generation + per-kind quality
  validators, approval gate + audit log, schedule/briefing, secretary capabilities.
- **Adapters**: COM (Excel/Word/PPT/Outlook/HWP/SolidWorks), batch (MATLAB/AutoCAD/
  Fluent), browser CDP. Optional-import graceful degradation; execution gated behind
  approval.
- **Company validation (2026-07-05)**: real gateway pipeline end-to-end (tool-use loop)
  succeeded; 6/6 business scenarios passed. Adapters office(Excel)/outlook/matlab/hwp/
  autocad/browser flipped to `available` with recorded evidence
  (`probe/results/company_check_20260705.md`). SolidWorks (connect-only), Fluent, and
  office Word/PPT convert remain pending.
- **Offline bring-in** (`release/`): per-file SHA256 prefetch manifest, `build_bundle.py`
  (transparent zip + internal MANIFEST_SHA256, secret refusal), offline `setup.bat`
  (`pip --no-index`), `verify_prefetch.py`, air-gap rehearsal pre-flight + procedure.
  Pilot deps = 8 office/COM wheels + python-embed (all hashes measured); local-serving
  and voice binaries deferred.
- **Diagnostics** (`probe/`): single-file `company_check.py` -> one `.md` report,
  auto-detecting a co-located runtime to run doctor + mock + real gateway E2E.
- **Security**: internal hostname purged from git history (git-filter-repo, all branches
  + main); secret-scan pre-commit; no secrets/hosts in code, commits, bundles, or reports.
- **OpenCode integration** (`docs/OPENCODE_INTEGRATION.md`): agent_ops runs as a parallel
  CLI (no external-runtime hook in OpenCode plugins), confirmed against official docs.

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
