---
description: Save user instruction to memory
agent: agentops-supervisor
subtask: false
---

Run:
```bash
python agent_ops/agentops.py remember $ARGUMENTS
```
Then use `/recall` or future llm_plan tasks will inject relevant memory.