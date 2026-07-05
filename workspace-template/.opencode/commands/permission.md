---
description: Explain the permission approval policy (ASK/AUTO) and how to toggle it
agent: agent
subtask: false
---

Requested action (if any): $ARGUMENTS

The real permission approval policy toggle (Claude-Code-style Shift+Tab: **ASK**
vs **AUTO**, same agent/model, only approval behavior changes) is implemented in
the **patched OpenCode build** — see `opencode_core_patch/README.md` and
`PERMISSION_MODE_IMPLEMENTATION_REPORT.md`. In that build:

```text
Shift+Tab            toggle ASK <-> AUTO
/permission status   show current policy
/permission ask      set ASK
/permission auto     set AUTO
/permission cycle    toggle ASK <-> AUTO
[PERM:ASK|AUTO shift+tab]   badge shown next to (not replacing) the agent name
```

**In an unpatched build, this Markdown command cannot change real approval
state.** Command frontmatter pins the agent statically, so this file can only
report and explain — it is not itself a policy switch and it must not change the
active agent or model.

If `$ARGUMENTS` asked to set a policy (`ask`, `auto`, `cycle`) in an unpatched
build, say plainly: "this command cannot change the live approval policy — build
the patched OpenCode (`opencode_core_patch/`) and use Shift+Tab or /permission
there." If `$ARGUMENTS` was `status` or empty, report:

1. The ASK/AUTO policy meaning above.
2. That `.opencode/plugins/command-guard.ts` blocks corrupted/dangerous bash in
   `tool.execute.before` regardless of the approval policy — this protection is
   independent of ASK/AUTO and independent of which agent is active.
3. A pointer to `opencode_core_patch/README.md` for the true toggle.

Approval policy (ASK/AUTO) and the command guard are separate layers: the policy
decides whether to prompt or auto-approve an `ask`; the guard hard-blocks
dangerous bash before execution. AUTO never disables the guard, and AUTO never
bypasses an explicit core `deny`.

Do not claim this command changed the approval policy. Do not run bash to
"simulate" a policy change.
