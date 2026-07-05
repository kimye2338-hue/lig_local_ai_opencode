# Validation checklist

Use this checklist before distributing a new artifact broadly.

This file covers two tracks: the **agent_ops runtime / offline bundle** (Track A, below) and the **patched OpenCode TUI** (Track B, further down).

## agent_ops runtime / offline bundle validation (2026-07-05)

Track A: the office-automation runtime (`workspace-template/agent_ops/`) delivered via the offline bundle (`release/` bring-in tooling, one-click `설치.bat`).

### Release manifest + bundle tests

`workspace-template/tests/test_release_manifest.py` (`py -3.11 tests\test_release_manifest.py`):

- Manifest schema/hash shape checks against `release/dependencies.json` (resolved entries carry a 64-hex sha256, positive size, https url; deferred entries carry no fake hash and explain why; pilot-scope office/COM wheels are all resolved).
- Bundle build check (`release/build_bundle.py` into a tmp dir): zip contains `MANIFEST_SHA256.txt` with one sha256 line per archived file, root **one-click installer `설치.bat`** present (plus `처음_읽어주세요.txt`, the `AI비서.bat` daily menu, and the `_py.bat` resolver), CRLF line endings on `설치.bat` and `release/setup.bat`, `workspace-template/agent_ops/` and `plan/STATUS.md` included, and no `lig-api.env` leakage.
- File-existence + hash checks against `release/prefetch/` run only when that folder is populated (otherwise SKIP, not fail).
- Last measured (final program review, 2026-07-04): **ALL 88 PASSED** with `release/prefetch/` filled (existence/hash branch exercised for the first time), **ALL 70 PASSED** with it empty (SKIP branch).

### Prefetch hash verification

`release/verify_prefetch.py` (`py -3.11 release\verify_prefetch.py`) checks every `resolved` entry in `release/dependencies.json` against the file actually present in `release/prefetch/`, by SHA256. Pilot-optional categories (`llm-gguf`, `asr-model`, `binary-github` — local LLM serving and voice, out of pilot scope) print `OPT` when absent instead of failing; `deferred`/`PENDING` entries print `DEFER`/`PEND`. Last measured: wheel (8) + python-embed (1) — all 9 pilot-required files hash-verified OK, exit 0.

### Rehearsal pre-flight

`release/rehearsal_check.py` is the cloud-doable half of the offline-install rehearsal: it builds a real bundle zip, confirms `release/setup.bat` is offline-safe (no `-ExecutionPolicy Bypass`, no network-fetch commands, any `pip install/download` line forces `--no-index`), and prints an advisory audit of outbound-capable calls in `workspace-template/agent_ops/*.py` (flagging anything that isn't localhost/env-configured gateway). The actual air-gap run (disable the network adapter, run `설치.bat`/`setup.bat`, record `doctor`) remains a human step — see `docs/OFFLINE_REHEARSAL.md`. Last measured: **ALL 83 PASSED**.

### Company measurement

`probe/company_check.py` is the single-file instrument brought onto the company PC. With the agent_ops bundle alongside it, section 0 auto-runs `doctor` (capabilities/adapters/artifact/LLM inventory), a mock `work` E2E, and a **real-agent E2E** (real gateway → tool-use loop → response). It also drives six end-to-end business scenarios once each (not just connectivity checks).

Results: `probe/results/company_check_20260705.md` — doctor exit 0, mock work E2E exit 0, real agent E2E exit 0 (turn 2, one tool call, read-then-summarize), gateway all-routes 200 with function calling confirmed, and **6/6 business scenarios** passed (LLM native tool round-trip, Excel macro inject+run, MATLAB `-batch`, HWP document create+save, Outlook read, AutoCAD `accoreconsole` script — the AutoCAD scenario needed one re-run after an instrumentation bug, not a product defect, was fixed).

### Adapter availability gating

`workspace-template/agent_ops/adapters/__init__.py` flips an adapter's `available` flag to `True` only after it carries a recorded `validated` note tied to real evidence. As of the 2026-07-05 company measurement: `office` (Excel), `outlook`, `matlab`, `hwp`, `autocad`, and `browser` are `available: True`, each citing the company_check run that proved it. `solidworks` stays `available: False` (COM connect proven, macro execution still pending the pilot) and `fluent` stays `available: False` (not yet validated on the company's ANSYS Fluent install); Word/PowerPoint conversion under the `office` adapter also remains pending.

## Track B — patched OpenCode TUI validation

### GitHub Actions validation

Required workflow: `Build LIG OpenCode offline package`

Must pass:

- clone pinned upstream OpenCode commit
- `git apply --recount --check`
- `git apply --recount`
- `bun install`
- `bun run --cwd packages/opencode typecheck`
- Windows binary build
- locate Windows x64 `opencode.exe`
- assemble offline package
- required-file checks
- full `SHA256SUMS.txt` verification
- upload artifact with hidden files included

### Artifact download validation

After downloading the artifact:

- Extract once; no inner package ZIP should be required.
- Confirm top-level files/folders:
  - `payload/`
  - `workspace/`
  - `SHA256SUMS.txt`
  - `README_OFFLINE_INSTALL.md`
  - `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt`
- Confirm hidden workspace files exist:
  - `workspace/.opencode/commands/permission.md`
  - `workspace/.opencode/commands/agentmode.md`
  - `workspace/.opencode/agents/agentops-supervisor.md`
  - `workspace/.opencode/plugins/command-guard.ts`
- Confirm context files exist:
  - `workspace/docs/AI_HANDOFF.md`
  - `workspace/patches/opencode-permission-mode-toggle.patch`
- Verify all hashes in `SHA256SUMS.txt`.
- Run `payload/opencode.exe --version`.

### Windows runtime validation

On the target Windows PC:

- Run `VERIFY_OFFLINE_INSTALL.bat`.
- Start OpenCode through `RUN_OPENCODE_LIG.bat`.
- Confirm the TUI opens without crash.
- Ask OpenCode to do a simple local read-only task.
- Confirm no `reconciler unknown component type spinner` crash.
- Press `Shift+Tab`; permission badge toggles ASK/AUTO.
- Press `Shift+Tab` again; permission badge toggles back.
- Confirm `Shift+Tab` does not change the agent/persona/model/workflow.
- Press `Shift+F3`; previous-agent behavior still works.
- Run `/permission status`.
- Run `/permission ask`.
- Run `/permission auto`.
- Run `/permission cycle`.
- Run `/perm status`.
- Run `/perm ask`.
- Run `/perm auto`.
- Run `/perm cycle`.

### Permission safety validation

- ASK mode still shows the normal permission prompt.
- AUTO mode replies with once-only approval for permission prompts that reach the TUI.
- AUTO handles consecutive permission prompts once each.
- Reject flow still works.
- Always flow still works if manually selected.
- Subagent reject flow still works.
- Command guard blocks dangerous or corrupted bash commands.
- Explicit deny rules are not bypassed.

### Report format

When updating `docs/CURRENT_RELEASE.md`, include:

- workflow run ID
- artifact ID
- artifact digest
- `payload/opencode.exe` SHA256
- checked file count
- mismatch count
- hidden file presence result
- manual Windows runtime result, if performed
