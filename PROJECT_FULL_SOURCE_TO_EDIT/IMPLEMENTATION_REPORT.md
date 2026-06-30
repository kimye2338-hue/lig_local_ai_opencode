# AgentOps v3.1 — Implementation Report

Implements the Opus senior review (`REVIEW_AND_WORK_INSTRUCTIONS/01_OPUS_FEEDBACK_FULL.md`)
per the low-token manager workflow. Scope was kept to `PROJECT_FULL_SOURCE_TO_EDIT/`;
the AgentOps v3.1 architecture was preserved (no rewrite). All validation ran on
Linux **Python 3.11.15** (the home PC uses Windows `py -3.11`; Windows-only checks
are listed in `VALIDATION_TODO_ON_WINDOWS.md`).

## Files changed (21 files, +700 / −58 vs imported baseline)

### Python (`agent_ops/`)
- `core.py` — P0-1 Windows-safe `_pid_alive`/`_lock_is_stale`; P1-4 `.bat.txt`/`.cmd.txt` ASCII validation.
- `llm_client.py` — P0-4 keyless gateway + defensive response parsing.
- `queue_manager.py` — P0-3 `claim_task`; P1-1 retry accounting; P1-2 `_retry_ready` + selectors.
- `orchestrator.py` — P0-3 `run_task_parallel` + `_CKPT_LOCK`; parallel path no longer writes shared single-file state.
- `memory_manager.py` — P1-3 success-lesson gating + `MAX_ACTIVE` archive cap.
- `failures.py` — P1-3 error-pattern dedupe by recent failure type.
- `safe_file_writer.py` — P1-4 `.bat.txt`/`.cmd.txt` ASCII validation.
- `state_manager.py` — review §D: `detect_interruption` also watches `checkpoint`.
- `agentops.py` — P1-7 read-only `cmd_status`; `status --ko`; `fix` + `dashboard` subcommands.
- `command_guard.py` — P2-1 orchestrator launches no longer auto-allowed.
- `render_ko.py` *(new)* — Korean plain-text status renderer.
- `dashboard.py` *(new)* — offline single-file HTML dashboard (html-escaped).

### OpenCode (`.opencode/`)
- `plugins/command-guard.ts` *(new)* — P0-2 `tool.execute.before` guard, zero npm imports.
- `plugins/compaction-handoff.ts` — P1-5 additive `output.context.push` + robust base path.
- `commands/start.md`, `work.md`, `fix.md` *(new)* — front-door commands.

### Runners / meta
- `RUN_AGENTOPS_START.bat.txt`, `RUN_AGENTOPS_FIX.bat.txt` *(new, ASCII)*.
- `.gitignore` *(new)* — excludes runtime state + `__pycache__`.
- `WORKLOG.md`, `REQUIRES_OPENCODE_SOURCE_PATCH.md`, `IMPLEMENTATION_REPORT.md`,
  `WINDOWS_TEST_PLAN.md`, `REMAINING_RISKS.md`, `VALIDATION_TODO_ON_WINDOWS.md` *(new docs)*.

## Items completed

### Phase 0 — P0 blockers (all 4, validated) — install blockers cleared
- **P0-1** Windows lock liveness/staleness fix.
- **P0-2** Real command-guard plugin in the exec path.
- **P0-3** Atomic parallel claim + no shared single-file writes from workers.
- **P0-4** Keyless internal LLM gateway + defensive parsing.

### Phase 1 — reliability (P1-1..P1-5, P1-7, §D)
- **P1-1/P1-2** order-independent retry + exponential backoff honored by selection.
- **P1-3** memory anti-bloat (success-lesson gating, error-pattern dedupe, 500-cap archive).
- **P1-4** `.bat.txt`/`.cmd.txt` ASCII validation.
- **P1-5** additive, path-robust compaction handoff.
- **P1-7** read-only `/status` (+ deliberate heartbeat-removal deviation, see below).
- **§D** interruption detection now catches a crash right after a checkpoint.

> P1-6 (relocate `*.bak` backups under `agent_ops/archive/backups/`) was **not**
> applied — see `REMAINING_RISKS.md`.

### Phase 2 — UX (all listed items)
- Front-door commands `/start`, `/work`, `/fix` (plus existing `/status`, `/remember`).
- Korean plain-text status (`status --ko`) + `fix --ko`.
- Offline HTML dashboard (`dashboard` subcommand).
- One-click `RUN_AGENTOPS_START.bat.txt` / `RUN_AGENTOPS_FIX.bat.txt`.
- **P2-1** guard: orchestrator launches downgraded to `ask`.

### Phase 3 — design only
- `REQUIRES_OPENCODE_SOURCE_PATCH.md` (permission-mode toggle C2). Not implemented:
  no OpenCode source in package.

## Tests run and output (Python 3.11.15, Linux)

| Test | Command (abridged) | Result |
|------|--------------------|--------|
| py_compile (all touched) | `python3 -m py_compile agent_ops/*.py` | PASS |
| P0-1 liveness | `_pid_alive(self)` / `_pid_alive(999999)` | `True` / `False` |
| P0-2 guard parity | `command_guard.py check "cat > a.py << 'EOF'"` | `block` (4 reasons) |
| P0-2 compound | `… "cd x && cat > a.py << 'EOF'"` | `block` |
| P0-2 safe / unknown | `… "… agentops.py status"` / `"node build.js"` | `allow` / `ask` |
| P0-2 transpile | `bun build .opencode/plugins/command-guard.ts` | OK |
| P0-3 parallel drain | 6 memorycheck tasks, workers=3 | each `done` once, no `attempt_count>1` |
| P0-4 keyless gate | `AGENTOPS_LLM_NO_AUTH=1 … is_configured()` | `True` (and `False` without flag) |
| P1-1/P1-2 retry | fail at 1/3 then 3/3; `get_next_task` | `pending`+`next_retry_at` then `failed`; backed-off task skipped |
| P1-3 dedupe | 5 identical successes; routine kinds | at most +1 lesson; routine skipped |
| P1-4 ASCII | ascii vs non-ascii `.bat.txt` | ok / `bat_cmd_must_be_ascii` |
| P1-7 status read-only | run status twice on stale `running` | active stays `active`; resume can still recover |
| P2 Korean / fix / dashboard | `status --ko`, `fix --ko`, `dashboard` | Korean output; offline HTML, XSS-escaped |
| P2-1 guard | `… orchestrator --parallel` | `ask` (not `allow`) |
| Final suite | `init` → `verify` | `verify ok: true` |

## Failures or skipped tests
- **No failures.** All Phase 0 validations passed → continued past the Phase 0 stop gate.
- **Skipped (cannot run off the target machine):** live OpenCode plugin behavior
  (review tests **T9** guard-in-TUI, **T8** real compaction trigger) and the
  Windows `py -3.11` launcher form. See `VALIDATION_TODO_ON_WINDOWS.md`.

## Deliberate deviation from the review (documented)
The review's verbatim read-only `cmd_status` kept `heartbeat("status")`. Because
`"status"` is not a watched run status and heartbeat refreshes `last_heartbeat`,
keeping it would **mask a real stale-heartbeat interruption** from a later
`resume`/`init` (which is where recovery now lives after P1-7). I removed the
heartbeat and `update_resume_plan` from `cmd_status` so status is truly read-only
and the interruption signal survives. Verified: after two `status` runs on a stale
`running` state, `detect_interruption()` still reports `interrupted: true`.

## Remaining risks / next recommended step
See `REMAINING_RISKS.md`. **Next step:** on the Windows 망분리 PC, run
`VALIDATION_TODO_ON_WINDOWS.md` (especially T9 live guard and T8 compaction), then
proceed to install. Defer the C2 permission-mode fork until after a source spike.
