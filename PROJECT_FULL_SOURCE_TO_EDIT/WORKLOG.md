# AgentOps v3.1 — Implementation WORKLOG

Token-economy log per `00_START_HERE_CLAUDE_CODE_LOW_TOKEN_OPUS_MANAGER.md`.
Only files changed / tests run / failures / next targets are recorded.

## Phase 0 — P0 blockers (COMPLETE, validated)

| Item | Files changed | Validation | Result |
|------|---------------|------------|--------|
| P0-1 Windows lock fix | `agent_ops/core.py` (`_pid_alive`, `_lock_is_stale`) | `py_compile`; `_pid_alive(self)` / `_pid_alive(999999)` | compiles; `True` / `False` ✓ |
| P0-2 command guard plugin | `.opencode/plugins/command-guard.ts` (new) | `command_guard.py check` parity; `bun build` | block/block/allow/ask ✓; transpiles ✓ |
| P0-3 parallel claim/race | `agent_ops/queue_manager.py` (`claim_task`), `agent_ops/orchestrator.py` (`run_task_parallel`, `_CKPT_LOCK`) | `py_compile`; 6-task parallel drain | each task `done` once, no `attempt_count>1` ✓ |
| P0-4 keyless LLM gateway | `agent_ops/llm_client.py` (`is_configured`, `chat`) | `py_compile`; keyless gate | `configured True` with `AGENTOPS_LLM_NO_AUTH=1`; `False` without ✓ |

Phase 0 validation all green → proceeding to Phase 1.

### Notes
- Workers in the parallel path no longer write the shared `ACTIVE_TASK.json` /
  `CHECKPOINT.json`; checkpoint is updated once per batch under `_CKPT_LOCK`.
- `attempt_count` is incremented only by `mark_task_running` (serial path) and
  `claim_task` (parallel path).
- TS plugin has zero npm imports → offline/망분리 safe; live OpenCode behavior is
  VERIFY-ON-MACHINE (test T9).
- Added `.gitignore` so AgentOps runtime state (`state/`, `logs/`, `.agent-memory/`,
  etc.) and `__pycache__` are not committed.

## Phase 1 — reliability (pending)
Targets: `queue_manager.py` (retry backoff), `memory_manager.py` + `failures.py`
(anti-bloat), `core.py` + `safe_file_writer.py` (.bat.txt ASCII),
`compaction-handoff.ts` (additive), `agentops.py` (`/status` read-only).

## Phase 2 — UX (pending)
Front-door commands, Korean status, dashboard, runners.

## Phase 3 — design doc only (pending)
`REQUIRES_OPENCODE_SOURCE_PATCH.md`.
