---
description: Create or update files without heredoc/cat/long python -c
agent: agent
subtask: false
---

For long files, do not use `cat >`, heredoc, long echo, or python -c.

Preferred:
1. Use OpenCode write/apply_patch.
2. Or create content in a project-local staging file, then run:
   `python agent_ops/safe_file_writer.py <target> --content-file <staging-file>`

After Python files, verify with:
`python -m py_compile <target>`
