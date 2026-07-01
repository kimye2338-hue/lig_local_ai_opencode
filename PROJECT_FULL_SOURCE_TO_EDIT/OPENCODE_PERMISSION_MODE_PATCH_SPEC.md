# OpenCode Permission-Mode Patch Spec (SUPERSEDED — historical)

> **SUPERSEDED.** This document described an early, wrong-direction design that
> framed permissions as a **PLAN/NORMAL/AUTO workflow mode** and mapped modes to
> agentops personas. That is **not** the delivered feature.
>
> The delivered feature is an independent **permission approval policy** toggle
> (**ASK / AUTO**) that does not change the agent/persona, workflow, or model.
> See the authoritative docs instead:
>
> - `opencode_core_patch/README.md`
> - `opencode_core_patch/opencode-permission-mode-toggle.patch`
> - `PERMISSION_MODE_IMPLEMENTATION_REPORT.md`
>
> Correct model: `ASK -> AUTO -> ASK`, toggled with `Shift+Tab`; AUTO auto-approves
> only `permission.asked` requests and never bypasses an explicit core `deny`; the
> command guard stays active in every policy. There is no PLAN mode and personas
> are not a permission mechanism. The text below is kept only for history.

---

**Original status (obsolete): `TRUE_PERMISSION_MODE_TOGGLE_NOT_IMPLEMENTED_BECAUSE_OPENCODE_SOURCE_WAS_NOT_AVAILABLE`.**

This package ships AgentOps snapshots only; no OpenCode core/TUI source tree was
found in `PROJECT_FULL_SOURCE_TO_EDIT/`, in the surrounding workspace, or
anywhere else searched on this machine. Per the implementation prompt's own
instruction ("If OpenCode source code is not available, do not fake
implementation. Create a precise source-patch design document instead."), this
document is the design — Outcome B. It supersedes the shorter design note in
`REQUIRES_OPENCODE_SOURCE_PATCH.md` (kept for history; this file is the
authoritative, fuller version) and is the thing an implementer with the
OpenCode source checked out should work from.

The companion fallback (no-core-patch) layer is `.opencode/commands/permission.md`
and the three primary agents `agentops-plan` / `agentops-supervisor` /
`agentops-autopilot`.

---

## 1. Exact desired behavior

A session-level `permissionMode` independent of which primary agent persona is
active, cycled with a hotkey, visible in the TUI, with three modes:

**A note on terminology first:** the Opus review of this codebase
(`REVIEW_AND_WORK_INSTRUCTIONS/01_OPUS_FEEDBACK_FULL.md`, fact F4) confirmed
OpenCode's permission system has exactly 15 keys: `read, edit, glob, grep,
list, bash, task, external_directory, todowrite, question, webfetch,
websearch, lsp, doom_loop, skill`. **There is no `write` or `apply_patch`
key** — every file-writing tool (`write`, `apply_patch`, the would-be `patch`
tool) gates under `edit`. The behavior tables below use `edit` for all
file-write actions; "write/apply_patch" in the original ask maps to `edit`.

| Permission key | PLAN | NORMAL | AUTO |
|---|---|---|---|
| `read` / `list` / `glob` / `grep` / `lsp` | allow | unchanged (existing rules) | allow |
| `todowrite` | allow | unchanged | allow |
| `edit` (covers write/apply_patch) | deny or ask | unchanged | allow for project-local paths |
| `bash` | ask, except a short read-only allow-list (`git status/diff/log`, `grep`, `findstr`, `dir`, `type`) | unchanged | allow for the safe AgentOps/verification commands below; ask for anything ambiguous; deny for known-dangerous/corrupted patterns |
| `task` | ask | unchanged | ask (not auto-approved) |
| `external_directory` | deny | unchanged | deny — never relaxed |
| `webfetch` / `websearch` | deny | unchanged (or whatever config already allows) | deny unless explicitly allowed by config |
| `question` | unchanged | unchanged | unchanged |
| `doom_loop` | deny | unchanged | deny |

AUTO's safe-command upgrade list (`ask` → `allow`), mirrors the existing
`agentops-autopilot.md` permission block:
- project-local `edit` (write/apply_patch) inside the repo root
- `git status*`, `git diff*`, `git log*`
- `grep *`, `findstr *`, `dir*`, `type *`
- `python -m py_compile *` / `py -3.11 -m py_compile *`
- `python agent_ops/agentops.py *` / `py -3.11 agent_ops/agentops.py *`
- `python agent_ops/command_guard.py *`
- `python agent_ops/safe_file_writer.py *`

AUTO must **never** auto-approve: `approve`, `submit`, `delete`, `send`,
`upload`, `download`-shaped actions, OTP/password/cookie/token extraction, or
anything matching `external_directory` — these require explicit current-session
user approval or stay denied, in every mode. AUTO is explicitly **not**
`--dangerously-skip-permissions`.

PLAN downgrades write-like actions to `ask`/`deny`; read-only actions stay
allowed. NORMAL is the literal pass-through of whatever
project/global/agent `permission:` config already resolves to — byte-for-byte
identical to today.

---

## 2. Required OpenCode source areas to locate

Before writing any core patch, find and read:
1. The keybind/action registry (where `Tab` → `switch_agent`/agent-cycle is
   wired today).
2. The single function that resolves a tool call's final
   `"allow" | "ask" | "deny"` decision (the permission resolver).
3. The session state type/store (where per-session fields such as the active
   agent live today) — this is where `permissionMode` would be added.
4. The TUI status bar renderer (wherever the current agent name / mode chip is
   painted) and the toast/notification API (for a mode-change confirmation).
5. The slash-command parser/registry, to learn whether a command can mutate
   session state or only run a prompt under a fixed agent (see §7 — in this
   package's command files, `agent:` is fixed per command in frontmatter, so
   today's commands cannot dynamically reassign the live primary agent).
6. The plugin host's `tool.execute.before` contract — confirm (it already is,
   per this package's working `command-guard.ts`) that a plugin can **block**
   (throw) a tool call but cannot **relax** an `ask`/`deny` into `allow`, and
   cannot register keybinds or paint TUI chrome. This is why C2 needs a core
   patch and a plugin alone cannot deliver it.

## 3. Search terms to find the permission resolver

Grep the OpenCode source tree for: `"ask"`, `"deny"`, `"allow"` together as
string literals; `PermissionResult`, `resolvePermission`, `permission.ts`,
`computePermission`, `evaluatePermission`, `checkPermission`,
`tool.execute.before`, `tool.execute.after`, `doom_loop`, `external_directory`
(a key unlikely to appear anywhere except the resolver and its config schema,
making it a good anchor), and the per-agent `permission:` frontmatter parser
(search for `"read"` + `"edit"` + `"bash"` co-occurring as object keys, which
should be the schema/validator).

## 4. Search terms to find keybind/action registration

`switch_agent`, `agent_cycle`, `cycle_agent`, `keybind`, `Shift+Tab` /
`shift+tab`, `registerAction`, `registerKeybind`, `KeymapEntry`, `Tab` (as a
literal key name near agent-list code), and the TUI's status-bar/segment
renderer (search for wherever the active agent's `description` from agent
frontmatter is rendered, since that is the existing "mode" indicator to
extend).

## 5. Proposed state model

```
session.permissionMode: "plan" | "normal" | "auto"   // default "normal"
```

- Lives on the same per-session state object that already tracks the active
  primary agent (found in §2.3).
- Persisted per session; restored when the session reopens, if the host
  already persists other session fields (mirror whatever mechanism already
  persists the active agent).
- Entirely independent of `session.agent` — switching agent must never reset
  `permissionMode`, and cycling `permissionMode` must never reset
  `session.agent`.
- Gated behind a config flag `experimental_permission_mode: true`. When unset
  or `false`, `permissionMode` is forced to `"normal"` and the resolver path
  added in §8 is a no-op — behavior is byte-for-byte identical to today.

## 6. Proposed keybind/action implementation

- Register a new action `cycle_permission_mode`.
- Binding: `shift+tab` **if and only if** the spike (§2.1) confirms that key
  is not already the agent-cycle bind. If it is already taken (the Opus
  review's fact F8 says OpenCode cycles primary agents on **Tab**, which
  suggests `Shift+Tab` may be free, but this must be confirmed against the
  actual keymap, not assumed), fall back to `ctrl+m` (then `alt+m`, then
  `ctrl+shift+m`, in that preference order — first one not already bound).
  Document whichever bind is actually free at implementation time; do not
  silently steal an existing bind without also updating the keybind docs and
  this file.
- The action advances the enum `plan → normal → auto → plan` and:
  - emits a TUI toast (`Mode: PLAN` / `Mode: NORMAL` / `Mode: AUTO`),
  - updates the status-bar segment (§7),
  - is a no-op on the active agent — `session.agent` is untouched.

## 7. Proposed TUI status indicator

A status-bar segment next to (not replacing) the existing agent-name
indicator, e.g. `agentops-autopilot · [AUTO]`. Compact form `[PLAN]` /
`[NORMAL]` / `[AUTO]` is acceptable if space-constrained. If the TUI framework
supports per-segment styling, give `AUTO` a visually distinct style (e.g. a
warning/accent color) since it is the highest-autonomy mode — mirror however
the codebase already distinguishes "destructive" vs. "safe" UI elements
elsewhere, rather than inventing a new color convention.

## 8. Proposed permission resolver algorithm

Insert this as a single overlay step in the existing resolver, evaluated
**after** today's full resolution (project/global/agent config + explicit
denies) and **before** returning the final decision:

```
decision = existing_resolver(tool, args, agent_config)   // unchanged, today's logic

if not config.experimental_permission_mode:
    return decision                                       // flag off: identical to today

mode = session.permissionMode  // default "normal"

if mode == "normal":
    return decision                                       // pass-through, unchanged

if decision == "deny":
    return "deny"                                          # explicit deny always wins — no mode may override it

if mode == "plan":
    if tool in {"edit"} or (tool == "bash" and is_write_ish(args.command)):
        return "deny" if decision == "deny" else "ask"     # never auto-execute writes in plan
    return decision                                        # read-only tools pass through

if mode == "auto":
    if decision != "ask":
        return decision                                    # only auto upgrades "ask"; never touches "allow"/"deny"
    if tool == "external_directory":
        return "ask"                                       # never relaxed, even under "ask"->"allow" logic
    if tool == "edit" and is_project_local(args.path):
        return "allow"
    if tool == "bash" and is_safe_autopilot_command(args.command):  # §1's AUTO allow-list
        return "allow"
    if tool == "bash" and is_known_dangerous(args.command):
        return "deny"                                       # corrupted/destructive: never silently ask-through
    return "ask"                                            # everything else stays "ask"

return decision
```

Notes:
- `is_write_ish`, `is_project_local`, `is_safe_autopilot_command`, and
  `is_known_dangerous` should reuse the **existing** pattern lists already
  proven in this package — `agent_ops/command_guard.py`'s detector and
  `.opencode/plugins/command-guard.ts`'s `WRITE_CODE`/`DANGEROUS` regex sets —
  rather than re-deriving a second classifier that can drift out of sync.
- The command guard plugin (`tool.execute.before`) keeps running **in
  addition to** this resolver change, in every mode, for every primary agent.
  It already has zero awareness of `permissionMode` and needs none — it blocks
  by regex on the literal command string regardless of who/what approved the
  call. This is the defense-in-depth layer the Opus review's fact F3 says the
  permission globs alone cannot provide (compound/whitespace-variant commands
  evade start-anchored globs; the regex-based guard does not).
- `approve|submit|delete|send|upload|download`-shaped actions and
  OTP/password/cookie/token extraction are out of scope for this overlay
  entirely — they must remain governed by existing `question`/explicit-approval
  paths in every mode; the resolver overlay must not introduce any path that
  auto-allows them.

## 9. Backward compatibility rules

- No source patch applied → behavior identical to today (this spec is inert
  until implemented).
- `experimental_permission_mode` unset or `false` → resolver overlay is a
  no-op; `permissionMode` stays `"normal"` always.
- No session `permissionMode` set (e.g. an old persisted session) → treated as
  `"normal"`.
- Switching `permissionMode` never mutates `session.agent`, agent frontmatter,
  or project/global `permission:` config files.

## 10. Tests to verify

- **T1 — default mode.** Start OpenCode. Expected: `permissionMode = NORMAL`;
  existing behavior unchanged.
- **T2 — keybind cycle.** Press the mode key three times. Expected order
  `NORMAL → AUTO → PLAN → NORMAL` (cycle is `plan → normal → auto → plan`, so
  starting from the default `NORMAL` the third press returns to `NORMAL`).
  Record the *actual* observed order once implemented; if it differs from this
  spec, that is a bug, not a doc update.
- **T3 — agent remains unchanged.** Cycle `permissionMode`. Expected:
  `session.agent` does not change; only the mode indicator changes.
- **T4 — AUTO allows safe edit.** In AUTO, ask the model to modify a
  project-local test file. Expected: no approval prompt; file is modified.
- **T5 — AUTO blocks corrupted bash.** In AUTO, attempt
  `cd portal_research && cat > r.py << 'EOF'`. Expected: `AgentOps command
  guard BLOCKED this command`; `r.py` is not created.
- **T6 — AUTO keeps external/risky blocked.** Attempt an external-directory
  edit or a risky portal action. Expected: denied or explicit ask; never
  silently allowed.
- **T7 — PLAN blocks writes.** In PLAN, ask the model to edit a file.
  Expected: edit requires approval or is denied.
- **T8 — NORMAL unchanged.** In NORMAL, existing OpenCode permission behavior
  is unchanged from a build without this patch.

None of T1–T8 can run without the OpenCode source patched and a live OpenCode
session — see `PERMISSION_MODE_IMPLEMENTATION_REPORT.md` for their current
status (all pending) and `WINDOWS_TEST_PLAN.md` for the home-PC procedure
template they should follow once C2 is implemented.

## 11. Known limitations

- **Unverified chokepoint.** Without the source, it is **not confirmed**
  that permission decisions are computed in one place. If the spike (§2.2)
  finds them scattered across call sites, C2 is too invasive — stay on the
  C1 fallback (§12) instead of forcing a patch.
- **Plugins cannot relax permissions.** Confirmed by this package's own
  `command-guard.ts`: its hook can only throw (block), never upgrade a
  decision. Any "AUTO allows X" behavior must come from the core resolver
  patch in §8, not from a plugin.
- **Commands cannot mutate live session state today.** Every `.opencode/commands/*.md`
  file in this package pins `agent:` statically in frontmatter (e.g.
  `agentops-autopilot.md`'s `/autopilot` command always runs as
  `agentops-autopilot`). A command cannot reassign the user's actual active
  primary agent, and — absent the §5 state field — cannot set a real
  `permissionMode` either. `.opencode/commands/permission.md` is therefore
  informational only until C2 lands; see that file for what it does instead.
- **Risk rating: HIGH.** Maintaining an OpenCode source fork on an offline
  (망분리) machine carries real maintenance cost (rebasing onto every OpenCode
  upgrade). Per `REQUIRES_OPENCODE_SOURCE_PATCH.md`, proceed only after the
  spike confirms a single chokepoint **and** the user explicitly accepts fork
  maintenance.

## 12. Fallback using agentops-plan / agentops-supervisor / agentops-autopilot

Shipped now, zero core patch, offline-safe (Option C1):

| Mode | Primary agent | How to enter |
|---|---|---|
| `plan` | `agentops-plan` (new, read-only: `edit: deny`, `bash` mostly `ask`, `external_directory`/`webfetch`/`websearch`: `deny`) | Tab-cycle to it, or select it in the agent picker |
| `normal` | `agentops-supervisor` (existing) | Tab-cycle / default |
| `auto` | `agentops-autopilot` (existing, guarded by `command-guard.ts`) | Tab-cycle, or `/autopilot <task>` / `/work <goal>` for one-off scoped work |

This is **mode-as-persona**, not a session-level toggle: switching "mode"
means switching the primary agent, so it does not satisfy "the same agent
should remain active while only permission behavior changes." It is offered
because it is robust and shippable today without an OpenCode fork. The command
guard plugin protects all three personas equally since it has no per-agent
awareness. `.opencode/commands/permission.md` documents this mapping for the
user and explains the gap to a true toggle.
