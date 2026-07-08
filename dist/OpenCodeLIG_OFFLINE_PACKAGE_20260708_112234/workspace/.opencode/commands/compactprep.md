---
description: Prepare compact handoff
agent: agent
subtask: false
---

Run:
```bash
python agent_ops/agentops.py checkpoint --note compactprep
python agent_ops/agentops.py memorycheck
python agent_ops/agentops.py status
```
Confirm COMPACT_HANDOFF.md exists. Plugin hook may enforce this if supported.