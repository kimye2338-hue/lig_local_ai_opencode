# AUTOMATION_ROADMAP — browser & local-PC automation direction

Goal: grow OpenCodeLIG from a file/code assistant into a controlled internal PC
assistant ("이 홈페이지에서 ~ 찾아줘", "이 창에서 버튼 눌러줘") **without
destabilizing the working tool-call/file-write core**.

## Phased model

| Phase | Scope | Status |
|---|---|---|
| A | file/code/proxy/diagnostics core | **shipped (this PR)** |
| B | browser automation (read → then act) | designed, not installed |
| C | local UI automation (windows/buttons/typing) | designed, not installed |

Phases B/C are **optional modules**: separate folder, separate installer,
core keeps working if they are absent. The agent already knows they are not
installed (skills `skill_browser_automation.md` / `skill_ui_automation.md`
make it answer honestly instead of faking).

## Phase B — browser (recommended: Edge/Chrome DevTools Protocol)

**Why CDP**: Edge is preinstalled on company Windows PCs; CDP needs no browser
extension and no pip package for the HTTP part; the user *sees* the browser
window the whole time (visible, user-approved workflow).

Design:
- `RUN_BROWSER_ASSIST.bat` starts Edge with `--remote-debugging-port=9222`
  and a **dedicated profile dir** (no access to the user's daily cookies —
  satisfies "no credential/cookie extraction by construction").
- `scripts/lig_browser.py` (stdlib; CDP WebSocket client is ~100 lines):
  subcommands the agent calls via bash — `open <url>`, `text` (visible page
  text), `links`, `find <text>`, and gated `click <selector>` / `type <selector>
  <text>` that require an explicit `--confirm` flag.
- Agent-side rules (already written in the skill): plan → user approval for
  any state-changing action → act → report clicked/typed steps; login is
  always done by the human.
- Read-only tier first (open/text/find). Act tier (click/type) only after the
  read tier proves stable on the company intranet.

## Phase C — local UI (recommended: Windows UIAutomation via pywinauto)

- `pywinauto` (offline wheel, isolated in `tools_optional\`) over pyautogui:
  UIAutomation addresses controls by name/role (reliable, locale-safe) instead
  of screen coordinates and screenshots.
- Same operating contract: user-initiated, one window at a time, plan-first
  for anything destructive, per-step reporting, stop-and-ask on ambiguity,
  operation log to `USERDATA\state\ui_actions.log`.
- Repetitive tasks: demonstrate once → user confirms → repeat remainder.

## Safety principles (both phases)
Local-only; user-initiated; no password/token/cookie reading; no hidden
scraping; confirmation before destructive/submitting actions; dry-run
("계획만 보여줘") supported; concise action logs + checkpoints; stop and ask
when ambiguous.

## What lands in the core NOW (this PR)
- The two placeholder skills (honest "not installed yet" behavior).
- This roadmap in `docs\`.
- Nothing else — no new dependencies, no diagnostic changes for automation.
