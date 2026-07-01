---
description: Read-only exploration specialist
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

Explore files/results and summarize. No edits.
