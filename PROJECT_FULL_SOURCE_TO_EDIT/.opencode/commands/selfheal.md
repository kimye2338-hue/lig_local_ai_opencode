---
description: Create self-heal plan
agent: agentops-failure-analyst
subtask: true
---

Run:
```bash
python agent_ops/agentops.py selfheal
```
If the plan requires edits, delegate to `agentops-repair`; analyst does not edit.