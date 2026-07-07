---
description: Explain the permission approval policy (ASK/AUTO/FULL) and how to cycle it
agent: agent
subtask: false
---

Requested action (if any): $ARGUMENTS

The real permission approval policy cycle (Claude-Code-style Shift+Tab: **ASK**
→ **AUTO** → **FULL**, same agent/model, only approval behavior changes) is
implemented in the **patched OpenCode build** — see `docs/설계/OPENCODE_INTEGRATION.md`
for how this package integrates that build. In that build:

```text
Shift+Tab            cycle ASK -> AUTO -> FULL -> ASK
/permission status   show current policy
/permission ask      set ASK  (every request prompts the user)
/permission auto     set AUTO (auto-approve one request at a time, reply "once")
/permission full     set FULL (완전 오토: reply "always" — same permission is
                     remembered for the rest of the session, fewest interruptions)
/permission cycle    advance to the next policy
[PERM:ASK|AUTO|FULL shift+tab]   badge shown next to (not replacing) the agent name
```

**In an unpatched build, this Markdown command cannot change real approval
state.** Command frontmatter pins the agent statically, so this file can only
report and explain — it is not itself a policy switch and it must not change the
active agent or model.

If `$ARGUMENTS` asked to set a policy (`ask`, `auto`, `full`, `cycle`) in an
unpatched build, say plainly: "this command cannot change the live approval
policy — use the patched OpenCode build (see `docs/설계/OPENCODE_INTEGRATION.md`) and
Shift+Tab or /permission there." If `$ARGUMENTS` was `status` or empty, report:

1. The ASK/AUTO/FULL policy meaning above.
2. That `.opencode/plugins/command-guard.ts` blocks corrupted/dangerous bash in
   `tool.execute.before` regardless of the approval policy — this protection is
   independent of ASK/AUTO/FULL and independent of which agent is active.
3. A pointer to `docs/설계/OPENCODE_INTEGRATION.md` for the true toggle.

Approval policy and the command guard are separate layers: the policy decides
whether to prompt or auto-approve an `ask`; the guard hard-blocks dangerous
bash before execution. AUTO/FULL never disable the guard, and neither can
bypass an explicit core `deny` (deny is resolved before a request is surfaced).

Do not claim this command changed the approval policy. Do not run bash to
"simulate" a policy change.
