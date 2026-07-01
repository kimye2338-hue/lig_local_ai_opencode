# AI handoff

This is the single shared handoff file for Codex, Claude Code, Claude chat, and future reviewers.

## Current state

The repository builds one current offline Windows package through one workflow:

- Workflow: `.github/workflows/build-offline-package.yml`
- Patch: `patches/opencode-permission-mode-toggle.patch`
- Workspace copied into the package: `workspace-template/`
- Pinned upstream OpenCode commit: `afff74eb2c9fc3808a9795f365707f32853099e9`

PR #4 was merged into `main` on 2026-07-01.

Important commits:

- PR #4 merge: `bde4cc036d091bb35971999faf7a4394b8865ddf`
- Repository cleanup: `2ac5d4aa99476fe80a44ba5b42391747aee3de11`

Verified cleanup baseline:

- Workflow run: `28505265540`
- Artifact ID: `8004882821`
- Artifact digest: `sha256:2d52e390461b732491eadafcde025ec7f329577d40e7e1f52618be6aab991115`
- `payload/opencode.exe` SHA256: `5fa524bbddb547fcbc776bf15c824945dcdd538b6aaccc077db4b47ff521545e`
- Artifact ZIP SHA matched GitHub digest.
- `SHA256SUMS.txt` verified 81 files with 0 mismatches.
- Hidden workspace files were present.
- `workspace/docs/AI_HANDOFF.md` and `workspace/patches/opencode-permission-mode-toggle.patch` were present.

If a newer successful workflow run exists on `main`, use that newer artifact. The baseline above is the last manually downloaded and checksum-verified artifact.

## User-reported crash and fix

Reported symptom:

```text
OpenCode crashed unexpected error stop the session reconciler unknown component type spinner
```

Root cause:

The offline Windows TUI rendered custom `<spinner>` JSX while the bundled OpenTUI reconciler did not know that renderable type. The reconciler crashed before useful work could proceed.

Fix:

- Remove direct `<spinner>` render paths from the patched offline build.
- Render stable text/status output instead.
- Keep the user-visible tradeoff explicit: no tiny spinner animation, but no session crash when OpenCode starts working.

Do not reintroduce `<spinner>` in this offline build unless a future OpenTUI/runtime version proves the renderable is registered and the Windows artifact is runtime-tested.

## Required behavior

The patch must implement a permission approval policy toggle independent from OpenCode agent/persona/workflow/model state.

Checklist:

- `Shift+Tab` toggles permission policy only.
- `Shift+Tab` does not cycle agent/persona/workflow/model/plan/autopilot.
- Previous-agent reverse cycle is `Shift+F3`.
- TUI displays current mode, for example `[PERM:ASK shift+tab]` or `[PERM:AUTO shift+tab]`.
- `/permission status`, `/permission ask`, `/permission auto`, `/permission cycle` work.
- `/perm status`, `/perm ask`, `/perm auto`, `/perm cycle` work.
- AUTO replies to permission requests with `reply: "once"`.
- AUTO must not use `reply: "always"`.
- AUTO must not bypass command guard or explicit deny behavior.
- ASK mode must preserve the original prompt flow.
- Reject, always, and subagent reject flows must not be broken.

## Implementation highlights

The patch changes these upstream OpenCode files after applying to the pinned commit:

- `packages/tui/src/config/keybind.ts`
  - moves `agent_cycle_reverse` from `shift+tab` to `shift+f3`
  - adds `permission_mode_cycle: shift+tab`
  - maps `permission_mode_cycle` to command `permission.mode`
- `packages/tui/src/context/permission.tsx`
  - uses `PermissionMode = "ask" | "auto"`
  - defaults to `args.auto ? "auto" : "ask"`
  - adds `set`, `cycle`, and `toggle`
- `packages/tui/src/app.tsx`
  - registers `permission.mode`
  - command calls `local.permission.cycle()`
- `packages/tui/src/component/prompt/index.tsx`
  - handles `/permission ...` and `/perm ...` commands locally
- `packages/tui/src/routes/session/index.tsx`
  - registers the binding and displays the permission badge
- `packages/tui/src/routes/session/permission.tsx`
  - uses request-id tracking for AUTO duplicate prevention
  - replies with `reply: "once"`
- `packages/tui/src/component/spinner.tsx`
  - falls back to text instead of custom `<spinner>`
- `packages/opencode/src/cli/cmd/run/footer.subagent.tsx`
  - uses status text/icon instead of direct `<spinner>`
- `packages/opencode/src/cli/cmd/run/footer.view.tsx`
  - removes the busy footer direct `<spinner>` block

## Packaging decisions

- GitHub artifact uploads the package directory, not a pre-compressed inner ZIP.
- `actions/upload-artifact@v4` uses `include-hidden-files: true` so `.opencode` files survive.
- `SHA256SUMS.txt` is generated and verified with hidden files included.
- Installer verifies `payload/opencode.exe` before copying.
- Installer backs up an existing `%USERPROFILE%\OpenCodeLIG` before overwriting.
- The package workspace includes `docs/` and `patches/` so future local AI sessions can recover context from the installed machine.

## Collaboration protocol

When an AI agent changes behavior or packaging:

1. Update this file with the new current state.
2. Update `docs/CURRENT_RELEASE.md` if a new artifact is manually downloaded and verified.
3. Update `docs/CHANGELOG.md` with the decision and user impact.
4. Keep old review material condensed in `docs/ARCHIVE_SUMMARY.md`; do not add a new large instruction bundle.
5. Report exact workflow run ID, artifact ID, digest, and verification results.

## Remaining manual validation

Before company-wide use, validate on the target Windows PC:

- `Shift+Tab` toggles ASK/AUTO in the actual terminal.
- `Shift+F3` still reaches previous-agent behavior.
- `/permission` and `/perm` variants behave identically.
- AUTO handles multiple consecutive permission prompts once each.
- ASK, reject, always, and subagent reject still behave as upstream intended.
- Command guard blocks dangerous bash/corrupted approval-window commands.
- OpenCode no longer crashes with `unknown component type spinner` when asked to do work.
