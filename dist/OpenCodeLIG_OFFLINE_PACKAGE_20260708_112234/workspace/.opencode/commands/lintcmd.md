---
description: Check a proposed shell command for approval-window corruption
agent: agent
subtask: false
---

Run the command guard on the proposed command text.

```bash
python agent_ops/command_guard.py check "$ARGUMENTS"
```

If decision is `block`, do not execute it. Use write/apply_patch/safe_file_writer instead.
