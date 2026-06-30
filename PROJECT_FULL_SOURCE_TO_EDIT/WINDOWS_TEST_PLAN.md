# Windows Test Plan (망분리 PC, Python 3.11, offline)

Run from the project root (`PROJECT_FULL_SOURCE_TO_EDIT/`). Use your launcher:
`py -3.11` or `python`. These mirror Opus review §5 (T1–T11) plus the new UX.
Items marked **[verified on Linux]** already passed here; re-running on Windows
confirms the Windows-specific path. Items marked **[Windows-only]** could not run
off the target machine.

## Pre-req
```bat
py -3.11 agent_ops\agentops.py init
```
`verify` needs `.agent-memory\memory.jsonl`, which `init` creates. Keep this order.

## Core P0 / P1

| ID | Command | Expected |
|----|---------|----------|
| T0  | `py -3.11 -m py_compile agent_ops\core.py agent_ops\queue_manager.py agent_ops\orchestrator.py agent_ops\llm_client.py agent_ops\command_guard.py agent_ops\safe_file_writer.py agent_ops\memory_manager.py agent_ops\failures.py agent_ops\agentops.py agent_ops\state_manager.py agent_ops\render_ko.py agent_ops\dashboard.py` | no output, all compile **[verified on Linux]** |
| T1  | `py -3.11 agent_ops\command_guard.py check "cat > a.py << 'EOF'"` | `"decision": "block"` **[verified]** |
| T2  | `py -3.11 agent_ops\command_guard.py check "python agent_ops/agentops.py status"` | `"decision": "allow"` **[verified]** |
| T3  | `py -3.11 agent_ops\command_guard.py check "node build.js"` | `"decision": "ask"` **[verified]** |
| P0-1w | `py -3.11 -c "from agent_ops.core import _pid_alive; import os; print(_pid_alive(os.getpid()), _pid_alive(999999))"` | `True False` (2nd may be `True` only if PID 999999 really exists) **[Windows-only path: ctypes/tasklist]** |
| T4  | create `staging.txt` containing `print(1)`, then `py -3.11 agent_ops\safe_file_writer.py out\demo.py --content-file staging.txt` | `"ok": true`, `py_compile_returncode: 0` |
| T4b | staging with `def(:` then same command | `"ok": false`, `py_compile_failed`, exit 40 |
| T4c | create `bad.bat.txt` with a non-ASCII char, run `py -3.11 agent_ops\safe_file_writer.py keep\bad.bat.txt --content-file bad.bat.txt` | `bat_cmd_must_be_ascii` **[verified on Linux via core.validate]** |
| T5  | edit `agent_ops\state\RUN_STATE.json`: `status:"running"`, `last_heartbeat` 1h ago; then `py -3.11 agent_ops\agentops.py resume` | "INTERRUPTED RUN RECOVERED"; any `active` task → `pending` |
| T5b | with the same stale state, `py -3.11 agent_ops\agentops.py status` then `... resume` | status does NOT recover; resume DOES (read-only status confirmed) **[verified on Linux]** |
| T6  | `py -3.11 agent_ops\agentops.py remember "always keep BAT ASCII"` then `... recall BAT ASCII` | recall lists the user instruction, high priority |
| T7  | enqueue 6 trivial tasks, `py -3.11 agent_ops\agentops.py orchestrator --parallel --workers 3 --interval 5`, idle one cycle, Ctrl-C, `... status` | each task `done` once; no `attempt_count>1`; `ACTIVE_TASK.json` valid **[parallel drain verified on Linux]** |
| T10 | `set AGENTOPS_LLM_NO_AUTH=1` + base_url + model, then `py -3.11 -c "from agent_ops.llm_client import is_configured; print(is_configured())"` | `True` **[verified]** |
| T11 | `py -3.11 agent_ops\agentops.py verify` (after `init`) | `"ok": true` **[verified]** |

## UX (Phase 2)

| ID | Command | Expected |
|----|---------|----------|
| U1 | `py -3.11 agent_ops\agentops.py status --ko` | Korean status paragraph, no raw JSON **[verified]** |
| U2 | `py -3.11 agent_ops\agentops.py fix --ko` | Korean self-heal + verify summary **[verified]** |
| U3 | `py -3.11 agent_ops\agentops.py dashboard` then open `agent_ops\reports\dashboard.html` | opens offline in a browser, no network **[verified]** |
| U4 | double-click `RUN_AGENTOPS_START.bat.txt` (rename to `.bat`) | init+resume+Korean status, then pause |
| U5 | double-click `RUN_AGENTOPS_FIX.bat.txt` (rename to `.bat`) | doctor+fix, then pause |

## Installer (P0.5) — run on the home PC before installing

| ID | Command (run from `installers_light\`) | Expected |
|----|----------------------------------------|----------|
| I1 | `py -3.11 INSTALL_OPENCODE_AGENTOPS_V3_1_COGROWTH.py.txt --dry-run` | `[INFO] Using payload: …`, `command-guard.ts present in payload and will be copied: True`, `Required-files check: OK`, `DRY_RUN_OK`. **No files written.** **[verified on Linux: 73 files, DRY_RUN_OK]** |
| I2 | In a scratch folder, run `RUN_INSTALL_OPENCODE_AGENTOPS_V3_1_COGROWTH_SAFE.bat` (rename from `.bat.txt`), then check `.opencode\plugins\command-guard.ts` exists | `INSTALL_OK`, `Command guard plugin installed: True`; the guard plugin file is present and byte-identical to the source. **[verified on Linux end-to-end]** |
| I3 | Negative: temporarily rename the payload's `command-guard.ts`, run `--dry-run` | installer prints `[ERROR] payload is missing required files: … command-guard.ts` and exits non-zero (fails loudly, never installs without the guard). |

> The installer now probes `agentops_v3_1_payload/`, `current_source/`, and its own
> parent source tree, and asserts the required files (incl. the P0-2 guard plugin)
> are present both before and after copy. `installers_light/`, `.agentops_backup/`,
> `.git/`, and `__pycache__/` are never copied into the target.

## OpenCode live (require OpenCode running) — **[Windows-only, VERIFY-ON-MACHINE]**

### T12 — both plugins load (do this first)
1. From the installed project root, run `opencode --version` and note the build.
2. Start OpenCode in the project (`ocode`). Watch the startup output.
3. **Expected:** no plugin load error for `command-guard.ts` or
   `compaction-handoff.ts`. Because both plugins have **zero npm imports**, there
   is **no** `bun install` step and **no** `.opencode/package.json` requirement —
   confirm OpenCode does not try to fetch anything (offline/망분리 safe). If a load
   error appears, capture it and stop (do not proceed to T9/T8).

### T9 — command guard blocks a corrupted bash command in the real exec path
1. Switch to the **autopilot** primary agent (Tab to `agentops-autopilot`), or run `/work test`.
2. Ask the model to run this exact command (a corrupted heredoc, the user's #1 fear):
   `cd portal_research && cat > r.py << 'EOF'`
3. **Expected (block):** OpenCode aborts the tool call and shows the thrown error
   beginning `AgentOps command guard BLOCKED this command (corrupted/unsafe).`
   followed by the reason list. The file `r.py` is **NOT** created
   (`dir portal_research\r.py` → not found).
4. **Negative control (must still run):** ask it to run `git status`.
   **Expected:** runs normally, no guard error.
5. **Second positive case:** ask it to run `printf "x" > a.conf` style or
   `python -c "open('x.py','w')"`. **Expected:** blocked (these evade OpenCode's
   own permission globs but the plugin regex catches them).
6. Cross-check the rule parity offline: `py -3.11 agent_ops\command_guard.py check "cd portal_research && cat > r.py << 'EOF'"` → `"decision": "block"`.
   If the CLI says `block` but OpenCode still runs it, the plugin did not load → re-check T12.

### T8 — compaction injects the durable handoff (additive, not replace)
1. Seed state so there is something to hand off:
   `py -3.11 agent_ops\agentops.py checkpoint --note "T8 compaction test"`
   then confirm `agent_ops\state\COMPACT_HANDOFF.md` exists and contains the run
   state + active task + the "planned, not approved" safety line.
2. Trigger compaction. Either (a) let a long OpenCode session auto-compact, or
   (b) force it via the OpenCode compaction control for the current build
   (e.g. the compact command/keybind shown in `opencode --help` for your version).
3. **Expected (additive):** after compaction, the model's first context contains
   **both** OpenCode's own summary **and** the appended block titled
   `## AgentOps durable handoff (preserve across compaction)`, which instructs it
   to read `COMPACT_HANDOFF.md`, `RESUME_PLAN.md`, `ACTIVE_TASK.json`,
   `CHECKPOINT.json` and repeats the "PLANNED, not approved" line. The original
   summary instruction must **not** be wiped (that is the P1-5 additive fix).
4. **Missing-file branch:** rename `COMPACT_HANDOFF.md` away and compact again.
   **Expected:** the block still appears but with the line
   `(COMPACT_HANDOFF.md not found at session start — run … checkpoint early.)`
   instead of silently injecting an empty handoff.
5. **Fallback if the build has no compaction hook:** the installer's `AGENTS.md`
   block already tells the model to read the handoff files at session start, so
   even without the hook the durable references survive — confirm `AGENTS.md`
   contains the `OPENCODE_AGENTOPS_V3_1_COGROWTH` block.
