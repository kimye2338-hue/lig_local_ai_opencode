# OpenCode Core Patch: Permission Approval Policy Toggle

## What this is

An upstream OpenCode source patch that adds a **permission approval policy**
toggle, modeled on Claude Code's Shift+Tab behavior.

It is **independent** of the active agent/persona, the current workflow, and the
current model. Toggling it only changes how permission requests are handled — it
never changes which agent is active, what task you are doing, or which model runs.

```text
ASK  = show permission requests to the user (default OpenCode behavior)
AUTO = auto-approve the requests that reach the TUI ("permission.asked")

Cycle: ASK -> AUTO -> ASK
```

## Keys

```text
Tab       = next agent            (unchanged)
Shift+F3  = previous agent        (moved here; was Shift+Tab upstream)
Shift+Tab = toggle ASK/AUTO permission approval policy
Ctrl+T    = cycle model variants  (unchanged)
```

Upstream OpenCode bound `shift+tab` to *previous agent*. To keep agent cycling
available, previous-agent moves to `shift+f3`, and `shift+tab` becomes the
approval-policy toggle. Next-agent stays on `tab`.

## `/permission` command

```text
/permission status   show the current approval policy
/permission ask      set policy to ASK
/permission auto     set policy to AUTO
/permission cycle    toggle ASK/AUTO
```

`/permission` changes only the approval policy. It never changes the agent,
persona, workflow, or model.

## TUI indicator

The session prompt shows a badge to the right of the prompt, separate from the
agent name:

```text
[PERM:ASK shift+tab]
[PERM:AUTO shift+tab]
```

## How AUTO stays safe

`AUTO` is **not** `--dangerously-skip-permissions`:

- Explicit `deny` decisions are resolved in opencode **core**
  (`packages/opencode/src/permission/index.ts`) *before* a request is ever
  surfaced as a `permission.asked` event. The TUI only ever sees requests that
  the core resolver already turned into an `ask`. Therefore AUTO can only
  auto-approve `ask` requests and can **never** bypass an explicit `deny`.
- `.opencode/plugins/command-guard.ts` runs in `tool.execute.before` and blocks
  corrupted/dangerous bash regardless of the approval policy. AUTO does not
  disable it. The command guard is a separate defense-in-depth layer.

So the two layers are orthogonal:

```text
approval policy (ASK/AUTO) = whether to prompt the user or auto-approve an "ask"
command guard              = hard block of dangerous/corrupted bash before exec
```

## What the patch changes

The design deliberately reuses OpenCode's existing permission state. Upstream
already stores a mode (`auto` via `--auto`) and already auto-replies `once` to
`permission.asked` when `mode === "auto"`, so the patch does **not** need to
touch `context/sync.tsx` at all.

```text
packages/tui/src/config/keybind.ts          Shift+Tab -> toggle policy; prev-agent -> Shift+F3
packages/tui/src/context/permission.tsx     mode type "ask" | "auto"; default ASK; set()/cycle()
packages/tui/src/app.tsx                     command "permission.mode" -> cycle; /permission slash
packages/tui/src/component/prompt/index.tsx  /permission status|ask|auto|cycle handler
packages/tui/src/routes/session/index.tsx    [PERM:...] badge next to the agent name
```

## Upstream target

```text
repo:   https://github.com/anomalyco/opencode
commit: afff74eb2c9fc3808a9795f365707f32853099e9
```

## Apply / build

```cmd
copy APPLY_AND_BUILD_PATCHED_OPENCODE.bat.txt APPLY_AND_BUILD_PATCHED_OPENCODE.bat
APPLY_AND_BUILD_PATCHED_OPENCODE.bat
```

The script clones upstream OpenCode, checks out the target commit, runs
`git apply`, then `bun install` / `bun run check` / `bun run build`.

## Validation status

The patch was authored against the inspected upstream source locations for the
target commit and its hunks are internally consistent (correct unified-diff
line counts). It has **not** been `git apply`-checked or built in this
environment, which has no network access to clone upstream OpenCode.

Before use, on a machine with Git + Bun + network:

```text
1. git apply --check opencode-permission-mode-toggle.patch   (adjust context if upstream drifted)
2. bun run check / bun run build
3. Runtime tests below.
```

Runtime tests to confirm:

```text
T1  default policy is ASK
T2  Shift+Tab: ASK -> AUTO
T3  Shift+Tab: AUTO -> ASK
T4  active agent/persona unchanged across toggles
T5  model unchanged across toggles
T6  AUTO auto-replies "once" to permission.asked
T7  ASK shows the normal permission prompt
T8  explicit deny is not bypassed by AUTO (resolved in core before "asked")
T9  command-guard.ts still blocks dangerous bash under AUTO
T10 /permission status|ask|auto|cycle changes only the approval policy
```

Workflow verification trigger: keep this branch moving so the GitHub Actions build can produce the offline package artifact.
