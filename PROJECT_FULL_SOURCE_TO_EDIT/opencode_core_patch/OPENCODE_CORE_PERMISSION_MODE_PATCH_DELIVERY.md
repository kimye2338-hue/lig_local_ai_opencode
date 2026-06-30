# OpenCode Core Permission Mode Patch Delivery

`TRUE_PERMISSION_MODE_TOGGLE_PATCH_DELIVERED_FOR_UPSTREAM_OPENCODE_SOURCE`

This package contains a concrete implementation patch for upstream OpenCode. It was prepared because this AgentOps repository does not contain the OpenCode core/TUI source tree.

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
- NORMAL -> AUTO -> PLAN -> NORMAL permission mode cycle
- Shift+Tab cycles permission mode
- Previous-agent cycling moves from Shift+Tab to Shift+F3
- Active agent/persona is preserved
- Prompt footer displays current permission mode
- AUTO becomes bounded auto-approval, not blind dangerous auto-approve
- PLAN rejects write/risky permission requests
```

## Apply/build

```cmd
copy APPLY_AND_BUILD_PATCHED_OPENCODE.bat.txt APPLY_AND_BUILD_PATCHED_OPENCODE.bat
APPLY_AND_BUILD_PATCHED_OPENCODE.bat
```

The script clones `https://github.com/anomalyco/opencode`, checks out commit `afff74eb2c9fc3808a9795f365707f32853099e9`, applies the patch, then tries Bun install/check/build.
