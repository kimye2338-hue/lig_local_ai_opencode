# Workspace template

This folder is copied into the offline package as `workspace/`, then installed to:

```text
%USERPROFILE%\OpenCodeLIG\workspace
```

It contains:

- `.opencode/` local OpenCode commands, agents, and plugins
- `agent_ops/` Python runtime helpers
- `RUN_AGENTOPS_*.bat.txt` launcher templates

The package workflow also copies repository `docs/` and `patches/` into the installed workspace so future Codex/Claude sessions can recover project context from the company PC.

Do not put old review prompt bundles or optional installer experiments here. Keep runtime files here, and keep context in `docs/`.
