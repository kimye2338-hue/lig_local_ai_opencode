# Repository map

## Active files

```text
.
├── .github/
│   └── workflows/
│       └── build-offline-package.yml
├── patches/
│   └── opencode-permission-mode-toggle.patch
├── workspace-template/
│   ├── .opencode/
│   │   ├── agents/
│   │   ├── commands/
│   │   └── plugins/
│   ├── agent_ops/
│   │   ├── config/
│   │   └── policies/
│   ├── RUN_AGENTOPS_*.bat.txt
│   └── README.md
├── docs/
│   ├── AI_HANDOFF.md
│   ├── ARCHIVE_SUMMARY.md
│   ├── CHANGELOG.md
│   ├── CURRENT_RELEASE.md
│   ├── INSTALL.md
│   ├── REPOSITORY_MAP.md
│   └── VALIDATION.md
├── AGENTS.md
└── README.md
```

## Purpose by folder

### `.github/workflows/`

One workflow builds and verifies the offline package. It owns the final generated installer and artifact.

### `patches/`

Patch files applied to upstream OpenCode. Keep only the active patch unless the user explicitly asks for variant patches.

### `workspace-template/`

Files copied into `%USERPROFILE%\OpenCodeLIG\workspace` by the generated installer.

This folder contains the runtime `.opencode` commands/agents/plugins and the `agent_ops` Python runtime.

### `docs/`

Human and AI-readable context. This is where Codex and Claude Code should preserve decisions, validation results, unresolved issues, and handoff notes.

## Do not recreate

Do not recreate these old folders unless the user explicitly asks for historical material:

- `PROJECT_FULL_SOURCE_TO_EDIT/`
- `REVIEW_AND_WORK_INSTRUCTIONS/`
- `OPTIONAL_PATCH_AND_INSTALLER_REFERENCES/`
- separate root-level manifests for old packages

Use `docs/ARCHIVE_SUMMARY.md` for historical context instead.
