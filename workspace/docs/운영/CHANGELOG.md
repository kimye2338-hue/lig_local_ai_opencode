# Changelog

## 2026-07-10 - CF-0 ~ CF-6 hardening complete

- 테스트 하니스 경로 의존을 제거해 `test_existing_install_hotfix.py`가 Codex/하니스 셸에서도 안정적으로 돈다.
- OpenCode 플러그인 4종을 비동기/비블로킹 기준으로 재정리했다.
  `memory-inject.ts`는 fallback 후 백그라운드 refresh로 바뀌었고,
  `session-autosave.ts`는 delta 버퍼링 후 ended 시점 flush로 바뀌었다.
- 햄스터 상태 판정은 실존 OpenCode 이벤트만 사용하도록 정리했다.
  가짜 `task.start`/본문 substring 추정은 제거했고, `task` tool 구조 신호만 본다.
- 자가개선은 별도 원장을 줄이고 메인 기억 원장으로 통합했다.
  실패/교훈/다음 세션 주입이 한 경로로 흐르며 중복 적재를 줄였다.
- 런처는 fast runtime 마이그레이션, `ocd` 작업폴더 보존, 햄스터 직접 실행,
  회사망 fetch 차단 환경변수 유지 기준으로 다시 검증했다.
- `agent_ops/release_contracts.py`를 추가해 런처/플러그인/진단 마커 계약을 한 곳으로 모았다.
  `pending_check.py`, `quality_gate.py`, 회귀 테스트가 이 공통 계약을 바라본다.
- `workspace/patches/build_final_patch.py`를 추가했다.
  이 스크립트가 원본 플러그인/런타임 파일을 읽어
  `existing_install_hotfix_20260709.py` 임베드를 다시 맞추고,
  `최종_패치파일.bat`를 CRLF/오프라인 포함 상태로 재생성한다.
- `existing_install_hotfix_20260709.py`는 이제 `release_contracts.py`도 같이 복구한다.
  따라서 기존 설치본에 최신 `quality_gate.py`를 밀어 넣어도 import 누락이 나지 않는다.

검증:

- `py -3.11 -m pytest tests\test_existing_install_hotfix.py tests\test_quality_gate.py tests\test_opencode_lig_plugin_runtime.py -q`
  - 결과: `27 passed`
- `py -3.11 tests\test_launch_bats.py`
  - 결과: `ALL 101 CHECKS PASSED`
- 로컬 커밋:
  - `01da2a5 fix hotfix test harness path dependency`
  - `ddc16b8 make plugin recall and autosave nonblocking`
  - `8223bc8 align hamster status bridge with real opencode events`
  - `b15d426 merge self improvement into main memory pipeline`
  - `9e3cced harden launcher migration and ocd environment handling`
  - `22ea48c centralize release runtime contracts`
  - `5df9726 rebuild offline hotfix and final patch bat`

## 2026-07-05 - FULL (완전 오토) permission tier

- TUI patch: permission policy is now a 3-way cycle ASK → AUTO → FULL
  (Shift+Tab). AUTO keeps replying `once` per request; FULL replies `always`
  so the same permission is remembered for the rest of the session — the
  fewest-interruption tier the user asked for. `/permission full` (+ `/perm`)
  added; FULL badge renders in the error color as a visual caution.
- Boundaries unchanged: explicit core `deny` is resolved before a request is
  surfaced, and command-guard keeps blocking dangerous bash in every tier.
- CI applies the patch with `git apply --recount` (headers recounted from
  body); apply/typecheck/build validation happens in the PR workflow.

## 2026-07-05 - 3 modes, guaranteed recall, image pet, IME mitigation

- **Modes reduced to 3**: built-in `build`(일반) / `plan`(계획) + one unified
  `agent`(에이전트 — agent_ops runtime + specialist subagents, work recipes,
  memory rules, command-guard rules). The old agentops-supervisor/autopilot/
  plan primaries are merged into `agent.md`; installer and patch actively
  remove the obsolete files from existing installs so Tab cycles only 3.
  Approval stays orthogonal: Shift+Tab ASK/AUTO (AUTO = auto-approve once
  each; command guard still blocks dangerous commands).
- **Guaranteed recall** ("기억해놓으면 꼭 회상"): user-sourced memories and
  recent error lessons are now ALWAYS injected into the agent loop
  (`pinned_recall`), regardless of keyword overlap; keyword recall adds on
  top (id-deduped). Agent-loop failures (tool_loop_cutoff/llm_failed/
  max_turns) auto-record an error_pattern that the next run recalls —
  mechanical trial-and-error learning. New `test_recall_guarantee.py`
  (7 checks).
- **Pet overlay uses the user's sticker set**: 6 state images (idle/working/
  done/needs_user/error/stalled) cut from the provided sheet into
  `agent_ops/ui/assets/pet/`; overlay renders them (procedural fallback,
  `LIG_PET_DIR` override). `run_agent_loop` publishes live status via
  status_writer so the pet reflects real work; desktop [비서펫] shortcut.
- **Korean IME input-lag mitigation**: `oc.bat` sets chcp 65001; the
  double-click [오픈코드] launcher opens in Windows Terminal when available
  (legacy conhost IME composition lag is the main suspect) — company-PC
  validation pending; RUNBOOK entry added.

## 2026-07-05 - LLM Wiki: compounding topic pages (Karpathy pattern, offline-first)

Memory grows into an Obsidian-compatible wiki instead of only an event list:

- New `agent_ops/wiki_manager.py` — 3 layers per the LLM Wiki pattern:
  raw ledger (`memory.jsonl`, immutable) → compiled wiki
  (`memory/wiki/<topic>.md`, regenerated deterministically, wikilinked via
  `[[topic]]`, `index.md` catalog + `log.md` operations log) → schema
  (`WIKI_SCHEMA.md`, seeded once, maintenance rules for agent+human).
- Compounding: every `remember`/self-lesson ingests into topic pages in place —
  the same page thickens as records accumulate. `wiki/manual/` is a
  human-owned area never touched by automation.
- Curation loop: `memorycheck`/`agentops.py wiki` run consolidate + lint
  (duplicate titles, orphan pages, stale topics — report only, never delete).
  Optional `wiki --curate` polishes page summaries via the gateway LLM behind
  a quality gate (anchored-to-ledger or discarded); offline-safe no-op without
  a gateway, stale markers when newer records arrive after curation.
- Compounding recall: the agent loop now injects the matching distilled topic
  page (excerpt) alongside raw memory recall — accumulated knowledge gets
  richer per prompt automatically.
- Knowledge book becomes blog-like: new "주제별 지식 (위키)" chapter with topic
  chips, expandable page articles, clickable `[[wikilinks]]` as anchors, and a
  pointer for opening `memory/wiki` as an Obsidian vault.
- Tests: `test_wiki_manager.py` (27 checks green); full suite unaffected.

## 2026-07-05 - browser reliability: sticky tab, SPA render wait, fill action

Defects found by a live headless-Chromium E2E (SPA page, JS-late render, JS click):

- Sticky active tab: every action reconnected and re-picked "first tab", so the
  tab opened by read_web_page and the tab seen by click/find_clickables could
  differ (reproduced live: empty clickables, failed click). The adapter now
  remembers the last used tab id and reuses it across calls; open_url/new_tab/
  select_tab update it.
- SPA render wait: open_url waited only for readyState, so early snapshots saw
  an empty body and the textContent fallback leaked raw <script> source into
  "rendered text". Now: innerText → script/style-stripped textContent →
  html-to-text, plus a short render-settle poll (open_url returns rendered flag).
- spa_map returns to the root URL after a click that navigated away, so the
  root selector list stays valid for the remaining clicks.
- New `fill` action (selector or placeholder/label/name text match, React-safe
  native value setter + input/change events, optional Enter) — reachable via
  browser_action for portal search/login forms.
- Live E2E (13 checks vs a local SPA: render text w/o script leak, click by
  text, view switch, fill+enter search, spa_map explore, sticky new_tab) now
  regression-coded into test_browser_adapter's live section (26 checks green
  with Chromium; static-only environments keep the SKIP path).

## 2026-07-05 - ocd folder profiles + shared global memory + patch package

- New `ocd` command (installed to `%USERPROFILE%\OpenCodeLIG\bin`, on PATH):
  opens OpenCodeLIG in the current folder, seeding `.opencodelig\`
  (profile.json / PERSONA.md / PROJECT_MEMORY.md / RULES.md / TASKS.md) on
  first run only — customized files are never overwritten. `ai` opens the menu.
- Agent context assembly now injects, in order: global memory recall →
  folder PROJECT_MEMORY → folder PERSONA → folder RULES → task, with the
  documented conflict rule (safety/global preferences > local persona;
  local rules > generic defaults; conflicts reported, not swallowed).
- New LLM tools `project_info` (context-source diagnostics) and `remember`
  (durable global-memory writes from inside a run) — implemented AND exposed
  through the dispatcher registry + tool schema, per the self-extension rule.
- Doctor now reports cwd / global memory dir / folder profile state.
- `core.run_cmd` captures child output as bytes and decodes UTF-8→CP949→replace,
  fixing Korean CMD mojibake in captured output (RUNTIME_LESSONS §4).
- Browser CDP exposure finished: `test_browser_adapter` updated for the SPA
  action set (was still pinned to the old five-action tuple).
- New `release/build_patch.py`: builds `OpenCodeLIG_PATCH_<date>.zip`
  (패치.bat + workspace overlay) that updates program files only — backs up
  changed files, never touches `OpenCodeLIG_USERDATA` (memory preserved),
  regenerates bin launchers. Companion to the full install bundle.
- Tests: `test_ocd_profiles.py` (25 checks), `test_patch_build.py` (21 checks).

## 2026-07-05 - agent_ops runtime rebuild + company validation

### Final polish (same day, ultracode full review)

- One-click install: bundle-root `설치.bat` + interactive gateway setup + desktop
  [AI비서] menu; all launcher BATs CRLF + shared Python 3.11 resolver (_py.bat).
- `work --mode real` now actually fills artifact content via the gateway LLM
  (quality-gated enrich, scaffold fallback); `work --execute` actually runs safe
  adapter mappings (matlab/.m, document->.hwp, macro->input .xlsx copy,
  autocad with input .dwg) and reports unmapped kinds honestly as no-auto-run.
- 'HWP/Word 변환' routes to document generation (no more stray AutoCAD/VBA kinds).
- Clear Korean guidance on missing gateway config and total-gateway-failure paths.
- 22 verified findings (10 must / 12 should) from a 42-agent review, all fixed;
  regression 20 green + new dispatch tests; docs (INSTALL/VALIDATION/
  REPOSITORY_MAP/AI_HANDOFF/launch README) aligned to the validated state.

Major milestone: the `agent_ops` office-automation runtime was rebuilt on the
`rebuild/fable5-open-architecture` branch and validated on the company PC.

- **Runtime**: stdlib-only core (weak-model tool-call recovery parser, LIG provider
  fallback, resilient LLM runtime with injectable transport, sandboxed file tools,
  mock/real agent loop, checkpoint/resume), keyword-routed capability planner with a
  NEGATIVE_CORPUS bench guard, input-grounded artifact generation + per-kind quality
  validators, approval gate + audit log, schedule/briefing, secretary capabilities.
- **Adapters**: COM (Excel/Word/PPT/Outlook/HWP/SolidWorks), batch (MATLAB/AutoCAD/
  Fluent), browser CDP. Optional-import graceful degradation; execution gated behind
  approval.
- **Company validation (2026-07-05)**: real gateway pipeline end-to-end (tool-use loop)
  succeeded; 6/6 business scenarios passed. Adapters office(Excel)/outlook/matlab/hwp/
  autocad/browser flipped to `available` with recorded evidence
  (`probe/results/company_check_20260705.md`). SolidWorks (connect-only), Fluent, and
  office Word/PPT convert remain pending.
- **Offline bring-in** (`release/`): per-file SHA256 prefetch manifest, `build_bundle.py`
  (transparent zip + internal MANIFEST_SHA256, secret refusal), offline `setup.bat`
  (`pip --no-index`), `verify_prefetch.py`, air-gap rehearsal pre-flight + procedure.
  Pilot deps = 8 office/COM wheels + python-embed (all hashes measured); local-serving
  and voice binaries deferred.
- **Diagnostics** (`probe/`): single-file `company_check.py` -> one `.md` report,
  auto-detecting a co-located runtime to run doctor + mock + real gateway E2E.
- **Security**: internal hostname purged from git history (git-filter-repo, all branches
  + main); secret-scan pre-commit; no secrets/hosts in code, commits, bundles, or reports.
- **OpenCode integration** (`docs/OPENCODE_INTEGRATION.md`): agent_ops runs as a parallel
  CLI (no external-runtime hook in OpenCode plugins), confirmed against official docs.

## 2026-07-01 - Repository cleanup and source-of-truth reset

- Merged PR #4 into `main`.
- Replaced the scattered old layout with clear top-level areas:
  - `.github/workflows/`
  - `patches/`
  - `workspace-template/`
  - `docs/`
- Condensed old Claude/Opus/Codex prompt bundles into `docs/ARCHIVE_SUMMARY.md`.
- Moved the installed workspace source from `PROJECT_FULL_SOURCE_TO_EDIT/` to `workspace-template/`.
- Moved the OpenCode source patch to `patches/opencode-permission-mode-toggle.patch`.
- Renamed the package workflow to `.github/workflows/build-offline-package.yml`.
- Added a single shared handoff file at `docs/AI_HANDOFF.md`.

## 2026-07-01 - Spinner crash fix

User report:

```text
reconciler unknown component type spinner
```

Decision:

The offline Windows TUI must not render direct custom `<spinner>` JSX unless the renderable is proven registered in that exact runtime.

Changes:

- `packages/tui/src/component/spinner.tsx` renders text fallback.
- `packages/opencode/src/cli/cmd/run/footer.subagent.tsx` uses status text/icon.
- `packages/opencode/src/cli/cmd/run/footer.view.tsx` removes direct busy footer spinner block.

User impact:

- The tiny loading animation is replaced with stable text/status output.
- OpenCode should no longer crash when asked to work.

## 2026-07-01 - Offline artifact hardening

- Artifact upload now uses the package directory instead of ZIP-inside-ZIP.
- `include-hidden-files: true` keeps `.opencode` files in the artifact.
- Workflow validates required files before upload.
- Workflow verifies every `SHA256SUMS.txt` entry.
- Installer checks `payload/opencode.exe` checksum before copying.
- Installer backs up existing `%USERPROFILE%\OpenCodeLIG` before overwrite.

## 2026-07-01 - Permission mode hardening

- `/perm` aliases now use the same direct parser as `/permission`.
- AUTO duplicate-reply protection tracks request id.
- Windows x64 binary selection fails if no matching `opencode.exe` is found.
- Branch pushes under `codex/**` and PRs trigger the package workflow.

## Earlier retained context

The old review bundles identified these important AgentOps runtime themes, retained in summarized form:

- Windows-safe file locks.
- Command guard must be in the OpenCode tool execution path.
- Parallel orchestrator must atomically claim tasks.
- Internal LLM gateway may be keyless.
- Memory should dedupe/cap lessons and error patterns.
- Status should remain read-only.
- Offline plugins should avoid npm imports.

See `docs/ARCHIVE_SUMMARY.md` for the condensed archive notes.
