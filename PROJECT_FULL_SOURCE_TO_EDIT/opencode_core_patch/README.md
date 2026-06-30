# OpenCode Core Patch: Permission Approval Controller

## Current status

`NEEDS_REWORK_BEFORE_USE`

This folder contains an upstream OpenCode patch draft, but the current draft should not be treated as final.

The required feature is not a workflow mode such as PLAN or AUTO and not an AgentOps persona switch. The required feature is an independent, higher-level permission approval controller similar to Claude Code's Shift+Tab behavior.

## Correct target behavior

```text
Shift+Tab changes permission approval behavior only.
The active agent/persona must not change.
The current task/workflow mode must not change.
The current model must not change.
The current approval state must be visible in the TUI.
```

The approval controller should sit above normal agent/persona selection.

## What must be fixed in the patch

The existing patch draft is too tied to mode names such as PLAN/NORMAL/AUTO. That framing is misleading for the user's requirement.

The corrected patch should use approval-policy language, for example:

```text
ASK    = show approval requests normally
AUTO   = approve permission requests from the TUI controller
```

or whatever names best match upstream OpenCode and Claude Code behavior.

The important point is this:

```text
Permission approval is independent from agent/persona and independent from task/planning mode.
```

## Upstream target

```text
https://github.com/anomalyco/opencode
```

Target commit inspected while preparing the draft:

```text
afff74eb2c9fc3808a9795f365707f32853099e9
```

## Files likely involved in upstream OpenCode

```text
packages/tui/src/config/keybind.ts
packages/tui/src/context/permission.tsx
packages/tui/src/context/sync.tsx
packages/tui/src/app.tsx
packages/tui/src/component/prompt/index.tsx
packages/tui/src/routes/session/index.tsx
```

## Required next step

A human or Claude Code should revise `opencode-permission-mode-toggle.patch` so that it implements an independent permission approval controller, not a workflow/persona mode.

After revision, verify:

```text
1. Shift+Tab changes only approval behavior.
2. Agent/persona remains unchanged.
3. The mode indicator reflects approval state only.
4. Direct commands such as /permission status, /permission ask, /permission auto, and /permission cycle work if supported.
5. Existing command guard behavior remains separate from approval-state switching.
```
