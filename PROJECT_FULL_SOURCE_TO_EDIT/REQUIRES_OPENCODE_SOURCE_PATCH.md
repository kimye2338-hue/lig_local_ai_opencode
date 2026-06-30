# Requires OpenCode Source Patch — Permission-Mode Toggle (Phase 3)

**Status: DESIGN ONLY. NOT IMPLEMENTED in this pass.**

Per `00_START_HERE_…_OPUS_MANAGER.md` Phase 3 and the Opus review §C, a true
Claude-Code-style permission-mode hotkey (plan | normal | auto) is **not**
implemented here because the OpenCode source repository is **not present** in this
package (`OPTIONAL_REFERENCE_PACKAGES/` ships only AgentOps snapshots, not the
OpenCode binary/source). This document records the design and exactly what an
implementer must find in the OpenCode source before writing any code.

## Why AgentOps-layer source cannot fully implement it

Verified against current OpenCode docs (review §0, fact F8):

- OpenCode cycles **primary agents** with **Tab** (`switch_agent` keybind). There
  is **no built-in session-level permission-mode toggle that is independent of the
  agent**. "Mode" and "agent persona" are the same axis today.
- Permission decisions (`allow` / `ask` / `deny`) are resolved by OpenCode core
  from per-agent + global `permission:` rules. A plugin's `tool.execute.before`
  hook can *block* a tool (throw) but cannot *relax* an `ask`/`deny` into `allow`,
  and cannot register a new keybind/action or paint a TUI status segment.
- Therefore a real "Shift+Tab cycles plan/normal/auto while keeping the persona"
  requires changing OpenCode core: state, keybind/action registry, the permission
  resolver, and the status bar. That is a **source fork**, out of scope for an
  offline AgentOps-only edit.

## What IS shipped instead (Option C1 — already in this package)

Mode-as-persona, zero core patch, offline-safe:

- **plan**  → use a read-only primary agent (e.g. `agentops-explorer` or a future
  `agentops-plan` with `edit: deny`, `bash: ask`).
- **normal** → `agentops-supervisor` (existing).
- **auto**  → `agentops-autopilot` (existing, now guarded by
  `.opencode/plugins/command-guard.ts`).

Cycle with **Tab** (built-in). A future tiny `event`/`session` plugin can write the
current agent name to `agent_ops/state/MODE.txt` and `/status` can surface it.
This is robust and offline-safe, but it is not the exact Claude-Code toggle.

## Option C2 — true toggle (design to verify against OpenCode source first)

`REQUIRES_OPENCODE_SOURCE_PATCH` / `NEEDS_OPUS_LEVEL_DESIGN`. Do **not** code until
the SPIKE below confirms the resolver is a single chokepoint.

### State model
- Add `session.permissionMode ∈ {plan, normal, auto}`, default `normal`,
  persisted per session.

### Keybind / action
- Register a `cycle_permission_mode` action; bind to `shift+tab` **only if** that
  is not already the agent-cycle bind (if it is, use `ctrl+m`). The action advances
  the enum and emits a TUI toast + status-bar segment.

### Permission resolver change (the critical chokepoint)
Consult `permissionMode` **before** the per-agent/global rules:
- `plan`   → force `edit` and write-ish `bash` to `deny`; everything else `ask`.
- `normal` → existing agent/global rules unchanged.
- `auto`   → upgrade `ask`→`allow` for project-local `edit` and safe `bash`, but
  **never** override an explicit `deny`, and **never** relax `external_directory`
  or risky portal rules.

### Backward compatibility
- No mode set / patch absent → behavior identical to today (`normal`).
- Gate the whole feature behind config flag `experimental_permission_mode: true`.

## SPIKE — what to find in the OpenCode source before implementing

Clone the **installed build's** source (version must match `opencode --version`)
and locate:

1. **Keybind/action registry** — search the TUI package for the existing
   agent-cycle action (`switch_agent` / Tab) to learn how actions and keybinds are
   registered.
2. **Permission resolver entry point** — search for where `"ask" | "allow" | "deny"`
   is computed for a tool call. Confirm it is a **single** function (one
   chokepoint). If permission decisions are scattered across call sites, C2 is too
   invasive → **stay on C1**.
3. **Session state shape** — where per-session state is stored/persisted, to add
   `permissionMode`.
4. **Status bar / toast API** — to render the active mode indicator.

### Acceptance (only after the patch)
- Mode cycles with the keybind; indicator shows the current mode.
- `plan` denies edits; `auto` allows project-local edits; an explicit `deny`
  still wins in every mode; `external_directory` never relaxed.
- With the flag off, behavior is byte-for-byte identical to today.

### Risk
HIGH — maintaining a fork on an offline 망분리 PC. Only proceed if C1 is proven
insufficient and the user explicitly accepts fork maintenance.
