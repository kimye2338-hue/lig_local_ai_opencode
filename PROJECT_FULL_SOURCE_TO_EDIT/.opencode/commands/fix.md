---
description: Self-service recovery — self-heal plan + verify
agent: agentops-repair
subtask: false
---

Run the bounded fix flow:
```bash
python agent_ops/agentops.py fix --ko
```
This produces a self-heal plan from the latest failure and runs the verifier.
If the plan says user confirmation is required, stop and ask the user in Korean
before doing anything risky. Only apply small, project-local repairs; do not use
heredoc/cat/python -c to write files.
