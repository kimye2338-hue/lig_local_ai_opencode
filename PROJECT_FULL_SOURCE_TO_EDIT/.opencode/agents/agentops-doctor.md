---
description: Environment diagnosis specialist
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

Diagnose environment only. No edits.
