# FABLE-OCD-WORKSPACE-PROFILES — implement `ocd` folder profiles with shared global memory

## Status

IMPLEMENTED 2026-07-05 (Fable) — cloud-side complete, company-PC validation pending.

Delivered: `agent_ops/project_profile.py` (single source: seed/context/diagnostics),
`agent_ops/ocd.py` (launcher), `bin\ocd.bat`+`ai.bat` via `release/setup_impl.py`
(`install_bin_launchers`, PATH), context injection in `run_agent_loop`
(global memory → PROJECT_MEMORY → PERSONA → RULES + conflict rule), LLM tools
`project_info`/`remember`, doctor `project_profile` section,
`tests/test_ocd_profiles.py` (25 checks green). Patch delivery:
`release/build_patch.py` (`tests/test_patch_build.py`, 21 checks green).

Remaining (company PC): new-CMD `ocd` PATH pickup, real OpenCode launch in a
project folder, folder-persona feel-check.

## Owner target

Fable / implementation agent

## Context

The user wants OpenCodeLIG to support a simple command:

```bat
cd <any project folder>
ocd
```

The command should open OpenCodeLIG in the current folder, create starter local profile files on first run, keep global memory shared, and allow folder-specific persona/project memory/rules.

Read first:

- `docs/COMPANY_PC_TRIALS_AND_NEXT_DIRECTION_20260705.md`
- `workspace-template/docs/MEMORY_AND_SELF_EXTENSION.md`
- `workspace-template/agent_ops/core.py`
- `workspace-template/agent_ops/memory_manager.py`
- `release/setup_impl.py`

## Requirements

### 1. Add `ocd` command

Create an installed command named `ocd` that works from a new CMD window after installation.

Expected use:

```bat
cd C:\Users\...\Desktop\some_project
ocd
```

It should start OpenCodeLIG in the current directory.

### 2. Add `agent_ops/ocd.py`

Create:

```text
workspace-template/agent_ops/ocd.py
```

Responsibilities:

1. Detect the current working directory.
2. Create `.opencodelig` under that directory if missing.
3. Seed files only when missing:
   - `profile.json`
   - `PERSONA.md`
   - `PROJECT_MEMORY.md`
   - `RULES.md`
   - `TASKS.md`
4. Never overwrite customized local profile files unless explicitly requested by a future flag.
5. Launch the existing OpenCodeLIG launcher in the current directory.
6. Set environment variables for the launched process:
   - `AGENTOPS_MEMORY_DIR=%USERPROFILE%\OpenCodeLIG_USERDATA\memory`
   - `AGENTOPS_PROJECT_DIR=<cwd>\.opencodelig`
   - `AGENTOPS_PROJECT_PERSONA=<cwd>\.opencodelig\PERSONA.md`
   - `AGENTOPS_PROJECT_MEMORY=<cwd>\.opencodelig\PROJECT_MEMORY.md`
   - `AGENTOPS_PROJECT_RULES=<cwd>\.opencodelig\RULES.md`

### 3. Add installer support

Modify `release/setup_impl.py` to generate:

```text
%USERPROFILE%\OpenCodeLIG\bin\ocd.bat
```

The batch file must be ASCII-only and CRLF, following the same style as existing generated BAT launchers.

The installer already adds `%USERPROFILE%\OpenCodeLIG\bin` to PATH. Verify `ocd.bat` is in that directory so the user can type `ocd` after opening a new CMD.

### 4. Prompt/context assembly

Modify the runtime context assembly so the agent receives:

1. global memory recall,
2. folder-local `.opencodelig/PROJECT_MEMORY.md`,
3. folder-local `.opencodelig/PERSONA.md`,
4. folder-local `.opencodelig/RULES.md`,
5. current user task.

Conflict rule:

- Global user preferences and safety rules win over local persona.
- Local project rules win over generic defaults.
- If there is a conflict, report it instead of silently ignoring either source.

### 5. Memory must remain durable

Do not delete or reset:

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\memory
```

Do not overwrite existing:

```text
memory.jsonl
WIKI.md
```

If memory storage is migrated, back up first and preserve unknown fields.

### 6. Diagnostics

Add a simple diagnostic path, command, or doctor output that reports:

- current working directory,
- global memory directory,
- local profile directory,
- local persona file,
- whether local files were created or reused.

### 7. Tests

Add tests covering:

1. First `ocd` run creates `.opencodelig` and seed files.
2. Second `ocd` run does not overwrite modified local files.
3. Global memory path remains `%USERPROFILE%\OpenCodeLIG_USERDATA\memory` unless override is set.
4. Local persona/rules/project memory are discoverable by context assembly.
5. Generated `ocd.bat` is ASCII-only and CRLF.

## Acceptance criteria

The task is complete only if:

- `ocd` is installed into `%USERPROFILE%\OpenCodeLIG\bin`.
- A new CMD can run `ocd` from any folder after installation/PATH refresh.
- First run creates `.opencodelig` files.
- Existing `.opencodelig` files are not overwritten.
- Global memory is shared across folders.
- Folder persona/project memory/rules are loaded into the agent context.
- Documentation explains how the user customizes per-folder persona.

## User-facing expected output

First run:

```text
[OpenCodeLIG] Local profile created: .opencodelig
[OpenCodeLIG] Global memory: %USERPROFILE%\OpenCodeLIG_USERDATA\memory
[OpenCodeLIG] Local persona: .opencodelig\PERSONA.md
[OpenCodeLIG] Starting OpenCode in this folder...
```

Later runs:

```text
[OpenCodeLIG] Local profile found: .opencodelig
[OpenCodeLIG] Starting OpenCode in this folder...
```

## Notes

This is a design/implementation task, not just documentation. The user explicitly wants Fable to implement this next.
