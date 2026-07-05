# AI agent instructions

This repository builds and reviews a patched offline OpenCode package for a Windows company PC,
plus the `agent_ops` office-automation runtime under `workspace-template/`.

## agent_ops build-out program (implementation workers: START HERE)

If you were asked to "다음 작업 진행", "continue the plan", or anything about the
agent_ops / OpenCodeLIG build-out:

1. Read `skills/worker-loop/SKILL.md` — it is the work loop (auto-advance rules included).
2. Reusable procedures live in `skills/` (repo-conventions, self-review, windows-batch,
   app-adapter). Read the ones your task names; do not re-derive them.
3. Mandatory rules: `plan/PROTOCOL.md`. Board: `plan/STATUS.md` (take the first READY task).
4. After each task, write `plan/reports/<TASK-ID>-r<N>.md`; reviewer feedback arrives in
   `plan/reviews/` — apply all "필수 수정" items before new work.

Strategy/why lives in `workspace-template/docs/MASTER_PLAN.md`. Do not start agent_ops
work without reading `plan/PROTOCOL.md`.

## Read first (OpenCode package work)

1. `README.md`
2. `docs/AI_HANDOFF.md`
3. `docs/REPOSITORY_MAP.md`
4. `docs/CURRENT_RELEASE.md`
5. `docs/OPENCODE_LIG_LOCAL_FIXES_20260705.md` when touching launchers, config, encoding, or TUI crash handling.

## Source of truth

- Workflow: `.github/workflows/build-offline-package.yml`
- OpenCode patch: `patches/opencode-permission-mode-toggle.patch`
- Installed workspace template: `workspace-template/`
- Shared handoff and review context: `docs/AI_HANDOFF.md`
- Current artifact/install state: `docs/CURRENT_RELEASE.md`
- Runtime hotfix notes/scripts: `docs/OPENCODE_LIG_LOCAL_FIXES_20260705.md` and `patches/runtime-hotfixes/`

Do not add a second competing workflow, patch file, installer folder, or handoff bundle unless the user explicitly asks.

## Primary behavior to preserve

- `Shift+Tab` toggles only permission approval policy: ASK <-> AUTO.
- `Shift+Tab` must not cycle agents, personas, workflow mode, plan mode, or models.
- Previous-agent reverse cycle is `Shift+F3`.
- The TUI shows the current permission mode.
- `/permission status|ask|auto|cycle` and `/perm status|ask|auto|cycle` behave identically.
- AUTO approval uses `reply: "once"` only.
- AUTO must not bypass command guard, explicit deny, or high-risk policy controls.
- ASK mode must preserve the original permission prompt flow.
- Direct `<spinner>` JSX or `D("spinner")` must not be reintroduced unless the OpenTUI renderable registration is proven fixed in the offline build.
- If a spinner indicator is needed, use a registered `text`/fallback component.

## Packaging constraints

The company PC install must stay offline-friendly.

Do not introduce:

- base64 payloads embedded in BAT files
- self-extracting BAT installers
- `PowerShell -ExecutionPolicy Bypass` in the installer
- company-PC internet downloads
- company-PC git clone, npm install, or bun install requirements
- npm imports in OpenCode local plugins unless the offline install path is updated and validated
- real local credentials in public GitHub-tracked files

## Windows encoding and command-output rules

- BAT entrypoints should use `chcp 65001 >nul`.
- Set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` in launchers/diagnostics.
- Python subprocess capture must use `encoding="utf-8", errors="replace"`.
- Do not rely on localized Korean `dir` output for parsing; use Python `Path.exists()` or ASCII sentinel lines.
- Mojibake such as `C ����̺���...` means command output encoding/codepage handling is wrong, not that the file/path is necessarily missing.

## Model/provider config rules

- `RUN_OPENCODE_LIG.bat` is not valid unless OpenCode config includes provider/model routes.
- The installer/repair path must write config to all roots used by the launcher:
  - `%USERPROFILE%\.config\opencode\opencode.json`
  - `%USERPROFILE%\OpenCodeLIG\userdata\config\opencode\opencode.json`
  - any workspace-local path referenced through `OPENCODE_CONFIG`.
- The launcher must load `%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env` into environment before starting OpenCode.
- Public repo files must avoid real local credentials. Closed-network local repair files may preserve them, but do not commit them.

## Review tasks

If the user asks for review/audit/feedback only:

- Do not modify files.
- Inspect the workflow, patch, and workspace template.
- Classify findings by severity.
- Report exact files and runtime implications.

## Fix tasks

If the user asks to fix:

- Make minimal targeted changes.
- Update `docs/AI_HANDOFF.md`, `docs/CURRENT_RELEASE.md`, `docs/CHANGELOG.md`, or `docs/OPENCODE_LIG_LOCAL_FIXES_20260705.md` when behavior or packaging changes.
- Run or trigger the existing workflow when package behavior changes.
- Report workflow run ID, artifact ID, digest, and validation result.

## Collaboration protocol

- Keep one shared handoff in `docs/AI_HANDOFF.md`.
- Add unresolved ideas or review findings to `docs/CHANGELOG.md` or `docs/VALIDATION.md`; do not scatter new prompt bundles.
- When Claude Code and Codex alternate, each agent should update the handoff with what changed, what was verified, and what remains.
