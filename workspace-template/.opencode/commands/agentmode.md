---
description: Explain AgentOps mode choices
agent: agentops-supervisor
subtask: false
---

AgentOps modes:

- agentops-supervisor: cautious supervisor. edit denied, bash mostly ask.
- agentops-autopilot: permission-skip mode. project-local edit/bash allowed.
- agentops-repair: subagent allowed to edit files.

Use `/autopilot <task>` or switch primary agent to `agentops-autopilot`.
