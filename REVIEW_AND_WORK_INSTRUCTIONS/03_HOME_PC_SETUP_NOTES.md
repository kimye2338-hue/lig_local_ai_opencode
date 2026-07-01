# Home PC setup notes

This package assumes the home PC may have nothing from the prior project.

## What is included

- Full editable AgentOps source snapshot:
  `PROJECT_FULL_SOURCE_TO_EDIT/`

- Full Opus feedback:
  `REVIEW_AND_WORK_INSTRUCTIONS/01_OPUS_FEEDBACK_FULL.md`

- Low-token Claude Code manager prompt:
  `REVIEW_AND_WORK_INSTRUCTIONS/00_START_HERE_CLAUDE_CODE_LOW_TOKEN_OPUS_MANAGER.md`

- Prior review context and optional reference packages.

## What is NOT included

This package does not include:

- Claude Code executable/account.
- OpenCode executable/binary.
- Python installer.
- Node/Bun/OpenCode source repository.
- Company internal LLM server access.

If Claude Code is installed on the home PC, open the parent folder and point it at this package.

## Recommended first action in Claude Code

Paste:

```text
Read REVIEW_AND_WORK_INSTRUCTIONS/00_START_HERE_CLAUDE_CODE_LOW_TOKEN_OPUS_MANAGER.md and follow it exactly.
```

## If OpenCode is not installed on the home PC

That is okay for code editing. Claude Code can still modify the AgentOps files. Live OpenCode plugin verification must be written into `VALIDATION_TODO_ON_WINDOWS.md`.

## If Python 3.11 is not installed

Claude Code can still edit files, but py_compile validation must be deferred. It should write the skipped commands and expected output into `VALIDATION_TODO_ON_WINDOWS.md`.
