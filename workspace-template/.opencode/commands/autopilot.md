---
description: Run one request in guarded AgentOps Autopilot mode
agent: agentops-autopilot
subtask: false
---

You are using guarded AgentOps Autopilot.

User request:
$ARGUMENTS

Execute project-local work directly, but do not use heredoc/cat/long echo/python -c to create files. Use write/apply_patch/safe_file_writer. If an approval modal contains prose mixed with command text, reject it.
