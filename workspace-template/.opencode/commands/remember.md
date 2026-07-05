---
description: Save user instruction to memory
agent: agent
subtask: false
---

Run:
```bash
python agent_ops/agentops.py remember $ARGUMENTS
```
Then use `/recall` or future llm_plan tasks will inject relevant memory.