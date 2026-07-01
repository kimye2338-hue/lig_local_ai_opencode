# OpenCode Permission Patch Review Handoff

This document is the shared handoff point for Codex, Claude Code, Claude chat, and other AI reviewers working on this repository.

## Current state summary

The repository currently builds a patched offline OpenCode Windows package through GitHub Actions.

Latest important commits:

- `0d412fc8c89560c777f3adb7c477cbb5ed6d5c42` — Add AI agent handoff instructions.
- `81e0cbd1933aa95616291d5e905c2e32eaf2cede` — Complete OpenCode permission auto approval patch.
- `0b065c380b9ede7f9bd86c492e447e8511b94302` — Harden offline OpenCode workflow verification.

Last known successful package run:

- Run ID: `28494990662`
- Workflow: `Build patched OpenCode offline package`
- Artifact: `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE`
- Artifact ID: `8000706677`
- Artifact digest: `sha256:14f4f9ba4144f5879fd5e2c49fefb0371ec415bf62baf50f057bfd75129f82b3`

Reported successful verification from that run:

- `git apply --check`: success
- `git apply --recount --check`: success
- `git apply --recount`: success
- `bun install`: success
- `bun run --cwd packages/opencode typecheck`: success
- `bun run --cwd packages/opencode build --single --skip-embed-web-ui`: success
- Windows x64 binary smoke test: success
- `opencode.exe --version`: `0.0.0--202607010513`
- Offline ZIP contains `payload/opencode.exe`
- Extracted artifact `payload/opencode.exe --version`: success

## Source-of-truth files

Do not create duplicate parallel implementations unless explicitly asked.

Primary implementation files:

- `.github/workflows/build-patched-opencode-offline.yml`
- `PROJECT_FULL_SOURCE_TO_EDIT/opencode_core_patch/opencode-permission-mode-toggle.patch`

Generated package contents are expected to include:

- `payload/opencode.exe`
- `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt`
- `README_OFFLINE_INSTALL.md`
- `SHA256SUMS.txt`
- `workspace/...`
- `workspace/opencode_core_patch/opencode-permission-mode-toggle.patch`

## Required behavior

The patch must implement a permission approval policy toggle, independent from OpenCode's agent/persona/workflow/model state.

Required behavior checklist:

- `Shift+Tab` toggles permission policy only.
- `Shift+Tab` does not cycle agent/persona/workflow/model/plan/autopilot.
- Previous agent reverse cycle is moved to `Shift+F3`.
- TUI displays current mode, e.g. `[PERM:ASK shift+tab]` or `[PERM:AUTO shift+tab]`.
- `/permission status` shows current permission mode.
- `/permission ask` sets ASK.
- `/permission auto` sets AUTO.
- `/permission cycle` toggles ASK/AUTO.
- `/perm` alias should behave consistently if command alias support is present.
- `AUTO` replies to permission requests with `reply: "once"`.
- `AUTO` must not use `reply: "always"`.
- `AUTO` must not bypass command guard or explicit deny behavior.
- ASK mode must preserve the original prompt flow.
- Reject / always / subagent reject flows must not be broken.

## Current implementation highlights

The patch currently changes these upstream OpenCode files after applying to pinned commit `afff74eb2c9fc3808a9795f365707f32853099e9`:

- `packages/tui/src/config/keybind.ts`
  - moves `agent_cycle_reverse` from `shift+tab` to `shift+f3`
  - adds `permission_mode_cycle: shift+tab`
  - maps `permission_mode_cycle` to command `permission.mode`

- `packages/tui/src/context/permission.tsx`
  - changes `PermissionMode` from `"auto" | "normal"` to `"ask" | "auto"`
  - defaults to `args.auto ? "auto" : "ask"`
  - adds `set`, `cycle`, and `toggle`

- `packages/tui/src/app.tsx`
  - registers `permission.mode`
  - command calls `local.permission.cycle()`

- `packages/tui/src/component/prompt/index.tsx`
  - handles `/permission status`, `/permission ask`, `/permission auto`, `/permission cycle`

- `packages/tui/src/routes/session/index.tsx`
  - registers `permission.mode` in session bindings
  - adds `PermissionModeBadge`

- `packages/tui/src/routes/session/permission.tsx`
  - imports `createEffect` and `useLocal`
  - adds `replyOnce()` helper
  - when `local.permission.mode === "auto"` and `store.stage === "permission"`, replies once automatically
  - replaces manual once reply body with `replyOnce()`

## Known areas requiring serious audit

Do not treat these as already proven safe just because typecheck/build passed.

1. `autoReplied` is a local variable inside `PermissionPrompt`. Review whether this safely prevents duplicate replies across SolidJS reactivity and component remounts.
2. `createEffect` auto reply timing: confirm it cannot reply after the user switches back to ASK or after stage changes.
3. Reply failure handling: current `void sdk.client.permission.reply(...)` may swallow failures. Review whether this is acceptable.
4. `/permission` parser is implemented directly in prompt handling. Review whether it conflicts with app command slash registration or shell mode handling.
5. `/perm` alias is registered in app command metadata, but direct prompt parser only matches `/permission`. Review whether alias actually works.
6. Badge location and layout in prompt right slot may affect TUI layout. Review runtime risk.
7. `Shift+Tab` terminal behavior may differ by terminal. Build success does not prove key recognition.
8. AUTO applies to all surfaced permissions. Review whether high-risk permissions such as `bash`, `edit`, `webfetch`, and `external_directory` should remain ASK or require a second policy.
9. Installer has no existing-install backup. Review whether this is acceptable for company PC use.
10. SHA256SUMS is generated, but installer does not enforce verification. Review whether manual verification is enough.

## Workflow review points

The workflow currently:

- triggers on `workflow_dispatch` and selected push paths
- uses `windows-latest`
- uses `actions/checkout@v4`, `oven-sh/setup-bun@v2`, and `actions/upload-artifact@v4`
- pins upstream OpenCode commit
- enables `$PSNativeCommandUseErrorActionPreference = $true` in PowerShell run steps
- applies patch with `git apply --recount --check` and `git apply --recount`
- runs `bun install`, typecheck, build
- locates built `opencode.exe`
- assembles offline ZIP
- verifies ZIP contains `payload/opencode.exe`
- smoke tests extracted `payload/opencode.exe --version`

Reviewers should consider:

- whether `windows-latest` should be pinned to a specific Windows image
- whether GitHub actions should be SHA-pinned
- whether binary selection logic can accidentally select a non-Windows binary
- whether `SHA256SUMS.txt` should be verified after archive extraction
- whether the artifact should include a release manifest with commit/run/workflow metadata

## Recommended collaboration protocol

When using multiple AI agents:

1. One agent performs full audit and lists issues only.
2. Another agent fixes only accepted issues.
3. The fixing agent must update this handoff file if it changes source-of-truth behavior.
4. Do not let multiple agents create parallel workflows or competing patch files.
5. Keep the final build path centered on `build-patched-opencode-offline.yml` and `opencode-permission-mode-toggle.patch`.

## Report format expected from reviewers

Use this structure:

1. Final verdict: `PASS`, `PASS_WITH_RUNTIME_VALIDATION_REQUIRED`, `PASS_WITH_MINOR_FIXES_REQUIRED`, `FAIL_NEEDS_FIX`, or `INCONCLUSIVE`.
2. Hunk-by-hunk review of the patch.
3. Runtime flow tracing:
   - Shift+Tab → permission.mode → cycle
   - `/permission` command handling
   - AUTO permission.asked → reply once
   - explicit deny / command guard interaction
4. Workflow audit.
5. Installer/offline package audit.
6. Findings by severity: Critical / High / Medium / Low.
7. Concrete improvement plan.
8. Tests that must be performed on the company Windows PC.
