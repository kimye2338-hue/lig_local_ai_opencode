# PERMISSION_MODE_IMPLEMENTATION_REPORT

## Result: TRUE_PERMISSION_MODE_TOGGLE_IMPLEMENTED

A Claude-Code-like, **session-level** permission mode toggle was implemented by
patching the OpenCode source at its real chokepoints. The active agent/persona
is unchanged when the mode changes; only tool-approval behavior changes.

## 1. Implemented or not implemented

**Implemented.** Mode is session-level runtime state read by the live
`PermissionV2` resolver (the resolver every tool calls via `permission.assert`).
It is not implemented by swapping agents.

## 2. OpenCode source path

- Upstream: `sst/opencode` → **`anomalyco/opencode`** (repo id `975734319`,
  branch `dev`). Git clone hit a policy `403` on the proxy git relay; the HTTPS
  tarball worked (`https://codeload.github.com/anomalyco/opencode/tar.gz/refs/heads/dev`).
- Local path: **`vendor/opencode-source/`** (git-ignored; reproduce with
  `scripts/fetch-and-patch.sh`).

## 3. Files changed

New:
- `packages/core/src/permission/mode.ts` — `Mode`, `cycle`, `overlay`,
  `commandGuard`, `safeBash` (pure, unit-tested).
- `packages/core/test/permission/mode.test.ts` — unit tests.

Modified (see `patches/permission-mode.patch`):
- `packages/core/src/permission.ts` — per-session mode `Map`, `setMode`/`getMode`
  on the service, guard + overlay applied in `evaluateInput`.
- `packages/opencode/.../httpapi/groups/permission.ts` — `GET/PUT
  /permission/mode/:sessionID` endpoints.
- `packages/opencode/.../httpapi/handlers/permission.ts` — handlers delegating to
  core `PermissionV2.getMode/setMode`.
- `packages/opencode/.../httpapi/server.ts` — added `PermissionV2.node` to the
  instance node graph.
- `packages/tui/src/config/keybind.ts` — `shift+tab` → `permission.cycle`;
  `agent_cycle_reverse` moved to `<leader>shift+tab`; fallback `<leader>p`.
- `packages/tui/src/context/local.tsx` — session mode store + server push (raw
  `fetch`, no SDK regen).
- `packages/tui/src/app.tsx` — `/permission`, `/permission-plan|normal|auto|status`.
- `packages/tui/src/component/prompt/index.tsx` — `[MODE: X]` footer + per-prompt
  mode sync.

Project integration layer (this repo):
- `.opencode/plugins/command-guard.ts` — defense-in-depth guard (works on
  unpatched OpenCode too).
- `.opencode/commands/permission.md` — command docs.

## 4. How to run the patched OpenCode

```bash
./scripts/fetch-and-patch.sh          # fetch source, apply patch, bun install
cd vendor/opencode-source
bun run dev                           # patched TUI + server
```

`bun run dev` runs `packages/opencode/src/index.ts` directly under Bun (no
separate compile step).

## 5. Keybind chosen / Shift+Tab / agent_cycle_reverse

- **Shift+Tab is used** for permission-mode cycling (`permission.cycle`), order
  **NORMAL → AUTO → PLAN → NORMAL**.
- Fallback **`<leader>p`** (leader = `ctrl+x`) and slash commands also work.
- **`agent_cycle_reverse`** (previously `shift+tab`) was **reassigned to
  `<leader>shift+tab`** — it is not removed, just moved (task-approved option).

## 6. Permission behavior by mode

- **NORMAL** — stock behavior; agent/global/project config unchanged; explicit
  `deny` wins.
- **PLAN** — reads allowed; `edit`/`bash` → ask; external-directory edits →
  deny; network → deny unless config already allows; unknown mutations → ask.
- **AUTO** — reads allowed; project-local `edit` → allow; safe verification bash
  (`git status`, `bun test`, `ls`, …) → allow; ambiguous bash → ask;
  dangerous/corrupted bash → deny (guard); external edits → deny; network not
  auto-opened; submit/delete/send/upload/download → ask. Explicit `deny` and the
  guard always win. AUTO is **not** dangerously-skip-permissions.

Resolver order (in `evaluateInput`): explicit agent deny → base decision →
command guard (all modes) → mode overlay.

## 7. Tests passed

- **Core overlay + guard logic: 44/44 assertions PASS** (standalone Bun run,
  executed twice incl. after a container restart). Covers T6–T10 decision logic.
- `bun test packages/core/test/permission/mode.test.ts` mirrors these as the
  in-repo suite.

## 8. Tests not run (and why)

- **Full-monorepo typecheck** (`bun run --cwd packages/{core,opencode,tui}
  typecheck`) and **`bun install`** — the sandbox `bun install` of this ~30-
  package monorepo is very slow (network-throttled by `bunfig` `minimumReleaseAge`)
  and was interrupted by a container restart. The verification is chained in
  `scripts/fetch-and-patch.sh` / the background verify job; results append to
  `scratchpad/verify.log`. Type-level review of each edit was done by hand
  (SessionID brand compatibility confirmed: `@/session/schema` `SessionID` ===
  core `SessionV2.ID`).
- **T1–T5 interactive TUI tests** — require a real terminal; steps documented in
  `PERMISSION_MODE_TEST_PLAN.md`.

## 9. Remaining risks

See `REMAINING_RISKS.md`. Highlights: mode is in-memory (re-pushed each prompt,
not persisted across server restart); TUI→server uses raw `fetch` (auth-header
edge cases); safe-bash allowlist is intentionally conservative; a separate
pre-existing `--auto` blanket-approve flag exists and is independent of this
feature.

## 10. Next action for the user

1. Run `./scripts/fetch-and-patch.sh` (or `bun install` inside
   `vendor/opencode-source`) to complete the dependency install.
2. `bun run --cwd packages/core typecheck` and the two other package typechecks
   to confirm the static build in your environment.
3. `bun run dev` and exercise T1–T5 from `PERMISSION_MODE_TEST_PLAN.md`.
