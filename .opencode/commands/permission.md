---
description: Show or change the session permission mode (normal / plan / auto)
---

# Permission mode

OpenCode has been patched with a **Claude-Code-like, session-level permission
mode**. The mode changes only how tool calls are approved — it does **not**
change the active agent/persona.

> True mode switching IS available in this build. The patched core resolver
> (`PermissionV2`) reads a per-session mode and overlays it on the normal
> permission decision. (Earlier fallback builds only swapped agents; that is no
> longer the primary mechanism.)

## Toggle

- **`shift+tab`** — cycle `NORMAL → AUTO → PLAN → NORMAL`
- **`<leader>p`** (leader = `ctrl+x`) — same cycle (fallback if your terminal
  intercepts `shift+tab`)
- The current mode is shown in the prompt footer as `[MODE: NORMAL|AUTO|PLAN]`.

## Slash commands

- `/permission` — cycle to the next mode
- `/permission-plan` — switch to PLAN
- `/permission-normal` — switch to NORMAL
- `/permission-auto` — switch to AUTO
- `/permission-status` — show the current mode

## Modes

| Mode | Behavior |
|------|----------|
| **NORMAL** | Stock OpenCode behavior. Existing project/global/agent permission config applies unchanged. Explicit `deny` always wins. |
| **PLAN** | Read/inspect only. Reads/list/glob/grep allowed; edit/write require approval; bash requires approval; external-directory edits denied; network denied unless config already allows it. Prevents accidental changes. |
| **AUTO** | Autonomous project-local work. Reads allowed; project-local edits allowed; safe verification commands (e.g. `git status`, `bun test`, `ls`) allowed; ambiguous bash still asks; dangerous/corrupted bash denied; external-directory edits denied; credential/OTP/cookie/token extraction denied; submit/delete/send/upload/download not auto-allowed. |

AUTO is **not** "dangerously-skip-permissions": explicit `deny` and the command
guard always win, and only bounded safe operations are auto-approved.

## Notes

- The agent reverse-cycle that used to be on `shift+tab` is now on
  `<leader>shift+tab`.
- There is a separate, orthogonal `--auto` client flag / "Enable auto-approve
  permissions" command that blanket-approves every prompt. That is a different,
  power-user escape hatch and is independent of this mode system.
