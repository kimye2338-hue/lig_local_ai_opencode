# ARCHITECTURE_REFORM_PLAN — OpenCodeLIG V4

## 1. Design principles
1. **One source of truth**: every path, env var, and config key is defined once, in
   `scripts/lig_common.py`. Launcher, repair, and diagnostic all import it — they can
   no longer drift apart (the old headless-vs-TUI env divergence becomes impossible).
2. **Four entry points, nothing else**: RUN / RUN_SAFE_PURE / DIAG / APPLY_OR_REPAIR.
   All old launcher and diagnostic variants are superseded and should be deleted.
3. **Honest diagnostics**: every success verdict requires positive evidence that could
   not have existed before the test ran (unique marker files, read-back proofs).
4. **Secrets never in git**: committed files contain no key and no internal URL.
   `secrets\lig_local.env` (written once by the chat-delivered SET_LIG_SECRET.bat) is
   auto-loaded by every script; env vars override it. This repo is public — the old
   `workspace-template/agent_ops/config/llm_config.example.json` already leaks the
   internal hostname and should be scrubbed / repo made private.
5. **Degrade gracefully**: SAFE_PURE is a first-class mode, not a workaround. The two
   plugins' functions were relocated so `--pure` loses nothing:
   - command-guard → Python proxy (`bash_guard_reason` + one corrective re-prompt)
     plus native `permission.bash` deny rules in config.
   - compaction-handoff → instruction-level checkpoint workflow
     (AGENTS_SESSION_START.md + checkpoints/ + SESSION_END_CHECKLIST.md).

## 2. Directory layout (final)
```
OpenCodeLIG\
  RUN_OPENCODE_LIG.bat              daily launcher (mode-aware)
  RUN_OPENCODE_LIG_SAFE_PURE.bat    explicit --pure fallback
  DIAG_OPENCODE_LIG.bat             the ONE diagnostic (GO/NO-GO)
  APPLY_OR_REPAIR_OPENCODE_LIG.bat  config repair with backup + read-back proof
  bin\opencode.exe                  binary (from offline package)
  scripts\lig_common.py             SINGLE SOURCE OF TRUTH
  scripts\lig_launch.py             launcher logic
  scripts\lig_apply_config.py       config writer
  scripts\lig_diag.py               diagnostic
  proxy\lig_toolcall_proxy.py       local tool-call rescue proxy (v3)
  secrets\lig_local.env             internal URL + key (LOCAL ONLY, never in git)
  workspace\                        user project area
    AGENTS.md / AGENTS_FILEOPS.md / AGENTS_SESSION_START.md   (config instructions)
    AGENTS_CONTEXT.md / AGENTS_MEMORY.md / SESSION_END_CHECKLIST.md  (on demand)
    skills\skill_*.md               7 focused skills, read on demand
    memory\MEMORY.md                durable facts (never overwritten by updates)
    checkpoints\CHECKPOINT_LATEST.md + CHECKPOINT_TEMPLATE.md
  docs\RUNBOOK.md ...               user docs
  logs\lig_toolcall_proxy.log
OpenCodeLIG_USERDATA\
  opencode_config\opencode.proxy.json   machine-generated; never hand-edit
  opencode_data|state|cache\            XDG-redirected OpenCode dirs
  diagnostics\LIG_DIAG_*.txt, LAST_RESULT.json
  backups\                              automatic pre-overwrite backups
  state\startup_mode.txt                normal|pure, written by diag
```
Deviation from the requirements sketch: memory/checkpoints live in `workspace\`
(not USERDATA) because OpenCode's tools read/write the workspace without
`external_directory` permission prompts; USERDATA keeps machine artifacts only.

## 3. Config / proxy / launcher source-of-truth flow
```
lig_common.py --build_config()--> opencode.proxy.json   (rewritten every launch/repair,
                                   backup on repair; no secrets inside - it points
                                   at 127.0.0.1:8765 only)
secrets\lig_local.env --load_secrets()--> env --> proxy (upstream URL + key)
diag --> state\startup_mode.txt --> launcher (--pure or normal)
```

## 4. Update / repair strategy
- **Update**: re-run INSTALL from a new deploy folder. Idempotent; AGENTS files are
  backed up first; MEMORY.md and checkpoints are never overwritten; `.txt` suffixes
  stripped automatically; config re-applied and proven by read-back.
- **Repair**: APPLY_OR_REPAIR rewrites config (backup first) and prints proof.
- **Rollback**: backups in `USERDATA\backups\` are timestamped copies.

## 5. Startup-hang strategy (plugin loader)
The diag's 5-way matrix distinguishes: pure / no plugins / no-op plugin /
plugins + registry-fail-fast / plugins default. Launcher env always sets
`NPM_CONFIG_REGISTRY=http://127.0.0.1:9` and `NO_PROXY=127.0.0.1,localhost`. If the
hang is a hidden registry/network fetch, fail-fast makes normal mode fast and diag
flips `startup_mode.txt` to `normal` automatically. If any local plugin still hangs
the loader itself, the system stays in `pure` permanently — with zero functional
loss (see principle 5). Either way the user experience is identical.

## 6. Daily workflow (user)
Run RUN_OPENCODE_LIG.bat → type Korean instructions → files actually get written.
On trouble: DIAG → send [RESULT] block + last report section. See RUNBOOK.md.
