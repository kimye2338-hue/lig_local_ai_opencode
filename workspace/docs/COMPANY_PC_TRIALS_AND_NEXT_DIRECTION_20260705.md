# Company PC trials and next implementation direction — 2026-07-05

This document records the latest user-observed trial results, failure patterns, and the next desired architecture for OpenCodeLIG / agent_ops.

The goal is to prevent future agents from rediscovering the same issues and to give Fable/Codex/Claude Code a concrete implementation brief.

## 1. What happened in the latest installed version

The user installed the latest GitHub Actions artifact on the company PC and tested realistic usage.

Observed positive signs:

- The current runtime is no longer purely static. It can inspect code, notice missing connections, and patch local problems.
- The agent found that `browser_cdp.py` had useful browser functions, but the actual tool registry exposed only limited browser tools.
- It successfully diagnosed a `site_maps` path collision where a zero-byte file existed where a directory was expected.
- It successfully ran `spa_map` after removing that collision and produced JSON/Markdown results and screenshots.
- The browser automation direction is therefore viable.

Observed limitations:

- Having a helper function in an adapter does not mean the LLM can call it.
- Tools need to be exposed through the dispatcher registry and the LLM tool schema.
- The running loop may not immediately see tools that were added during that same loop.
- Browser SPA pages can look empty if the adapter reads static HTML instead of rendered DOM text.
- Windows CMD Korean output still appears as mojibake in some places.
- Chrome restore/first-run prompts can block unattended browser work.

## 2. Specific trial/error notes to preserve

### 2.1 `new_tab` existed privately but was not exposed

Observed issue:

- `browser_cdp.execute('new_tab', {})` failed because `new_tab` was not included in the adapter `ACTIONS` list.
- `_new_tab()` existed internally, but the external action dispatcher could not call it.

Lesson:

- Private helper functions are not tools.
- A tool must be implemented, listed in adapter actions, registered in `tool_dispatch.py`, and included in generated LLM tool definitions.

### 2.2 `spa_map` existed but the LLM could not call it

Observed issue:

- `browser_cdp.py` had advanced browser actions such as `spa_map`.
- `tool_dispatch.py` exposed only `browse_tabs` and `read_web_page`.
- Therefore the LLM agent could not directly call `spa_map`, `snapshot`, `find_clickables`, or similar browser tools.

Lesson:

- Always inspect both adapter implementation and `tool_dispatch.py`.
- If an action is useful to the LLM, add a registry entry and tests.

### 2.3 `site_maps` file blocked directory creation

Observed issue:

```text
[WinError 183] 파일이 이미 있으므로 만들 수 없습니다: '...\\agent_ops\\results\\site_maps'
```

Root cause:

- `agent_ops/results/site_maps` existed as a zero-byte file, not a directory.

Lesson:

- Result-directory creation should handle file-vs-directory collisions.
- If a path exists as a file where a directory is expected, either move/delete the file or create a corrected fallback path.

### 2.4 SPA page text extraction was weak

Observed issue:

- Portal pages are JavaScript SPA pages.
- `snapshot`, `extract_text`, and `read_web_page` could return empty or near-empty text.

Required direction:

- Prefer rendered page text through `Runtime.evaluate`:
  - `document.body.innerText`
  - fallback to `document.body.textContent`
- Add fallback through CDP DOM methods:
  - `DOM.getDocument`
  - `DOM.getOuterHTML`
- Convert outer HTML to readable text only as fallback.

### 2.5 Click by coordinate is fragile

Observed issue:

- `find_clickables` may work, but CDP mouse event click can timeout or break CDP sessions.

Required direction:

- Prefer `Runtime.evaluate` and `element.click()` for menu/navigation clicks.
- Support `selector`, `text`, and `index` click modes.

### 2.6 Screenshots are necessary for browser debugging

Observed issue:

- Without screenshots, the agent cannot reliably know what page state it is in.

Required direction:

- Add screenshot capture through `Page.captureScreenshot`.
- Save screenshots in a stable result folder.
- Avoid Korean-generated screenshot filenames because CMD/log output can become mojibake.

### 2.7 Chrome restore prompt can block automation

Observed issue:

- Restarted debug Chrome can show restore-session / first-run prompts.

Required direction:

- Add Chrome launch flags to suppress restore/first-run prompts where possible.

### 2.8 CMD mojibake remains a separate issue

Observed issue:

- Commands such as `dir` printed Korean paths as garbled text.

Example:

```text
C ����̺��� �������� �̸��� �����ϴ�.
```

Likely cause:

- Windows console output encoding mismatch, usually CP949 vs UTF-8 decoding.

Required direction:

- Browser patches can reduce mojibake by avoiding Korean filenames.
- Full fix requires command-runner stdout/stderr decoding improvements.
- Future command execution should capture bytes and decode with a Windows-aware fallback order, likely UTF-8 first, then CP949, with replacement only as last resort.

## 3. Tool self-extension rule

The model can write code for a new tool, but it does not automatically gain that tool inside the same already-started schema.

Required lifecycle:

1. Implement or repair the adapter action.
2. Add it to the adapter public action list.
3. Register it in `tool_dispatch.py`.
4. Ensure `tool_definitions()` exposes it to the LLM.
5. Add tests or diagnostics.
6. Tell the user whether a restart/new loop is required.

Never claim a capability is available merely because helper code exists.

## 4. Memory preservation direction

The current version is showing useful improvement because some user instructions and repeated lessons are being preserved. This must be protected.

User expectation:

- Future patches should not wipe or reset memory.
- The assistant should remember repeated failures, successful fixes, user preferences, environment details, and project decisions.
- Updating runtime code should make the assistant better, not erase accumulated behavior.

Preserve:

- `%USERPROFILE%\\OpenCodeLIG_USERDATA\\memory`
- any explicit `AGENTOPS_MEMORY_DIR`
- `memory.jsonl`
- existing `WIKI.md`
- generated memory views such as `ACTIVE_MEMORY.md`, `LESSONS_LEARNED.md`, and `MEMORY_INDEX.json`

Installer/runtime rule:

- Program files can be replaced.
- User data and memory must be durable.
- If migration is needed, back up first and preserve unknown fields.

## 5. Desired next UX: `ocd` command

The user wants a command similar to this:

```bat
cd C:\some\project\folder
ocd
```

Expected behavior:

1. `ocd` opens OpenCodeLIG in the current folder.
2. If the folder has no local OpenCodeLIG profile yet, create initial local files.
3. Global memory remains shared across all folders.
4. Each folder can have its own persona, local project memory, and specialized rules.
5. The installer automatically registers `ocd` on PATH so a new CMD can run it immediately.

## 6. Proposed folder/profile architecture

### 6.1 Global user state

Location:

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\
```

Purpose:

- Shared memory across every folder.
- User preferences.
- Repeated lessons.
- Credentials/secrets.
- Diagnostics and audit logs.

Suggested structure:

```text
OpenCodeLIG_USERDATA\
  memory\
    memory.jsonl
    WIKI.md
    ACTIVE_MEMORY.md
    LESSONS_LEARNED.md
    MEMORY_INDEX.json
  secrets\
    lig-api.env
  diagnostics\
  audit\
  global_personas\
```

### 6.2 Folder-local project state

Location inside the current working folder:

```text
.project-root\
  .opencodelig\
    profile.json
    PERSONA.md
    PROJECT_MEMORY.md
    RULES.md
    TASKS.md
    diagnostics\
    state\
```

Purpose:

- Folder-specific persona.
- Folder-specific project rules.
- Local context that should not pollute global memory.
- Project task queue/status.

### 6.3 Shared plus local memory model

Prompt assembly should load memory in this order:

1. Global durable user memory.
2. Folder-local `.opencodelig/PROJECT_MEMORY.md`.
3. Folder-local `.opencodelig/PERSONA.md`.
4. Folder-local `.opencodelig/RULES.md`.
5. Current task prompt.

Conflict rule:

- Safety and global user preferences win over local persona.
- Local project rules win over generic defaults.
- The agent should report conflicts instead of silently ignoring one side.

## 7. Proposed `ocd` implementation behavior

### 7.1 Installer

Installer should create:

```text
%USERPROFILE%\OpenCodeLIG\bin\ocd.bat
```

And add `%USERPROFILE%\OpenCodeLIG\bin` to user PATH.

### 7.2 `ocd.bat`

`ocd.bat` should be ASCII-only and minimal. It should delegate to Python to avoid CMD quoting/codepage problems.

Expected batch behavior:

```bat
@echo off
set "LIG_HOME=%USERPROFILE%\OpenCodeLIG"
set "LIG_WORKSPACE=%LIG_HOME%\workspace"
python "%LIG_WORKSPACE%\agent_ops\ocd.py" %*
```

Use the embedded/detected Python path if the install already stores one.

### 7.3 `agent_ops/ocd.py`

Responsibilities:

1. Detect current working directory.
2. Create `.opencodelig` if missing.
3. Seed local files only if missing:
   - `profile.json`
   - `PERSONA.md`
   - `PROJECT_MEMORY.md`
   - `RULES.md`
   - `TASKS.md`
4. Launch `oc.bat` or `opencode.exe` in that same folder.
5. Pass environment variables telling runtime where global and local memory live:
   - `AGENTOPS_MEMORY_DIR=%USERPROFILE%\OpenCodeLIG_USERDATA\memory`
   - `AGENTOPS_PROJECT_DIR=<current>\.opencodelig`
   - `AGENTOPS_PROJECT_PERSONA=<current>\.opencodelig\PERSONA.md`

### 7.4 Initial local files

`profile.json` example:

```json
{
  "version": 1,
  "name": "folder-default",
  "created_by": "ocd",
  "global_memory": true,
  "local_memory": true,
  "persona_file": "PERSONA.md",
  "rules_file": "RULES.md",
  "project_memory_file": "PROJECT_MEMORY.md"
}
```

`PERSONA.md` default:

```markdown
# Folder persona

This folder can define a specialized working style. Keep global user preferences intact.

## Role
- General project assistant until customized.

## Style
- Follow global user memory first.
- Use this folder's rules for project-specific behavior.
```

`PROJECT_MEMORY.md` default:

```markdown
# Project memory

Folder-specific facts, decisions, and lessons go here.

Do not store secrets here.
```

`RULES.md` default:

```markdown
# Project rules

- Preserve global memory.
- Do not overwrite local profile files unless explicitly requested.
- Record project-specific lessons here instead of polluting global memory.
```

## 8. Implementation checklist for Fable

Fable should implement in small patches:

1. Add `workspace-template/agent_ops/ocd.py`.
2. Add `ocd.bat` generation to `release/setup_impl.py`.
3. Ensure installer adds `%USERPROFILE%\OpenCodeLIG\bin` to user PATH.
4. Add local profile seeding under `.opencodelig`.
5. Modify prompt/context assembly to read global memory plus local project files.
6. Add diagnostics command showing:
   - current project dir,
   - global memory dir,
   - local profile dir,
   - active persona file.
7. Add tests for:
   - first-run creates `.opencodelig`,
   - second-run does not overwrite customized files,
   - global memory path remains unchanged,
   - local persona is read when present.
8. Document usage in README and `workspace-template/docs/RUNBOOK.md`.

## 9. User-facing target behavior

After install:

```bat
cd C:\Users\...\Desktop\quant_project
ocd
```

First run:

```text
[OpenCodeLIG] Local profile created: .opencodelig
[OpenCodeLIG] Global memory: %USERPROFILE%\OpenCodeLIG_USERDATA\memory
[OpenCodeLIG] Local persona: .opencodelig\PERSONA.md
[OpenCodeLIG] Starting OpenCode in this folder...
```

Second run:

```text
[OpenCodeLIG] Local profile found: .opencodelig
[OpenCodeLIG] Starting OpenCode in this folder...
```

The user can then customize per folder by editing:

```text
.opencodelig\PERSONA.md
.opencodelig\PROJECT_MEMORY.md
.opencodelig\RULES.md
```

## 10. Success definition

This is successful when:

- The user can type `ocd` from any folder in a new CMD window.
- The program opens in that folder.
- The folder receives initial profile files only once.
- Global memory is shared.
- Folder-specific persona and project memory are loaded.
- Runtime updates do not erase memory.
- The agent can explain which global and local context it loaded.
