# V4_REVIEW_NOTES — second-pass review (2026-07-02)

## Risks fixed
1. **Stale-proxy false success**: health check now parses full `/health` JSON and
   requires `rev == "v3"` + identity (never identity alone) and
   `upstream_configured == true` before launch. New proxy `/shutdown` endpoint
   lets future upgrades replace an outdated V4 proxy automatically; truly old
   proxies trigger a clear Korean stop message (exit code 4) with close/restart
   steps instead of silent continuation.
2. **Python resolution**: new `scripts\lig_python.bat` shared by all entry BATs:
   `LIG_PYTHON_EXE` → PATH `python` → `py -3.11` → `py -3` → common per-user
   install paths. Every candidate is verified by actually running it (filters
   the Microsoft Store alias). Korean guidance if nothing works.
3. **DIAG/launcher command mismatch**: DIAG now probes BOTH `opencode --help`
   (top-level TUI shape the daily launcher uses) and `opencode run --help`
   (headless), saves results to `state\cli_flags.json`; the launcher reads that
   file and only passes flags proven supported.
4. **Deprecated entry points**: installer quarantines old launcher/diag/apply
   variants from the root AND workspace into `USERDATA\backups\deprecated_*`
   (moved, not deleted). Root keeps exactly 4 BATs.
5. **Public-repo leak**: `workspace-template/agent_ops/config/llm_config.example.json`
   internal hostname replaced with `INTERNAL_LIG_GATEWAY_PLACEHOLDER`.
   (History still contains it — making the repo private is still recommended.)

## UX improvements
- Launcher shows a Korean status panel (mode, proxy rev, config, secrets,
  workspace, usage hints incl. "계속") and `[문제]/[해결]` messages per failure.
- DIAG adds a Korean `[설명]` triage section (per-failure next action: secrets →
  SET_LIG_SECRET, exe → copy to bin, stale proxy → close window, FILE_CREATE
  fail with CORE_OK → send refs/log tails, pure mode → "정상, 기능 손실 없음")
  and a one-copy `[보내기]` block for bug reports.
- Installer ends with a readiness checklist ([OK]/[해야함]: exe, secrets,
  Python) and the exact next file to run.
- RUNBOOK now starts with the 4-line "한눈에 보기" and a symptom→fix table;
  architecture is last and optional.
- AGENTS.md: changed-file list after multi-file work, max-one-question rule,
  explicit risky-action confirmation list; new skills `skill_code_patch`
  (backup→patch→verify→report) and `skill_risky_confirm` (plan-first approval).

## Browser / UI automation direction (recommended)
Phased optional modules, core untouched (see `AUTOMATION_ROADMAP.md`):
- **Phase B (browser)**: Edge/Chrome DevTools Protocol with a dedicated debug
  profile (visible window, no access to daily cookies), stdlib CDP client
  exposed as CLI subcommands; read-only tier (open/text/find) first, act tier
  (click/type) gated behind `--confirm` + user approval.
- **Phase C (local UI)**: pywinauto/UIAutomation (offline wheel, isolated in
  `tools_optional\`) — control-by-name, plan-first, per-step reporting.
- **In this PR**: only the two placeholder skills (agent answers honestly that
  automation is not installed and offers alternatives) + the roadmap. No new
  dependencies, no core changes.

## Needs real company-PC testing (cannot be verified here)
- Actual plugin-startup matrix values and whether registry fail-fast unlocks
  normal mode on the real network.
- Headless `opencode run` behavior with the real gateway (UnknownError repro);
  if it recurs, DIAG now auto-collects `err_*` refs + log tails.
- `py` launcher / per-user Python paths on the target machine.
- Stale-proxy path with the genuinely old rescue-v2 proxy running.

## Exact test steps for you
1. Pull branch → rename `INSTALL_OPENCODELIG_V4.bat.txt` → run it.
2. Follow the readiness checklist: copy `opencode.exe` to `bin\`, run
   `SET_LIG_SECRET.bat` once.
3. Run `DIAG_OPENCODE_LIG.bat` → expect `GO`; read the `[설명]` lines.
4. Run `RUN_OPENCODE_LIG.bat` → status panel → type:
   `메모.md 파일을 실제로 만들어줘. 경로와 요약만 답해줘.` → file must exist.
5. Type `계속` in a new session → agent should read the latest checkpoint.
6. If anything fails: copy only the `[보내기]` block from DIAG.
