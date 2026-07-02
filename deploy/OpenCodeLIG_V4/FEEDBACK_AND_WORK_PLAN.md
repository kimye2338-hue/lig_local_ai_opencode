# FEEDBACK_AND_WORK_PLAN — OpenCodeLIG V4 convergence pass

Date: 2026-07-02. Scope: one-pass fix + architecture reform for the internal Windows PC setup.

## 1. Concise diagnosis

### Already solved (do not re-litigate)
- Proxy tool-call rescue works: identity `LIG generic-toolcall-rescue-v2`, forced smoke test returns `has_tool_calls=true`.
- TUI file creation through the proxy launcher works (real file appeared).
- Config routes to `http://127.0.0.1:8765/v1`, `instructions` populated with `AGENTS_FILEOPS.md`.
- Quoting bug (`cmd /k python "path"`) and cp949 decode crash: fixed patterns are kept in V4 (`[sys.executable, str(path)]`, `encoding="utf-8", errors="replace"` everywhere, TimeoutExpired byte-safe decode).
- Headless `-q` flag: removed; this build has no `-q`.

### Remaining root causes
1. **Plugin startup hang (~45–50s with ANY local plugin, 1.4s with none / `--pure`).**
   Evidence: `command-guard.ts` has zero imports; `compaction-handoff.ts` imports only node builtins. So the hang is not plugin *code* — it is OpenCode's **plugin loader path** that activates the moment any local plugin exists. On an isolated network the most likely slow step is a network fetch inside the loader (Bun/npm registry resolution or similar) hitting a firewalled endpoint and waiting for TCP timeout (2×~21s ≈ 45s matches Windows connect-timeout behavior exactly).
   Correct classification per acceptance criteria: `any_local_plugin_or_plugin_runtime_slow`.
   V4 response (three layers):
   - Diagnostic now runs a **5-way matrix**: `pure_flag`, `no_plugins`, `noop_plugin_only` (a generated do-nothing plugin), `all_plugins_failfast` (registry pointed at `http://127.0.0.1:9` so any hidden fetch fails instantly), `all_plugins_default`. This pins loader-vs-code-vs-network in one run.
   - Launcher env always sets `NPM_CONFIG_REGISTRY=http://127.0.0.1:9` and `NO_PROXY=127.0.0.1,localhost` (harmless offline; converts a 45s hang into an instant failure if the loader fetch is the cause).
   - The two plugins' *functions* are **relocated out of the plugin runtime** so `--pure` loses nothing: command-guard logic moves into the Python proxy (blocks/rescues bash echo/heredoc file writes before OpenCode ever executes them) + native `permission.bash` deny rules stay in config; compaction-handoff becomes an instructions-level rule (`AGENTS_SESSION_START.md` + checkpoint files).
2. **Headless E2E `UnknownError` (rc=1) + false-positive verdict.**
   Two independent defects: (a) verdict counted `after_exists=true` for a preexisting file — fixed with a unique `E2E_<stamp>.md` target and exact marker-line verification; rc alone never passes. (b) The old diag ran headless with a *different* environment than the launcher (no XDG redirects, no `AGENTOPS_HOME`), so headless OpenCode used different data/state dirs than the proven-working TUI — a prime `UnknownError` suspect. V4 gives every entry point the **same** env via one shared builder (`lig_common.build_env`). If headless still fails, the diag automatically extracts `err_*` refs and appends tails of the newest OpenCode logs + proxy log into the report (never dumped to chat).
3. **Config/launcher sprawl and false-positive-prone diagnostics** — solved by the reform (section 3).
4. **Secret hygiene**: this repo is PUBLIC and already exposes the internal gateway hostname in `workspace-template/agent_ops/config/llm_config.example.json`. V4 committed files contain **no key and no internal URLs**; a chat-delivered `SET_LIG_SECRET.bat` (run once) writes `%USERPROFILE%\OpenCodeLIG\secrets\lig_local.env`, which every script auto-loads. No manual editing, nothing secret in git. **Recommendation: make the repo private and scrub the example config.**

## 2. Exact patch/reform plan (what V4 ships)

| Area | File(s) | Change |
|---|---|---|
| Single source of truth | `scripts/lig_common.py` | All paths, env building (UTF-8, XDG redirects, NO_PROXY, registry fail-fast), secret loading, config builder, proxy health/start, safe subprocess capture. Every other script imports it. |
| Daily launcher | `RUN_OPENCODE_LIG.bat` + `scripts/lig_launch.py` | Mode-aware: reads `USERDATA\state\startup_mode.txt` (written by diag; default `pure`). One launcher for daily use. |
| Explicit fallback | `RUN_OPENCODE_LIG_SAFE_PURE.bat` | Forces `--pure`. |
| Diagnostic | `DIAG_OPENCODE_LIG.bat` + `scripts/lig_diag.py` | Marker-based E2E (cannot false-pass), CLI flag probe (never guesses `-q`/`--auto`), 5-way startup matrix, correct classification, auto log-tail collection on failure, GO/NO-GO block, writes `startup_mode.txt` and `LAST_RESULT.json`. No `input()`. |
| Repair | `APPLY_OR_REPAIR_OPENCODE_LIG.bat` + `scripts/lig_apply_config.py` | Rewrites config (backup first), proves `instructions` by read-back. No secrets needed (config points only at the local proxy). |
| Proxy | `proxy/lig_toolcall_proxy.py` (v3) | Same rescue engine + identity string; adds: secret-file loading, bash-write guard with one corrective re-prompt, SSE `Connection: close` fix, refuses to start with a clear message if secrets are missing. |
| Install/update | `INSTALL_OPENCODELIG_V4.bat` | Pure CMD: creates all dirs, backs up existing AGENTS files, copies + strips `.txt`, runs apply. Re-runnable for updates. |
| Agent instructions | `workspace_seed/AGENTS*.md`, `checkpoints/`, `memory/` | Compact Korean policy set (32k-context friendly); session start/end, memory, checkpoint/handoff templates. |
| Skills | `workspace_seed/skills/*.md` | 7 focused skills, loaded on demand (not stuffed into instructions). |
| Docs | `RUNBOOK.md` (Korean), `ARCHITECTURE_REFORM_PLAN.md` | Daily use, GO/NO-GO meaning, resume, bug-report format. |
| Deprecated | `OPENCODE_LIG_FINAL_ACCEPTANCE_TEST_ALL_IN_ONE.bat`, old `DIAG_LIG_STARTUP_AND_TOOLCALL.bat`, old apply/launch variants | Superseded; delete from the PC after V4 install. |

## 3. Final acceptance criteria (unchanged targets, honest measurement)
- `CORE_OK`: config exists, baseURL `http://127.0.0.1:8765/v1`, model `lig-proxy/ai_infra_llm_api`, `AGENTS_FILEOPS.md` in instructions, proxy identity `LIG generic-toolcall-rescue-v2`, forced smoke `has_tool_calls=true`.
- `FILE_CREATE_OK`: unique `E2E_<stamp>.md` contains exact marker line `LIG_E2E_MARKER_<stamp>`. rc alone never passes; preexisting files cannot pass.
- Startup: `PURE_STARTUP_OK` ≤15s (expected ~1.4s). `NORMAL_STARTUP_OK` ≤15s only if the fail-fast registry env fixes the loader hang; otherwise diag pins the class and the launcher stays in SAFE_PURE — with no functional loss because guard/handoff were relocated.
- `STRUCTURE_OK` / `UX_OK`: one daily launcher, one diagnostic, one repair, automatic backups, GO/NO-GO + report path printed, Korean runbook.

## 4. Residual risk / what to send back if something still fails
Run `DIAG_OPENCODE_LIG.bat` and send only the `[RESULT]` block plus the last section of the report file it names. That is enough to continue diagnosis without another long loop.
