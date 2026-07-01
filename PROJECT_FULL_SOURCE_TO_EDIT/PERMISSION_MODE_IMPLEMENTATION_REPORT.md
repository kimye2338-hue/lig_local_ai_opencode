# Permission Approval Policy — Implementation Report

`PERMISSION_APPROVAL_POLICY_TOGGLE_PATCH_DELIVERED_FOR_UPSTREAM_OPENCODE_SOURCE`

## Goal

A Claude-Code-style **permission approval policy** toggle that is independent of
agent/persona, workflow, and model. Shift+Tab flips only how permission requests
are handled — not the agent, not the mode, not the model.

```text
ASK  = show permission requests to the user (default OpenCode behavior)
AUTO = auto-approve requests that reach the TUI as "permission.asked"
Cycle: ASK -> AUTO -> ASK
```

## Where it is implemented

OpenCode core/TUI source is not vendored in this AgentOps repository, so the
toggle ships as an upstream source patch under:

```text
PROJECT_FULL_SOURCE_TO_EDIT/opencode_core_patch/
```

Target upstream commit:

```text
afff74eb2c9fc3808a9795f365707f32853099e9
```

## Files changed by the patch

```text
packages/tui/src/config/keybind.ts          Shift+Tab -> permission toggle; prev-agent -> Shift+F3
packages/tui/src/context/permission.tsx     mode "ask" | "auto"; default ASK; set()/cycle()
packages/tui/src/app.tsx                     "permission.mode" command cycles; exposes /permission
packages/tui/src/component/prompt/index.tsx  /permission status|ask|auto|cycle
packages/tui/src/routes/session/index.tsx    [PERM:ASK|AUTO shift+tab] badge, separate from agent name
```

`context/sync.tsx` is intentionally **not** patched: upstream already replies
`once` to `permission.asked` when `mode === "auto"`, so keeping the value `"auto"`
means AUTO works through existing core behavior with no new event-handling code.

## Keybind

```text
Tab      = next agent
Shift+F3 = previous agent
Shift+Tab= toggle permission approval policy (ASK/AUTO)
```

This resolves the upstream conflict where `shift+tab` meant previous-agent cycling.

## Behavior

### ASK
Default OpenCode behavior. A `permission.asked` event shows the normal prompt.

### AUTO
The TUI auto-replies `once` to `permission.asked`. It does not pop a prompt for
each request.

AUTO cannot bypass safety:
- Explicit `deny` is resolved in opencode core
  (`packages/opencode/src/permission/index.ts`) before a request becomes an
  `ask`, so it never reaches the TUI and AUTO can never override it.
- `.opencode/plugins/command-guard.ts` still blocks corrupted/dangerous bash in
  `tool.execute.before`, independent of the approval policy.

AUTO is not `--dangerously-skip-permissions`; it only auto-approves the `ask`-level
requests the core resolver already allowed to surface.

## Independence guarantees (the success criterion)

```text
Shift+Tab / /permission changes only session-level approval policy.
It does not call any agent-switch or model-switch code path.
permission.tsx holds mode independently of agent state; toggling never writes agent/model.
```

## Relationship to the AgentOps fallback personas

`agentops-plan` / `agentops-supervisor` / `agentops-autopilot` remain as ordinary
personas for unpatched OpenCode. They are **not** the permission toggle and are no
longer described as a permission mechanism. The real toggle is this core patch.

## Tests

No live OpenCode runtime tests were run here (no upstream clone / no TUI in this
environment). Static work completed:

```text
- Reworked the patch from a 3-state workflow-mode design to a 2-state ASK/AUTO approval policy.
- Removed PLAN and all workflow/persona framing.
- Verified every hunk's unified-diff line counts are internally consistent.
- Confirmed the design reuses upstream core auto-approve (no sync.tsx change needed).
```

Runtime tests required on the target machine (Git + Bun + OpenCode TUI):

```text
T1  start -> approval policy is ASK
T2  Shift+Tab -> ASK to AUTO
T3  Shift+Tab -> AUTO to ASK
T4  agent/persona unchanged across toggles
T5  model unchanged across toggles
T6  AUTO auto-replies "once" to permission.asked
T7  ASK shows the normal prompt
T8  explicit deny not bypassed by AUTO
T9  command-guard.ts still blocks dangerous bash under AUTO
T10 /permission ask|auto|cycle|status changes only the approval policy
```

## Remaining risks

```text
- Patch targets a pinned upstream commit; may need context rebasing on newer OpenCode.
- Not git-apply-checked or built in this environment (no upstream network access here).
- Not live-tested in the OpenCode TUI yet.
- Maintaining a forked OpenCode binary has upgrade/rebase cost.
```
