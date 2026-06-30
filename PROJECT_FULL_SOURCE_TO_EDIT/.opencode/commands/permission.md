---
description: Show/explain AgentOps permission-mode fallback (plan/normal/auto)
agent: agentops-supervisor
subtask: false
---

Requested mode (if any): $ARGUMENTS

**There is no true session-level permission-mode toggle in this build.** A real
Claude-Code-style PLAN/NORMAL/AUTO hotkey (same agent, only permission behavior
changes) requires an OpenCode core source patch — see
`OPENCODE_PERMISSION_MODE_PATCH_SPEC.md`. This command always runs as
`agentops-supervisor`; it cannot change the live session's active primary
agent or any real permission state, so it can only report and explain — it is
not itself a mode switch.

Fallback mapping shipped today (Option C1 — mode-as-persona, no core patch):

| Mode | Primary agent | How to actually switch |
|---|---|---|
| plan | `agentops-plan` | Tab-cycle to it, or pick it in the agent selector |
| normal | `agentops-supervisor` | Tab-cycle to it (also the default) |
| auto | `agentops-autopilot` | Tab-cycle to it, or run `/autopilot <task>` / `/work <goal>` for one scoped task without switching persistently |

If `$ARGUMENTS` named a mode (`plan`, `normal`, or `auto`), tell the user
plainly: "this command cannot switch you into that mode — Tab-cycle to
`agentops-<mode>`, or use `/autopilot`/`/work` for one-off auto-mode work."
If `$ARGUMENTS` was `status` or empty, report:
1. The fallback table above.
2. That `.opencode/plugins/command-guard.ts` blocks corrupted/dangerous bash
   in every mode regardless of which agent is active — that protection is not
   mode-dependent.
3. A pointer to `OPENCODE_PERMISSION_MODE_PATCH_SPEC.md` for what a true
   toggle would require and why it isn't implemented here.

Do not claim this command changed the permission mode. Do not run bash to
"simulate" a mode change.
