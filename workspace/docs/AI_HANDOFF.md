# AI handoff

This is the single shared handoff file for Codex, Claude Code, Claude chat, and future reviewers. It covers two tracks: the **agent_ops runtime / offline bundle** (this section) and the **patched OpenCode TUI** (rest of this file).

## agent_ops runtime track (2026-07-05 기준 현황)

### 2026-07-05 (후속): ocd 폴더 프로필 + 전역 기억 + 패치 패키지

- **`ocd` 구현 완료** (plan/tasks/FABLE-OCD-WORKSPACE-PROFILES.md): 아무 폴더에서
  `ocd` → `.opencodelig\` 시드(있으면 절대 미덮어쓰기) → 그 폴더에서 OpenCode 실행.
  단일 진실 소스는 `agent_ops/project_profile.py`, 런처는 `agent_ops/ocd.py` +
  설치기 생성 `bin\ocd.bat`(+`ai.bat`, PATH 등록).
- **컨텍스트 주입**: `run_agent_loop` 가 전역 기억 recall → 폴더 기억/페르소나/규칙
  순으로 system 메시지 주입, 충돌 규칙(전역 선호·안전 > 로컬 페르소나, 로컬 규칙 >
  일반 기본값, 충돌은 보고) 포함.
- **LLM tool 노출**: `project_info`, `remember` 신규 등록 (구현≠노출 교훈 반영,
  스키마 예산 7.8KB로 갱신 — test_tool_dispatch 주석 참고).
- **mojibake 수정**: `core.run_cmd` 바이트 캡처 + UTF-8→CP949 폴백
  (`encoding_ops.decode_console_bytes`).
- **패치 패키지**: `release/build_patch.py` → `OpenCodeLIG_PATCH_<date>.zip`
  (프로그램만 교체·변경분 백업·USERDATA 절대 불가침). 전체 설치는 기존
  `build_bundle.py`. 회귀: test_ocd_profiles 25 + test_patch_build 21 신규,
  전 스위트 green(리눅스에서 py셔임 포함 실측; Windows 전용 3개 제외).
- **남은 것**: 회사 PC에서 `ocd` 실주행(새 CMD에서 PATH 반영 확인), 폴더 페르소나
  체감 검증. 브라우저 SPA 액션은 test_browser_adapter 를 SPA 세트로 갱신 완료.

- 런타임(`workspace-template/agent_ops/`)이 재구축되어 **회사 PC에서 실측 검증됨**: doctor·mock work·real agent E2E 전부 성공, 업무 시나리오 6/6 성공. 근거: `probe/results/company_check_20260705.md`.
- 배포는 오프라인 번들 설치 — 번들 zip을 풀고 **`설치.bat`** 더블클릭 한 번으로 끝(빌드는 `release/build_bundle.py`).
- 작업은 `plan/STATUS.md` 보드에서 관리(지시서 `plan/tasks/`, 보고서 `plan/reports/`, 리뷰 `plan/reviews/`).
- 최종 리뷰: `plan/reviews/FINAL-2026-07-04.md` (클라우드에서 가능한 작업 전량 완결 판정).
- 남은 것: 회사 파일럿 12종 UX 실주행 — 절차서 `workspace-template/docs/PILOT_DAY1.md`.

## Current state (patched OpenCode TUI track)

The repository builds one current offline Windows package through one workflow:

- Workflow: `.github/workflows/build-offline-package.yml`
- Patch: `patches/opencode-permission-mode-toggle.patch`
- Workspace copied into the package: `workspace-template/`
- Pinned upstream OpenCode commit: `afff74eb2c9fc3808a9795f365707f32853099e9`

PR #4 was merged into `main` on 2026-07-01.

Important commits:

- PR #4 merge: `bde4cc036d091bb35971999faf7a4394b8865ddf`
- Repository cleanup: `2ac5d4aa99476fe80a44ba5b42391747aee3de11`

Verified cleanup baseline:

- Workflow run: `28505265540`
- Artifact ID: `8004882821`
- Artifact digest: `sha256:2d52e390461b732491eadafcde025ec7f329577d40e7e1f52618be6aab991115`
- `payload/opencode.exe` SHA256: `5fa524bbddb547fcbc776bf15c824945dcdd538b6aaccc077db4b47ff521545e`
- Artifact ZIP SHA matched GitHub digest.
- `SHA256SUMS.txt` verified 81 files with 0 mismatches.
- Hidden workspace files were present.
- `workspace/docs/AI_HANDOFF.md` and `workspace/patches/opencode-permission-mode-toggle.patch` were present.

If a newer successful workflow run exists on `main`, use that newer artifact. The baseline above is the last manually downloaded and checksum-verified artifact.

## User-reported crash and fix

Reported symptom:

```text
OpenCode crashed unexpected error stop the session reconciler unknown component type spinner
```

Root cause:

The offline Windows TUI rendered custom `<spinner>` JSX while the bundled OpenTUI reconciler did not know that renderable type. The reconciler crashed before useful work could proceed.

Fix:

- Remove direct `<spinner>` render paths from the patched offline build.
- Render stable text/status output instead.
- Keep the user-visible tradeoff explicit: no tiny spinner animation, but no session crash when OpenCode starts working.

Do not reintroduce `<spinner>` in this offline build unless a future OpenTUI/runtime version proves the renderable is registered and the Windows artifact is runtime-tested.

## Required behavior

The patch must implement a permission approval policy toggle independent from OpenCode agent/persona/workflow/model state.

Checklist (2026-07-05: FULL mode added by explicit user request):

- `Shift+Tab` cycles permission policy only: ASK → AUTO → FULL → ASK.
- `Shift+Tab` does not cycle agent/persona/workflow/model/plan/autopilot.
- Previous-agent reverse cycle is `Shift+F3`.
- TUI displays current mode, e.g. `[PERM:ASK shift+tab]`, `[PERM:AUTO shift+tab]`,
  `[PERM:FULL shift+tab]` (FULL badge uses the error color as a visual warning).
- `/permission status|ask|auto|full|cycle` and `/perm ...` aliases work.
- AUTO replies to permission requests with `reply: "once"` — never "always".
- FULL (완전 오토) replies with `reply: "always"` — the same permission is
  remembered for the session. This is a deliberate opt-in tier; AUTO keeps the
  original once-only guarantee.
- Neither AUTO nor FULL may bypass command guard or explicit core deny
  (deny is resolved before a request is surfaced to the TUI).
- ASK mode must preserve the original prompt flow.
- Reject, always, and subagent reject flows must not be broken.

## Implementation highlights

The patch changes these upstream OpenCode files after applying to the pinned commit:

- `packages/tui/src/config/keybind.ts`
  - moves `agent_cycle_reverse` from `shift+tab` to `shift+f3`
  - adds `permission_mode_cycle: shift+tab`
  - maps `permission_mode_cycle` to command `permission.mode`
- `packages/tui/src/context/permission.tsx`
  - uses `PermissionMode = "ask" | "auto"`
  - defaults to `args.auto ? "auto" : "ask"`
  - adds `set`, `cycle`, and `toggle`
- `packages/tui/src/app.tsx`
  - registers `permission.mode`
  - command calls `local.permission.cycle()`
- `packages/tui/src/component/prompt/index.tsx`
  - handles `/permission ...` and `/perm ...` commands locally
- `packages/tui/src/routes/session/index.tsx`
  - registers the binding and displays the permission badge
- `packages/tui/src/routes/session/permission.tsx`
  - uses request-id tracking for AUTO duplicate prevention
  - replies with `reply: "once"`
- `packages/tui/src/component/spinner.tsx`
  - falls back to text instead of custom `<spinner>`
- `packages/opencode/src/cli/cmd/run/footer.subagent.tsx`
  - uses status text/icon instead of direct `<spinner>`
- `packages/opencode/src/cli/cmd/run/footer.view.tsx`
  - removes the busy footer direct `<spinner>` block

## Packaging decisions

- GitHub artifact uploads the package directory, not a pre-compressed inner ZIP.
- `actions/upload-artifact@v4` uses `include-hidden-files: true` so `.opencode` files survive.
- `SHA256SUMS.txt` is generated and verified with hidden files included.
- Installer verifies `payload/opencode.exe` before copying.
- Installer backs up an existing `%USERPROFILE%\OpenCodeLIG` before overwriting.
- The package workspace includes `docs/` and `patches/` so future local AI sessions can recover context from the installed machine.

## Collaboration protocol

When an AI agent changes behavior or packaging:

1. Update this file with the new current state.
2. Update `docs/CURRENT_RELEASE.md` if a new artifact is manually downloaded and verified.
3. Update `docs/CHANGELOG.md` with the decision and user impact.
4. Keep old review material condensed in `docs/ARCHIVE_SUMMARY.md`; do not add a new large instruction bundle.
5. Report exact workflow run ID, artifact ID, digest, and verification results.

## Remaining manual validation

Before company-wide use, validate on the target Windows PC:

- `Shift+Tab` toggles ASK/AUTO in the actual terminal.
- `Shift+F3` still reaches previous-agent behavior.
- `/permission` and `/perm` variants behave identically.
- AUTO handles multiple consecutive permission prompts once each.
- ASK, reject, always, and subagent reject still behave as upstream intended.
- Command guard blocks dangerous bash/corrupted approval-window commands.
- OpenCode no longer crashes with `unknown component type spinner` when asked to do work.
