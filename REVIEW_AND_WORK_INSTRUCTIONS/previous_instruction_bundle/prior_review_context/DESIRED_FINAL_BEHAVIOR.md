# Desired final behavior

The user wants OpenCode AgentOps to behave like a robust self-maintaining assistant layer over an internal-network OpenCode/local LLM environment.

## Core behaviors

1. Continue-until-stopped operation
   - Work should continue across OpenCode restarts and CMD restarts.
   - Durable state must be enough to recover without relying on chat history.

2. Self-maintenance
   - Detect failure patterns.
   - Stop repeating the same failing action.
   - Delegate to specialist agents or external orchestrator.
   - Repair, verify, checkpoint, and record lessons.

3. Co-growth
   - User corrections and discovered lessons must affect future decisions.
   - Memory should not just accumulate; it must be recalled into task prompts.

4. Safe autonomy
   - Project-local files can be edited with minimal prompts in autopilot mode.
   - Risky external/portal actions remain blocked.
   - No credential/OTP/cookie/token automation.

5. Command integrity
   - Never let approval windows contain corrupted text, reasoning, fake tool calls, or half-shell/half-explanation.
   - Long file creation should use write/apply_patch/safe writer, not heredoc.

6. Claude-Code-like permission UX
   - Desired: switch permission mode independently of agent/persona, ideally via keybind.
   - Current workaround: separate `agentops-supervisor` and `agentops-autopilot`.

7. Better parallelism
   - Do not assume OpenCode subagents are parallel.
   - Use external orchestrator for safe parallel read-only/specialist analysis.
   - Serialize repair/write tasks.

8. Portal research automation
   - Eventually attach to already-authenticated Chrome.
   - Collect snapshots/reports safely.
   - Block submit/approve/delete/send/delete/upload/download unless explicitly approved.
   - Never automate login/OTP.
