# Remaining Risks & Deferred Work

After the 4 P0 blockers and the Phase 1/2 hardening, AgentOps v3.1 is installable.
The items below are known, **non-blocking**, and recorded for follow-up.

## Must verify on the target machine (not a code gap)
- **Live OpenCode plugin behavior (T8/T9).** Both `.ts` plugins transpile cleanly
  (`bun build`) but their hooks only run inside OpenCode. Confirm the command guard
  blocks a corrupted heredoc in the autopilot exec path, and the compaction hook
  adds (not replaces) the durable handoff. See `VALIDATION_TODO_ON_WINDOWS.md`.
- **Windows lock branch (P0-1).** The `nt` ctypes/tasklist path only runs on
  Windows; re-run the liveness check there.
- **Korean console encoding.** `status --ko`/`fix --ko` rely on a UTF-8 console;
  the UTF-8 `STATUS_KO.md` artifact is the reliable fallback.

## Deferred review items (intentionally not implemented this pass)
- **P1-6** — `safe_file_writer.py` still writes `*.bak` beside the target instead
  of under `agent_ops/archive/backups/`. Cosmetic clutter only; `opencode.json`
  already ignores `**/*.bak`. Low priority.
- **P2-2** — `llm_client.chat` has no retry/timeout tier; a slow internal model
  raises immediately. Add 1 retry + a distinct `LLM_TIMEOUT` failure type later.
- **P2-3** — `doctor.py` chromedriver candidates include a hardcoded
  `Desktop/local_LLM/...` path. Move to config/env only with one generic fallback.
- **P2-4** — No dedicated read-only `agentops-plan` agent yet; Option C1 currently
  reuses `agentops-explorer`/supervisor as the "plan/normal" personas.
- **P4 reflection task** — repeated-failure consolidation (≥3 of one `ftype` → one
  generalized lesson) is designed in the review but not wired into the orchestrator.
- **P4 portal CDP runner** — attach-only snapshotter with action quarantine is
  **design-first** and requires explicit user sign-off; the `safety.py` classifier
  is ready, the runner is not built (and must never extract cookies/tokens).
- **Phase 3 / C2 permission-mode toggle** — design only in
  `REQUIRES_OPENCODE_SOURCE_PATCH.md`; needs an OpenCode source fork.

## Installer note (review §H) — flagged, not modified here
The reference installer (`installers_light/INSTALL_*.py.txt`) copies from a
`agentops_v3_1_payload/` directory and, as written, does **not** ship the new
`.opencode/plugins/command-guard.ts`. Before packaging an installable bundle:
1. Make the installer probe the actual source dir (e.g. also try `current_source/`).
2. Add `.opencode/plugins/command-guard.ts` to the payload file list so the P0-2
   guard actually ships.
The installer was left unmodified because the real install layout lives on the
home PC and is outside the verified edit scope of this pass.

## Residual edge cases (covered, noted for awareness)
- A worker killed **between** `claim_task` (status `active`) and `mark_task_done`
  leaves the task `active`; it is swept back to `pending` by the interruption
  recovery on next start. Consider extending `recover_interrupted_active_tasks` to
  also sweep tasks whose `claimed_at` is older than `max_age` (watchdog).
- `touches` is advisory: a write-ish task that forgets to declare `touches` can run
  concurrently with another. Mitigation (review §F): default write-ish tasks to
  `touches: ["*"]` to force serial unless explicitly narrowed.

## Recommended next step
Run `WINDOWS_TEST_PLAN.md` on the 망분리 PC (prioritize T9 live guard + T8
compaction), fix the installer payload per §H, then install. Hold the C2 fork and
the portal runner until after a source spike and explicit go-ahead.
