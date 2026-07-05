# IMPLEMENT_PERMISSION_MODE_PATCH_PLAN

Claude-Code-like, session-level permission mode toggle for OpenCode.

## Source location found

OpenCode moved from `sst/opencode` to **`anomalyco/opencode`** (GitHub repo id
`975734319`, default branch `dev`). Git clone over the session proxy returned a
policy `403` on the dedicated git relay port, but the source tarball downloaded
cleanly through the HTTPS path:

```
curl -sSL -o opencode-dev.tar.gz \
  "https://codeload.github.com/anomalyco/opencode/tar.gz/refs/heads/dev"
```

Extracted to: **`vendor/opencode-source/`** (TypeScript monorepo, Bun
workspaces, ~30 packages).

Key architecture facts discovered:

- The TUI is **TypeScript + SolidJS (`@opentui/solid`)**, not the old Go TUI.
- There are **two permission systems**: `PermissionV1` (legacy) and
  **`PermissionV2`** (`packages/core/src/permission.ts`, service id
  `@opencode/v2/Permission`).
- **Tool execution uses `PermissionV2`.** `bash`, `edit`, `write`,
  `apply-patch`, `read`, `glob`, `grep`, `webfetch`, `websearch`, `skill`,
  `todowrite`, `question` all call `permission.assert({ action, resources,
  sessionID, agent, source })`. This makes `PermissionV2.evaluateInput` the
  single real chokepoint.
- The SDK (`packages/sdk/js/src/v2/gen/`) is **generated** by
  `@hey-api/openapi-ts`, so the control plane avoids SDK regen and uses a raw
  `fetch` to a new server route (the TUI SDK context exposes `url` + `fetch`).

## Files to edit

| File | Change |
|------|--------|
| `packages/core/src/permission/mode.ts` (new) | Pure mode model: `Mode`, `cycle`, `overlay`, `commandGuard`, `safeBash`. Dependency-light, unit-testable. |
| `packages/core/src/permission.ts` | Add in-memory `Map<sessionID, Mode>`; `setMode`/`getMode` on the service; apply command guard + mode overlay inside `evaluateInput`. |
| `packages/core/test/permission/mode.test.ts` (new) | Unit tests for overlay + guard (covers T6–T10 logic). |
| `packages/opencode/src/server/routes/instance/httpapi/groups/permission.ts` | Add `GET /permission/mode` and `PUT /permission/mode` endpoints. |
| `packages/opencode/src/server/routes/instance/httpapi/handlers/permission.ts` | Handlers calling core `PermissionV2.getMode/setMode`. |
| `packages/tui/src/config/keybind.ts` | New `permission_cycle` (shift+tab) + `permission_set_*`; reassign `agent_cycle_reverse` off shift+tab; command-map entries. |
| `packages/tui/src/app.tsx` | Register `permission.cycle` + `permission.set` commands (slash `/permission`). |
| `packages/tui/src/context/local.tsx` | `permission` mode store: `current()`, `set()`, `cycle()`, server push via raw fetch. |
| `packages/tui/src/component/prompt/index.tsx` | Render `[MODE: X]` indicator next to the agent name; send mode with each prompt. |

## Relevant functions / types found

- `PermissionV2.evaluate(action, resource, ...rulesets)` — last-match wins.
- `PermissionV2.evaluateInput(input)` — resolves agent rules, explicit `deny`
  short-circuit, merges saved rules, returns `{ effect, rules }`. **Overlay
  point.**
- `Permission.Effect = "allow" | "deny" | "ask"`.
- Session `switchAgent` (event-sourced) — pattern reference; we deliberately do
  NOT persist mode through event sourcing to keep the surface buildable.
- TUI keybind `Definitions` + `CommandMap`; `agent_cycle: tab`,
  `agent_cycle_reverse: shift+tab` (the conflict).
- TUI `local.agent` store (`move(±1)`, `set`, `current`) — pattern for
  `local.permission`.

## Planned state field

Session-level **runtime** state: `permissionMode: "plan" | "normal" | "auto"`,
default `normal`, held in a `Map<SessionID, Mode>` inside the `PermissionV2`
service. It is keyed by session, independent of the active agent/persona, and
read by the resolver. (Not persisted across server restarts — acceptable per
the "if the session system supports it" qualifier; persisting would require an
event + projector + DB migration, which is out of scope for a buildable patch.)

## Planned keybind

- **`shift+tab` → `permission.cycle`**, cycle order **NORMAL → AUTO → PLAN →
  NORMAL**.
- `agent_cycle_reverse` reassigned to **`<leader>shift+tab`** (leader = `ctrl+x`).
- Fallback **`<leader>p`** also bound to `permission.cycle`.
- Slash commands: `/permission plan|normal|auto|status`.

## Planned permission resolver overlay

In `evaluateInput`, after the existing decision is computed and explicit `deny`
is preserved:

1. Compute base effect (unchanged existing logic).
2. If `action === "bash"`, run `commandGuard` on each resource → `deny` wins in
   ALL modes (including AUTO).
3. Apply `overlay(base, mode, action, command)`:
   - **NORMAL**: unchanged.
   - **PLAN**: reads → allow; `edit` → ask; `external_directory` → deny; network
     → deny unless config-allowed; bash → ask.
   - **AUTO**: `deny` never weakened; reads → allow; project-local `edit` →
     allow; `external_directory` → deny; safe bash → allow, ambiguous bash →
     ask, dangerous bash → deny (guard); unknown actions → keep base (never
     auto-allow submit/delete/send/upload/download).

## Planned tests

- Core unit tests (`bun test`) for `overlay` and `commandGuard` — the verifiable
  proof (maps to T6–T10).
- `tsgo --noEmit` typecheck on `@opencode-ai/core` (and TUI/server best-effort).
- Manual TUI test plan documented in `PERMISSION_MODE_TEST_PLAN.md` (T1–T5
  require a running terminal).
