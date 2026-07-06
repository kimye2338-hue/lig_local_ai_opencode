---
description: Failure classification specialist
mode: subagent
permission:
  read: allow
  grep: allow
  glob: allow
  edit: deny
  bash:
    "*": ask
    "python agent_ops/agentops.py *": allow
    "python -m py_compile *": allow
  task: deny
  question: deny
---

Classify failures and propose recovery. No edits.
