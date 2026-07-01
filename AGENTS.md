# AI Agent Instructions

This repository is used to build and review a patched offline OpenCode package for the user's Windows company PC.

## Read these first

Before doing any work, read:

1. `AGENTS.md` — this file.
2. `AI_REVIEW_HANDOFF.md` — current project state, source-of-truth files, run IDs, and review/fix protocol.

## Primary goal

The goal is **not** to modify OpenCode agent/persona/workflow/model behavior.

The goal is:

- `Shift+Tab` toggles only the permission approval policy between `ASK` and `AUTO`.
- `Shift+Tab` must not cycle agents, personas, workflow mode, plan mode, or model variants.
- Existing agent reverse cycling must be moved away from `Shift+Tab`, currently to `Shift+F3`.
- TUI must clearly show the current permission mode, e.g. `[PERM:ASK shift+tab]` or `[PERM:AUTO shift+tab]`.
- `/permission status`, `/permission ask`, `/permission auto`, `/permission cycle` must work.
- `AUTO` must approve permission requests with `reply: "once"`, not `always`.
- `AUTO` must not remove or bypass OpenCode core command guard / explicit deny behavior.

## Source of truth files

The current implementation is delivered through:

- `.github/workflows/build-patched-opencode-offline.yml`
- `PROJECT_FULL_SOURCE_TO_EDIT/opencode_core_patch/opencode-permission-mode-toggle.patch`

The workflow clones upstream OpenCode at pinned commit:

- upstream repo: `https://github.com/anomalyco/opencode.git`
- pinned commit: `afff74eb2c9fc3808a9795f365707f32853099e9`

## Working rules

### Review-only tasks

If the user asks for review/audit/feedback:

- Do not modify files.
- Do not commit.
- Do not push.
- Do not create a PR.
- Do not rerun workflows unless explicitly asked.
- Inspect the patch and workflow line-by-line.
- Trace runtime behavior, especially permission auto-reply flow.
- Classify findings as `Critical`, `High`, `Medium`, or `Low`.

### Fix tasks

If the user explicitly asks to fix:

- Make minimal, targeted changes.
- Keep the workflow and patch as the source of truth.
- Avoid creating duplicate experimental workflows.
- Prefer updating the existing offline workflow and patch over adding parallel alternatives.
- After changes, run/verify the existing workflow and report run ID, artifact name, and exact verification results.

## Packaging constraints

The offline package is intended for a company Windows PC.

Do not use or introduce:

- Base64 payload embedded in BAT files.
- Self-extracting BAT installers.
- `PowerShell -ExecutionPolicy Bypass` in the installer.
- Company-PC internet downloads.
- Company-PC git clone / npm / bun install requirements.

The installer should remain a simple local-copy installer.

## Known review priorities

When reviewing, focus on these areas first:

1. `PermissionPrompt` auto mode: `createEffect`, `autoReplied`, `replyOnce()`, race conditions, duplicate reply risk.
2. `Shift+Tab` keybind path: `Definitions` → `CommandMap` → command registration → `local.permission.cycle()`.
3. `/permission` slash command path and whether it conflicts with regular command registration.
4. ASK mode preserving existing prompt behavior.
5. AUTO mode not bypassing command guard / explicit deny.
6. Offline installer safety and SHA256/package verification.

## Do not get distracted

Do not stop because there are no open PRs/issues. This repo may be used through direct commits and GitHub Actions.

Do not require a local path like `/home/user/lig_local_ai_opencode`. Use GitHub repository state as the source of truth.
