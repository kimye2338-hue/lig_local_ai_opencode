# OpenCode Core Patch: Claude-Code-like Permission Mode Toggle

This folder contains a concrete source patch for the upstream OpenCode TUI/core source tree.

Target upstream repository:

```text
https://github.com/anomalyco/opencode
```

Target upstream commit inspected while preparing this patch:

```text
afff74eb2c9fc3808a9795f365707f32853099e9
```

## What this patch implements

This is the real OpenCode-side implementation path for the feature that cannot be implemented from the AgentOps layer alone.

It changes OpenCode TUI behavior from the existing two-state permission toggle:

```text
normal <-> auto
```

to a Claude-Code-like three-state mode cycle:

```text
NORMAL -> AUTO -> PLAN -> NORMAL
```

## UX

```text
Shift+Tab
```

cycles permission mode.

Because upstream OpenCode currently uses `shift+tab` for previous-agent cycling, this patch moves previous-agent cycling to:

```text
Shift+F3
```

The active agent/persona is not changed by permission-mode cycling.

The prompt footer shows a visible mode badge:

```text
[NORMAL shift+tab]
[AUTO shift+tab]
[PLAN shift+tab]
```

## Behavior by mode

### NORMAL

Existing behavior. Permission requests are shown normally.

### AUTO

Bounded auto-approval. This is intentionally not equivalent to `--dangerously-skip-permissions`.

Auto-approves read/glob/grep/list/todowrite, edit requests with filepath metadata, and obviously safe bash verification/read-only commands.

Keeps prompting or rejects external_directory, webfetch, websearch, task, doom_loop, question, plan_enter, plan_exit, dangerous/corrupted bash, and credential/token/cookie/password-like commands.

### PLAN

Rejects write/risky permission requests: edit, bash, task, webfetch, websearch, external_directory, doom_loop, question, plan_exit, and dangerous/corrupted command shapes.

Read-like requests are not auto-rejected.

## Files changed in upstream OpenCode

```text
packages/tui/src/config/keybind.ts
packages/tui/src/context/permission.tsx
packages/tui/src/context/sync.tsx
packages/tui/src/app.tsx
packages/tui/src/routes/session/index.tsx
```

## Apply

From a cloned OpenCode source tree:

```cmd
git checkout afff74eb2c9fc3808a9795f365707f32853099e9
git apply path\to\opencode-permission-mode-toggle.patch
```

On Windows, use `APPLY_AND_BUILD_PATCHED_OPENCODE.bat.txt`. Rename/copy it to `.bat` only on a trusted development PC.

## Important limitation

This repository does not contain the OpenCode upstream source tree or a built OpenCode binary. Therefore this PR can deliver the exact patch and build instructions, but the patched OpenCode executable must be built on a PC that has network/toolchain access to clone and build OpenCode.
