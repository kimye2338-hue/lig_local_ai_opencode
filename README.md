# LIG local AI OpenCode — offline office-automation package

사내(오프라인 내부망) Windows PC에서 도는 로컬 AI 업무 자동화 패키지. 두 부분으로 구성된다:

1. **agent_ops 런타임** (`workspace-template/agent_ops/`) — 사내 LLM 게이트웨이를 쓰는
   업무 자동화(비서/일정/문서·매크로 생성/앱 실행 어댑터). **stdlib-only 코어** + 선택적
   어댑터. 오프라인 반입 설치(`release/`)로 배포한다.
2. **패치된 OpenCode TUI** — 권한 승인 모드를 agent/페르소나/워크플로/모델 선택과 분리한
   TUI. GitHub Actions가 고정 upstream 커밋 + 패치로 빌드한다(아래 Build).

## 현재 상태 (2026-07-05)

**회사 PC 실측으로 현재 빌드가 실제 작동함을 확인.** (`probe/results/company_check_20260705.md`)

- 실 게이트웨이 파이프라인(요청→tool-use→응답) end-to-end 성공, doctor·mock work 정상.
- 업무 시나리오 **6/6** 성공(LLM tool 왕복 / Excel 매크로 / MATLAB / HWP / Outlook / AutoCAD).
- **app-validation 완료 어댑터**: office(Excel)·outlook·matlab·hwp·autocad·browser → `available`.
- 잔여(pending): SolidWorks 매크로 실행(연결만 확인), Fluent, office의 Word/PPT 변환.
- 남은 단계: 회사 파일럿 12종 UX 실주행(`workspace-template/docs/PILOT_DAY1.md`).

## 설치 — 더블클릭 한 번 (사내 PC)

번들 zip을 풀고 **`설치.bat` 을 더블클릭**하면 끝. 설치기가 Python 탐지 → 라이브러리
오프라인 설치(`pip --no-index`) → 프로그램 배치 → **게이트웨이 주소/키 입력(붙여넣기,
모르면 Enter)** → 진단 → **바탕화면 [AI비서] 바로가기**까지 자동으로 한다.
매일 쓸 때는 바탕화면 [AI비서] 하나만 실행하면 된다(업무 시키기/브리핑/주간보고/진단 메뉴).

번들 만들기 (집/개발 PC, 인터넷 O):

```bat
py -3.11 -m pip download --only-binary=:all: --platform win_amd64 --python-version 3.11 ^
  --implementation cp --abi cp311 -d release\prefetch pywin32 openpyxl python-pptx
py -3.11 release\build_bundle.py --date YYYYMMDD   :: -> release\dist\OpenCodeLIG_BUNDLE_*.zip
```

- 상세 설치 안내: `docs/INSTALL.md` · 전 과정 체크리스트: `workspace-template/docs/BRING_IN_CHECKLIST.md`
- 반입 전 집 air-gap 리허설: `docs/OFFLINE_REHEARSAL.md`
- 파일럿 필수 = office/COM wheel 8종 + python-embed(전부 매니페스트 실측 해시). 로컬 LLM 서빙
  (llama.cpp/GGUF)·음성(whisper/ffmpeg)은 `deferred`(사내 게이트웨이가 LLM 서빙하므로 파일럿 불필요).

## 환경 진단 (설치 전/후)

단일 파일 계측기로 회사 환경 + 런타임을 한 번에 점검한다.

```bat
py -3.11 probe\company_check.py     :: -> company_check_result.md 하나 (전체 JSON은 부록 포함)
```

agent_ops를 옆에 두면 섹션 0에서 doctor + mock work + real agent(게이트웨이) E2E까지 자동 실행.
자세히: `probe/COMPANY_CHECK.md`.

## agent_ops 구축 관리 (plan 보드)

런타임 구축 작업은 **`plan/`** 폴더에서 관리된다 — 보드(`plan/STATUS.md`), 지시서(`plan/tasks/`),
보고서(`plan/reports/`), 리뷰(`plan/reviews/`). AI 워커는 `plan/README.md`부터, 전략은
`workspace-template/docs/MASTER_PLAN.md`.

## Repository map

```text
release/                       오프라인 반입 설치 (agent_ops)
  build_bundle.py                설치 번들 zip 빌드 (소스 + prefetch)
  build_check_package.py         환경+런타임 점검 패키지 zip 빌드
  setup.bat                      사내 PC 오프라인 설치기 (pip --no-index)
  dependencies.json              의존성 매니페스트 (per-file SHA256)
  verify_prefetch.py             prefetch 해시 검증
probe/                         환경 계측
  company_check.py               단일 파일 종합 계측기 -> .md 하나
  results/                       회사 실측 결과 (sanitized)
results/                       어댑터 실기 검증 증거 (workspace-template/agent_ops/results/adapter_validation/)
skills/                        AI 워커용 스킬 문서 (app-adapter/repo-conventions/worker-loop 등)
workspace-template/            사내 PC workspace로 설치되는 트리
  agent_ops/                     런타임 (코어 stdlib + 어댑터)
  tests/                         py -3.11 tests\test_*.py (네트워크 없음)
  launch/                        CMD 런처
  docs/                          RUNBOOK / MASTER_PLAN / PILOT / 반입 체크리스트
plan/                          구축 작업 보드 (STATUS/tasks/reports/reviews)
docs/                          패키지 문서 (INSTALL / OFFLINE_REHEARSAL / OPENCODE_INTEGRATION 등)
.github/workflows/build-offline-package.yml   OpenCode TUI 오프라인 패키지 빌드
patches/opencode-permission-mode-toggle.patch  고정 upstream OpenCode에 적용되는 패치
AGENTS.md                      이 repo에서 일하는 AI 에이전트 규칙
```

## OpenCode TUI 빌드 (패치 바이너리)

GitHub Actions의 `Build LIG OpenCode offline package` 워크플로가 수행:

1. upstream `anomalyco/opencode` 고정 커밋 `afff74eb2c9fc3808a9795f365707f32853099e9` 클론
2. `patches/opencode-permission-mode-toggle.patch` 적용
3. 의존성 설치·typecheck·Windows 바이너리 빌드
4. `payload`(opencode.exe) + `workspace` + 설치기 BAT + `SHA256SUMS.txt` 오프라인 패키지 조립
5. 필수 파일·전 SHA256 검증 후 업로드

TUI 사용 바이너리는 `main`의 최신 성공 워크플로 런에서 나온 `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE`
아티팩트를 쓴다(자가검증 SHA256SUMS 내장). 상세: `docs/CURRENT_RELEASE.md`, `docs/INSTALL.md`.

### TUI 사용자 동작

- `Shift+Tab` = `[PERM:ASK]` / `[PERM:AUTO]` 토글만. `Shift+F3` = 이전 agent 단축키.
- `/permission status|ask|auto|cycle`, `/perm ...` 동작. AUTO는 `reply: "once"`.
- 스피너 크래시 완화: 오프라인 TUI 빌드에서 직접 `<spinner>` 렌더 경로 제거.

## AI 협업 규칙

Codex·Claude Code·기타 AI 리뷰어: `AGENTS.md`와 `docs/AI_HANDOFF.md`를 먼저 읽는다.
source-of-truth 변경은 워크플로·패치·workspace 템플릿·plan 보드·docs에 집중한다. 과거 병렬
지시 번들을 재생성하지 않는다.
