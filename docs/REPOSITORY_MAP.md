# Repository map

Two tracks live in this repository:

- **Track A — agent_ops runtime**: an offline office-automation runtime (`workspace-template/agent_ops/`) delivered to the company PC via an offline bundle (`release/` bring-in tooling, one-click `설치.bat`). Work on this track is managed on the board in `plan/`.
- **Track B — patched OpenCode TUI**: a patched build of OpenCode with a permission-mode toggle, produced by `.github/workflows/build-offline-package.yml` from `patches/opencode-permission-mode-toggle.patch`.

`workspace-template/` is shared by both tracks: the same tree (`agent_ops/` + `.opencode/`) is installed to `%USERPROFILE%\OpenCodeLIG\workspace\` whether it arrives via the Track A bundle installer or the Track B offline package installer.

## Active files

```text
.
├── .github/
│   └── workflows/
│       └── build-offline-package.yml      # builds the patched OpenCode TUI offline package (Track B)
├── patches/
│   └── opencode-permission-mode-toggle.patch
├── workspace-template/                    # installed to %USERPROFILE%\OpenCodeLIG\workspace\ (both tracks)
│   ├── .opencode/
│   │   ├── agents/                          # agentops-* subagents (supervisor, doctor, safety, verifier, ...)
│   │   ├── commands/                        # /work /doctor /permission /agentmode ...
│   │   └── plugins/                         # command-guard.ts, compaction-handoff.ts
│   ├── agent_ops/                          # the office-automation runtime (Track A) — stdlib core + adapters
│   │   ├── adapters/                         # office/outlook/excel/hwp/matlab/autocad/fluent/solidworks/browser
│   │   ├── config/, control/, policies/, archive/, results/, reports/, state/
│   │   └── *.py                              # agentops.py, doctor.py, orchestrator.py, secretary.py, capabilities.py, ...
│   ├── tests/                              # py -3.11 tests\test_*.py (offline, no network)
│   ├── launch/                             # CMD launchers: AI비서.bat, diag.bat, gateway-smoke.bat, probe-*.bat, run-agent.bat, ...
│   ├── docs/                                # MASTER_PLAN.md, RUNBOOK.md, PILOT_DAY1.md, PILOT_RECORD.md, BRING_IN_CHECKLIST.md
│   ├── config/                              # lig-api.env.example (gateway URL/key template)
│   ├── scripts/                             # precommit_scan.py, install_hooks.bat
│   ├── portal_research/                    # research artifacts (logs/results/screenshots/reports)
│   └── README.md
├── release/                               # offline bring-in tooling for the agent_ops bundle (Track A)
│   ├── build_bundle.py                       # builds the install bundle zip (source + prefetch)
│   ├── build_check_package.py                # builds the environment/runtime check package zip
│   ├── setup.bat                              # company-PC one-click offline installer (pip --no-index)
│   ├── dependencies.json                      # prefetch manifest (per-file SHA256)
│   ├── verify_prefetch.py                     # verifies prefetch files against the manifest
│   └── rehearsal_check.py                     # offline-install rehearsal pre-flight (cloud-doable half of the air-gap rehearsal)
├── probe/                                 # environment + runtime measurement
│   ├── company_check.py                      # single-file company-PC instrument -> one .md report
│   ├── COMPANY_CHECK.md                       # how to use company_check.py
│   └── results/                               # sanitized company measurement results (company_check_YYYYMMDD.md, probe_env_*.json, ...)
├── plan/                                  # agent_ops build-out work board (Track A)
│   ├── STATUS.md                              # the board (task states)
│   ├── PROTOCOL.md, README.md, NEXT_ONSITE.md
│   ├── tasks/                                 # task instructions (P00-01 ... P20-01)
│   ├── reports/                               # worker reports per task
│   ├── reviews/                               # reviewer feedback per task, incl. FINAL-2026-07-04.md
│   └── templates/                             # task/report/review templates
├── results/                               # legacy home-smoke adapter validation notes, superseded by probe/results/ for company measurement
├── skills/                                # reusable AI-worker procedures (worker-loop, repo-conventions, self-review, windows-batch, app-adapter, delegate-to-codex)
├── docs/
│   ├── AI_HANDOFF.md
│   ├── ARCHIVE_SUMMARY.md
│   ├── CHANGELOG.md
│   ├── CURRENT_RELEASE.md
│   ├── INSTALL.md
│   ├── OFFLINE_REHEARSAL.md
│   ├── OPENCODE_INTEGRATION.md
│   ├── REPOSITORY_MAP.md
│   ├── VALIDATION.md
│   └── fable5-rebuild-prompt.md, naming-guide.md, prompt-research.md
├── AGENTS.md
└── README.md
```

## Purpose by folder

### `.github/workflows/`

One workflow builds and verifies the offline OpenCode TUI package (Track B). It owns the final generated installer and artifact.

### `patches/`

Patch files applied to upstream OpenCode. Keep only the active patch unless the user explicitly asks for variant patches.

### `workspace-template/`

Files copied into `%USERPROFILE%\OpenCodeLIG\workspace\` by the generated installer (either track's installer copies the same tree).

This folder contains the runtime `.opencode` commands/agents/plugins (Track B integration) and the `agent_ops` Python runtime (Track A), plus its own `tests/`, `launch/` CMD launchers, and `docs/` (RUNBOOK, MASTER_PLAN, pilot docs).

### `release/`

Offline bring-in tooling for the agent_ops bundle (Track A): builds the install/check-package zips, verifies prefetched dependency hashes against `dependencies.json`, and runs the offline-install rehearsal pre-flight. `setup.bat` is the one-click company-PC installer (wrapped by the top-level `설치.bat` flow).

### `probe/`

`company_check.py` is the single-file instrument brought onto the company PC to measure the environment and, when the agent_ops runtime is alongside it, the runtime itself (doctor/mock/real-agent E2E + app/COM scenarios). `results/` holds sanitized company measurement reports, e.g. `company_check_20260705.md`.

### `plan/`

The agent_ops build-out work board: `STATUS.md` tracks task state, `tasks/` holds instructions, `reports/` holds worker output per task, and `reviews/` holds reviewer feedback (including the program-completion review `FINAL-2026-07-04.md`).

### `results/`

Older home-smoke adapter validation notes recorded before `probe/results/` existed. Superseded for company measurement; kept for historical adapter-validation evidence.

### `skills/`

Reusable procedures for AI workers building out agent_ops (worker loop, repo conventions, self-review, Windows batch conventions, app-adapter pattern, delegating to Codex).

### `docs/`

Human and AI-readable context. This is where Codex and Claude Code should preserve decisions, validation results, unresolved issues, and handoff notes for both tracks.

## Do not recreate

Do not recreate these old folders unless the user explicitly asks for historical material:

- `PROJECT_FULL_SOURCE_TO_EDIT/`
- `REVIEW_AND_WORK_INSTRUCTIONS/`
- `OPTIONAL_PATCH_AND_INSTALLER_REFERENCES/`
- separate root-level manifests for old packages

Use `docs/ARCHIVE_SUMMARY.md` for historical context instead.
