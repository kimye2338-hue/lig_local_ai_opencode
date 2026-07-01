---
description: Do one bounded goal in guarded Autopilot mode
agent: agentops-autopilot
subtask: false
---

You are using guarded AgentOps Autopilot for one bounded goal.

User goal:
$ARGUMENTS

Execute project-local work directly, but do NOT use heredoc/cat/long echo/python -c
to create files — use write/apply_patch or `python agent_ops/safe_file_writer.py`.
If an approval modal contains prose mixed with command text, reject it. Do not run
long loops inside OpenCode; enqueue with `/enqueue` and let the external orchestrator
BAT run them. Risky actions (submit/approve/delete/upload/download) require explicit
current-session user approval.
