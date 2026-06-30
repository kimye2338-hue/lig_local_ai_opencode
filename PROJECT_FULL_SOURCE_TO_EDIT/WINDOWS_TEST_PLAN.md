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

## OpenCode live (require OpenCode running) — **[Windows-only, VERIFY-ON-MACHINE]**

| ID | Step | Expected |
|----|------|----------|
| T9 | In OpenCode autopilot, attempt `cd portal_research && cat > r.py << 'EOF'` | OpenCode shows the thrown **AgentOps command guard BLOCKED** error; command does NOT run. Negative: `git status` runs normally. |
| T8 | Trigger compaction in a long OpenCode session (or inspect after `... checkpoint --note test`) | The durable handoff block is **added** to the summary context (additive), referencing COMPACT_HANDOFF.md / RESUME_PLAN.md and the "PLANNED, not approved" safety line. |
| T12 | Confirm both plugins load: `opencode --version`, then start a session | no plugin load error; zero npm imports means no Bun install needed (offline-safe). |
