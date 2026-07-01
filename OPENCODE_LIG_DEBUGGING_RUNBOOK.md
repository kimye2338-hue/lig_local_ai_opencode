# OpenCodeLIG Debugging Runbook

This runbook defines the diagnostic files and checks that should exist on the company PC after applying the all-in-one hardening patch.

## Goals

- Keep user memory outside patch/reinstall scope.
- Keep chat output concise and user-facing.
- Prevent tool-call schema leakage from being shown as final answer.
- Detect common OpenCode/model/proxy compatibility failures quickly.
- Provide a single diagnostic report file instead of flooding the chat.

## Persistent folders

Expected root:

```text
%USERPROFILE%\OpenCodeLIG_USERDATA
```

Expected subfolders:

```text
memory
settings
logs
diagnostics
backups
opencode_data
opencode_state
opencode_config
opencode_cache
```

## Required persistent memory files

```text
memory\USER_MEMORY.md
memory\PROJECT_MEMORY.md
memory\COMPANY_ENV.md
memory\TOOLING_NOTES.md
memory\OPEN_CODE_LIG_POLICY.md
```

## Required workspace bridge files

```text
%USERPROFILE%\OpenCodeLIG\workspace\AGENTS.md
%USERPROFILE%\OpenCodeLIG\workspace\.opencode\AGENTS.md
%USERPROFILE%\OpenCodeLIG\workspace\OPEN_CODE_LIG_POLICY.md
%USERPROFILE%\OpenCodeLIG\workspace\OPEN_CODE_TOOLCALL_NOTES.md
```

## Required helper commands

```text
.opencode\commands\quiet.md
.opencode\commands\toolpolicy.md
.opencode\commands\memory.md
.opencode\commands\diagnose.md
```

## Required helper scripts

```text
RUN_OPENCODE_LIG.bat
VERIFY_OFFLINE_INSTALL.bat
DIAG_OPENCODE_LIG.bat
CAPTURE_OPENCODE_LIG_SESSION.bat
REPAIR_OPENCODE_LIG_SAFE_STATE.bat
```

## Failure signatures to scan

```text
tool=:
JSON parsing failed
Unknown component type spinner
question JSON
header/options/multiple/custom
webfetch blocked
websearch unavailable
ChromeDriver missing
```

## Diagnostic report policy

Diagnostics should be written to:

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics
```

The user-facing chat should only receive the path to the report and a short summary.

## Remaining true code-level work

The hardening patch is operational. A fully robust implementation still requires proxy/core-level code:

- valid tool-name whitelist
- per-tool JSON schema validator
- malformed tool-call repair/retry
- final answer sanitizer
- question schema leakage sanitizer
- raw shell-output compressor
