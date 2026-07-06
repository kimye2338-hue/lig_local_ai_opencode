# AgentOps v3.1 Runtime Rules

<!-- OPENCODE_AGENTOPS_V3_1_COGROWTH -->

## Non-negotiable operating rules

- Do not run infinite or long-running loops inside OpenCode bash. OpenCode bash is for bounded tasks only.
- Long-running work belongs to the external Python orchestrator, started from a separate CMD.
- Do not put growing memory files in `opencode.json` instructions.
- Memory source of truth is `.agent-memory/memory.jsonl`; Markdown files are rendered views.
- Before/after compaction, read `agent_ops/state/COMPACT_HANDOFF.md` and `RESUME_PLAN.md`.
- Queue items and `next_step` are planned, not approved.
- Risky actions require explicit current-session user approval.
- File modification is owned by `agentops-repair`; supervisor and analysis agents must not directly edit files.
- Use real OpenCode tools. Do not print fake tool-call JSON such as `bash {"command": "..."}`.
