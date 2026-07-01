# OpenCode Core Permission Approval Policy Patch — Delivery

`PERMISSION_APPROVAL_POLICY_TOGGLE_PATCH_FOR_UPSTREAM_OPENCODE_SOURCE`

This package delivers an upstream OpenCode source patch that adds a Claude-Code-style
**permission approval policy** toggle. It lives here because this AgentOps
repository does not vendor the OpenCode core/TUI source tree.

## Added files

```text
opencode_core_patch/
  README.md
  opencode-permission-mode-toggle.patch
  APPLY_AND_BUILD_PATCHED_OPENCODE.bat.txt
  OPENCODE_CORE_PERMISSION_MODE_PATCH_DELIVERY.md
  MANIFEST.json
```

## What the patch implements

```text
- ASK -> AUTO -> ASK approval-policy cycle (2 states, not 3)
- Shift+Tab toggles the approval policy only
- Previous-agent cycling moves from Shift+Tab to Shift+F3 (Tab still = next agent)
- Active agent/persona is NOT changed by the toggle
- Current workflow and current model are NOT changed by the toggle
- Prompt shows [PERM:ASK shift+tab] / [PERM:AUTO shift+tab], separate from the agent name
- /permission status|ask|auto|cycle controls only the approval policy
- AUTO auto-approves only requests that reach the TUI as "permission.asked";
  explicit core "deny" is never bypassed
- command-guard.ts keeps blocking dangerous bash in every policy
```

This is intentionally **not** a workflow-mode switch (no PLAN/NORMAL) and **not**
an agentops persona switch. Permission approval is a layer above agent selection.

## Apply/build

```cmd
copy APPLY_AND_BUILD_PATCHED_OPENCODE.bat.txt APPLY_AND_BUILD_PATCHED_OPENCODE.bat
APPLY_AND_BUILD_PATCHED_OPENCODE.bat
```

The script clones `https://github.com/anomalyco/opencode`, checks out commit
`afff74eb2c9fc3808a9795f365707f32853099e9`, applies the patch, then runs
`bun install` / `bun run check` / `bun run build`.

## Verification note

The patch is internally consistent (valid unified-diff hunks) and targets the
inspected upstream locations for that commit, but it has not been `git apply`-checked
or built in this environment (no network to clone upstream). Run
`git apply --check` on the target machine first; adjust context lines if upstream
has drifted from the pinned commit.
