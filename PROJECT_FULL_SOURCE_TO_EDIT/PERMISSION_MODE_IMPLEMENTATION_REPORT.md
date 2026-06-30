# Permission Mode Implementation Report

`TRUE_PERMISSION_MODE_TOGGLE_NOT_IMPLEMENTED_BECAUSE_OPENCODE_SOURCE_WAS_NOT_AVAILABLE`

## Outcome

**Outcome B — source patch spec only.** OpenCode source was not present
anywhere on this machine (searched `PROJECT_FULL_SOURCE_TO_EDIT/`, the rest of
the cloned repo, the workspace root, and the global npm module path — no
OpenCode core/TUI source tree found, only this AgentOps package). A true
session-level PLAN/NORMAL/AUTO toggle independent of the active agent cannot
be implemented from the AgentOps layer alone:
- A plugin's `tool.execute.before` hook (the only execution-path extension
  point available here) can **block** a tool call but cannot **relax** an
  `ask`/`deny` decision into `allow` — confirmed by this package's own
  `command-guard.ts`, which only ever throws.
- This package's `.opencode/commands/*.md` files pin their `agent:` statically
  in frontmatter — a command cannot reassign the live session's active primary
  agent, so it cannot act as a real mode switch either.
- There is no keybind/action-registry surface reachable without OpenCode core.

No fake implementation was written. Deliverables:
- `OPENCODE_PERMISSION_MODE_PATCH_SPEC.md` — full source-patch design (state
  model, keybind/action plan, resolver algorithm, tests, limitations).
- `.opencode/commands/permission.md` — fallback command; explains the gap and
  reports the C1 persona mapping, does not pretend to switch state.
- `.opencode/agents/agentops-plan.md` — new read-only primary agent,
  completing the C1 fallback trio (`agentops-plan` / `agentops-supervisor` /
  `agentops-autopilot`); this was previously deferred as review item P2-4.

## Whether true core implementation was possible

No. OpenCode source unavailable (see above).

## Files changed

- `PROJECT_FULL_SOURCE_TO_EDIT/OPENCODE_PERMISSION_MODE_PATCH_SPEC.md` (new)
- `PROJECT_FULL_SOURCE_TO_EDIT/.opencode/commands/permission.md` (new)
- `PROJECT_FULL_SOURCE_TO_EDIT/.opencode/agents/agentops-plan.md` (new)
- `PROJECT_FULL_SOURCE_TO_EDIT/PERMISSION_MODE_IMPLEMENTATION_REPORT.md` (this file, new)
- `PROJECT_FULL_SOURCE_TO_EDIT/REMAINING_RISKS.md` (updated: P2-4 marked
  resolved, Phase 3/C2 entry pointed at the new spec)
- `PROJECT_FULL_SOURCE_TO_EDIT/REQUIRES_OPENCODE_SOURCE_PATCH.md` (updated:
  pointer added to the fuller spec, original kept intact for history)

## Keybind chosen

None — not implemented (no core to register a keybind in). Proposed in the
spec (§6): `shift+tab` if free, else `ctrl+m`/`alt+m`/`ctrl+shift+m` in that
order, to be confirmed against the actual OpenCode keymap during the source
spike.

## Mode state location

None — not implemented. Proposed in the spec (§5):
`session.permissionMode: "plan"|"normal"|"auto"`, default `"normal"`, on the
same per-session store that already tracks the active agent, gated behind
`experimental_permission_mode`.

## Permission resolver changes

None to OpenCode core (no source to patch). The AgentOps-layer permission
*configs* (`agentops-plan.md` / `agentops-supervisor.md` / `agentops-autopilot.md`
frontmatter `permission:` blocks) already implement the per-mode behavior
tables from spec §1 as three separate agent personas — that is the C1
fallback, not a resolver patch.

## Status indicator changes

None to the OpenCode TUI (no source). The existing TUI already shows the
active agent name, which under C1 doubles as the mode indicator (e.g.
`agentops-autopilot` visible = AUTO mode active). No new chip/segment was
added since that requires the status-bar renderer (spec §7), which is core.

## Command guard integration result

No change needed. `.opencode/plugins/command-guard.ts` hooks
`tool.execute.before` globally — it has no per-agent or per-mode awareness and
runs identically regardless of which of the three personas (or any future real
`permissionMode`) is active. Verified by reading the plugin: it inspects only
`input.tool === "bash"` and the literal command string, with zero references
to agent/session/mode. This satisfies the "guard must stay active in all
modes" requirement without any modification.

## Tests run

None of T1–T8 (`OPENCODE_PERMISSION_MODE_PATCH_SPEC.md` §10) — all require a
live OpenCode session and (for T2–T8 in their literal "permission mode" sense)
the unimplemented core patch. Not run, not claimed.

What *was* checked statically on this machine:
- `agentops-plan.md` frontmatter follows the same schema as the existing
  `agentops-supervisor.md`/`agentops-autopilot.md`/`agentops-explorer.md`
  files (15 valid permission keys only, no `write`/`apply_patch`/`patch` key
  — consistent with Opus review fact F4).
- `command-guard.ts` read in full; confirmed mode-agnostic (see above).

## Tests not run

T1, T2, T3, T4, T5, T6, T7, T8 — all pending; require OpenCode source patched
per this spec **and** a live OpenCode session. Once C2 is implemented, run
them following the procedure style already used in `WINDOWS_TEST_PLAN.md`.

## Remaining risks

- **HIGH** — maintaining an OpenCode source fork on an offline (망분리)
  machine, if C2 is ever implemented (rebase cost on every OpenCode upgrade).
  Per the spec, proceed only after a source spike confirms the permission
  resolver is a single chokepoint, and only with explicit user sign-off to
  maintain the fork.
- **Unverified assumption** — `OPENCODE_PERMISSION_MODE_PATCH_SPEC.md` §2.2's
  "single chokepoint" assumption is inherited from the Opus review's reading
  of OpenCode's public docs/behavior, not from reading OpenCode's own source
  (which was unavailable here too). The spike is still required before any
  code is written.
- **C1 fallback gap** — `agentops-plan` is a new persona, not yet exercised
  against a live OpenCode session; verify its `permission:` block resolves as
  intended (read-only, no edits) the same way `WINDOWS_TEST_PLAN.md`/`VALIDATION_TODO_ON_WINDOWS.md`
  already plan to verify `agentops-autopilot`.
