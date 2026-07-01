# Optional runtime files to add from the actual home PC

The package includes the current source snapshot, Opus feedback, and implementation prompt. It does NOT include the user's actual home-PC runtime state.

If available, add these files/folders before running Claude Code so it can validate against real state:

```text
opencode.json
AGENTS.md
.opencode/agents/
.opencode/commands/
.opencode/plugins/
agent_ops/state/RUN_STATE.json
agent_ops/state/CHECKPOINT.json
agent_ops/state/ACTIVE_TASK.json
agent_ops/state/TASK_QUEUE.jsonl
agent_ops/state/RESUME_PLAN.md
agent_ops/state/COMPACT_HANDOFF.md
agent_ops/reports/STATUS.md
agent_ops/reports/VERIFICATION_REPORT.md
agent_ops/logs/*.jsonl
agentops_command_guard_patch_log.txt
agentops_v31_install_log.txt
```

Do NOT add these unless specifically needed:

```text
__pycache__/
.agentops_backup/large historical backups
agent_ops/archive/large backups
portal_research/screenshots/*
portal_research/html_snapshots/*
one-file base64 installers
OpenCode binary zips
```

Also provide command outputs if possible:

```cmd
ocode --version
py -3.11 --version
python --version
```
