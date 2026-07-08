---
description: Start here — recover state and show a plain-language status
agent: agent
subtask: false
---

This is the front door. Run these bounded commands in order:
```bash
python agent_ops/agentops.py recall --pinned
python agent_ops/agentops.py resume
python agent_ops/agentops.py status --ko
```
First apply the recalled pinned memory as session context. Then read
`RESUME_PLAN.md`, tell the user the current situation and the single recommended
next action in Korean, and wait. Do not start long loops inside OpenCode.
Anything under next_step or queue is PLANNED, not approved.
