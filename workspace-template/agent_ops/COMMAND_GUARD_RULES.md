# AgentOps Command Guard Rules

## Problem this patch prevents

Approval windows can contain corrupted command text, for example:

```text
cat > portal_research/scripts/portal_autonomous_research_runner.py << 'EOF'
...
The content contains triple quotes and escaped newlines that broke JSON.
Let's write it line by line...
```

That is not a clean shell command. It is mixed reasoning + command text and should be rejected.

## Prevention layers

1. `agentops-autopilot` no longer has broad `bash: allow`.
2. Safe AgentOps/Python verification commands are allowed by pattern.
3. Known bad shell-generation patterns are denied:
   - `cat > *`
   - `* << *`
   - `python -c *`
   - `py -3.11 -c *`
   - `powershell *EncodedCommand*`
   - destructive commands such as `rm -rf *`
4. `agent_ops/command_guard.py` classifies proposed command text.
5. `agent_ops/safe_file_writer.py` provides a safer fallback for file generation.

## Rule of thumb

- Use OpenCode `write`/`apply_patch` for real files.
- Use `safe_file_writer.py` if shell-only creation is unavoidable.
- Never approve a modal that includes reasoning text mixed into bash.
