# Permission Mode Implementation Report

`TRUE_PERMISSION_MODE_TOGGLE_NOT_IMPLEMENTED_INSIDE_AGENTOPS_LAYER`

`TRUE_PERMISSION_MODE_TOGGLE_PATCH_DELIVERED_FOR_UPSTREAM_OPENCODE_SOURCE`

## Outcome

OpenCode core/TUI source is still not vendored inside this AgentOps repository, so the true Claude-Code-like permission mode cannot be activated by AgentOps files alone.

However, this branch now includes a concrete upstream OpenCode source patch under:

```text
PROJECT_FULL_SOURCE_TO_EDIT/opencode_core_patch/
```

That patch is intended to be applied to upstream OpenCode source commit:

```text
afff74eb2c9fc3808a9795f365707f32853099e9
```

## What is now delivered

```text
PROJECT_FULL_SOURCE_TO_EDIT/opencode_core_patch/README.md
PROJECT_FULL_SOURCE_TO_EDIT/opencode_core_patch/opencode-permission-mode-toggle.patch
PROJECT_FULL_SOURCE_TO_EDIT/opencode_core_patch/APPLY_AND_BUILD_PATCHED_OPENCODE.bat.txt
PROJECT_FULL_SOURCE_TO_EDIT/opencode_core_patch/OPENCODE_CORE_PERMISSION_MODE_PATCH_DELIVERY.md
PROJECT_FULL_SOURCE_TO_EDIT/opencode_core_patch/MANIFEST.json
```

## What the upstream patch implements

```text
- NORMAL -> AUTO -> PLAN -> NORMAL permission mode cycle
- Shift+Tab cycles permission mode
- Previous-agent cycling moves from Shift+Tab to Shift+F3
- Active agent/persona is preserved while permission mode changes
- Prompt footer displays [NORMAL shift+tab] / [AUTO shift+tab] / [PLAN shift+tab]
- AUTO is bounded auto-approval, not blind dangerous skip-permissions
- PLAN rejects write/risky permission requests
```

## Files changed by the upstream OpenCode patch

```text
packages/tui/src/config/keybind.ts
packages/tui/src/context/permission.tsx
packages/tui/src/context/sync.tsx
packages/tui/src/app.tsx
packages/tui/src/routes/session/index.tsx
```

## Keybind chosen

```text
Shift+Tab = cycle permission mode
Shift+F3 = previous agent
Tab = next agent
```

This resolves the upstream conflict where `shift+tab` originally meant previous-agent cycling.

## Permission mode behavior

### NORMAL

Existing OpenCode behavior. Permission requests are shown normally.

### AUTO

Bounded auto-approval.

Approves only safe/read-like or clearly local verification requests, including:

```text
read / glob / grep / list / todowrite
edit requests with filepath metadata
safe bash verification/read-only commands such as git status, git diff, py_compile, test/check/build
```

Still prompts or rejects risky requests such as:

```text
external_directory
webfetch / websearch
task
doom_loop
question
plan_enter / plan_exit
dangerous or corrupted bash
credential/token/cookie/password-like commands
```

### PLAN

Rejects write/risky requests:

```text
edit
bash
task
webfetch / websearch
external_directory
doom_loop
question
plan_exit
dangerous/corrupted command shapes
```

Read-like requests are not auto-rejected.

## AgentOps fallback still retained

The existing fallback persona mapping remains useful when running unpatched OpenCode:

```text
PLAN fallback   = agentops-plan
NORMAL fallback = agentops-supervisor
AUTO fallback   = agentops-autopilot
```

This fallback is not the real Claude-Code-like mode toggle. The real mode toggle requires applying and running the upstream OpenCode patch.

## Apply/build

From this folder:

```cmd
PROJECT_FULL_SOURCE_TO_EDIT\opencode_core_patch
```

Run on a trusted Windows development PC with Git and Bun installed:

```cmd
copy APPLY_AND_BUILD_PATCHED_OPENCODE.bat.txt APPLY_AND_BUILD_PATCHED_OPENCODE.bat
APPLY_AND_BUILD_PATCHED_OPENCODE.bat
```

The script clones `https://github.com/anomalyco/opencode`, checks out the target commit, applies the patch, runs Bun install/check/build, and leaves a patched OpenCode source tree at:

```text
PROJECT_FULL_SOURCE_TO_EDIT/opencode_core_patch/opencode-source/
```

## Tests run

No live OpenCode runtime tests were run in this environment.

What was completed:

```text
- Upstream OpenCode source was inspected through GitHub connector.
- Keybind chokepoint located: packages/tui/src/config/keybind.ts.
- Permission local state located: packages/tui/src/context/permission.tsx.
- Runtime permission request handling located: packages/tui/src/context/sync.tsx.
- App command registry located: packages/tui/src/app.tsx.
- Session prompt footer/status insertion point located: packages/tui/src/routes/session/index.tsx.
- Concrete patch file generated and added to this PR branch.
```

## Tests still required on target PC

```text
T1: patched OpenCode starts normally, default mode NORMAL
T2: Shift+Tab cycles NORMAL -> AUTO -> PLAN -> NORMAL
T3: active agent/persona does not change while cycling modes
T4: prompt footer displays current mode badge
T5: /permission command or palette command cycles mode
T6: PLAN blocks edit/bash/risky requests
T7: AUTO allows safe project-local edit/verification requests
T8: AUTO blocks corrupted heredoc/prose bash
T9: explicit deny still wins over AUTO
T10: dangerous submit/delete/send/upload/download/credential-like actions are not silently allowed
```

## Remaining risks

```text
- The patch targets a specific upstream OpenCode commit and may need rebasing on future OpenCode versions.
- The patch has not been built in this ChatGPT environment.
- The patch has not been live-tested in the Windows/OpenCode TUI.
- Maintaining a forked OpenCode binary has upgrade/rebase cost.
```
