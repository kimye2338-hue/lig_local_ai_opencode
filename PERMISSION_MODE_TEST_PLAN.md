# PERMISSION_MODE_TEST_PLAN

Tests for the Claude-Code-like session permission mode toggle.

## Automated (verifiable now)

### Core logic unit tests — `packages/core/test/permission/mode.test.ts`

Run from `vendor/opencode-source`:

```bash
bun test packages/core/test/permission/mode.test.ts
```

These cover the decision logic for T6–T10 (overlay + command guard). A
standalone smoke run (no workspace install needed) is also provided and was
executed during development:

```
44 passed, 0 failed
```

### Typecheck

```bash
# core (resolver + mode registry)
bun run --cwd packages/core typecheck
# server (httpapi mode endpoints)
bun run --cwd packages/opencode typecheck
# tui (keybind, store, status, commands)
bun run --cwd packages/tui typecheck
```

## Manual (require a running TUI in a real terminal)

Start the patched build:

```bash
cd vendor/opencode-source
bun install
bun run dev            # = bun run --cwd packages/opencode --conditions=browser src/index.ts
```

### T1 — default mode
Start OpenCode. **Expected:** footer shows `[MODE: NORMAL]`; existing behavior
unchanged.

### T2 — keybind cycle
Press `shift+tab` repeatedly (or `<leader>p`). **Expected:**
`NORMAL → AUTO → PLAN → NORMAL`; footer + toast update each press.

### T3 — same agent preserved
Note the active agent. Cycle the permission mode. **Expected:** agent/persona
unchanged; only `[MODE: …]` changes.

### T4 — status visible
**Expected:** `[MODE: …]` always visible in the prompt footer; AUTO/PLAN shown
bold + colored (AUTO=warning, PLAN=info); updates immediately on toggle.

### T5 — slash commands
Run `/permission`, `/permission-plan`, `/permission-normal`, `/permission-auto`,
`/permission-status`. **Expected:** mode changes accordingly; status reports the
current mode.

### T6 — PLAN blocks writes
In PLAN, ask the model to edit a project file. **Expected:** edit prompts for
approval (not silently applied).

### T7 — AUTO allows safe project-local edit
In AUTO, ask the model to modify a harmless project-local file. **Expected:** no
prompt; file modified.

### T8 — AUTO blocks corrupted bash
In AUTO, attempt `cd portal_research && cat > r.py << 'EOF'`. **Expected:**
blocked by the command guard; `r.py` not created. (Covered by unit test +
`.opencode/plugins/command-guard.ts`.)

### T9 — explicit deny still wins
Configure an agent `deny` rule for an action AUTO would otherwise allow.
**Expected:** deny wins; AUTO does not override it. (Resolver returns deny before
the overlay runs — covered by unit test.)

### T10 — dangerous action blocked
Attempt `rm -rf`, `del /s`, credential/token extraction, or
submit/delete/send/upload/download. **Expected:** not silently allowed in any
mode. (Guard + unit tests cover the bash forms; submit/delete/etc. stay `ask` in
AUTO.)

## Status

| Test | Type | Status |
|------|------|--------|
| Overlay/guard logic (T6–T10) | unit | PASS (44/44 standalone) |
| Core typecheck | static | see PERMISSION_MODE_IMPLEMENTATION_REPORT.md |
| Server typecheck | static | see report |
| TUI typecheck | static | see report |
| T1–T5 | manual TUI | requires interactive terminal |
