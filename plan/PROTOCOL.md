# PROTOCOL — 구현 워커 필수 규약

이 문서를 지키지 않은 작업은 리뷰에서 CHANGES-REQUESTED 또는 REJECTED 처리된다.

## 0. 스킬 우선 (토큰 규약)

반복 절차 지식은 `skills/`에 있다 — **작업 루프는 `skills/worker-loop/SKILL.md`가
단일 진실 소스**이며, auto-advance(리뷰 대기 없이 다음 READY 연속 진행) 조건과
hard gate 목록도 거기에 있다. 코드 작업 전 `skills/repo-conventions`,
제출 전 `skills/self-review`를 적용한다. task 지시서와 스킬이 충돌하면 task가 이긴다.

## 1. 시작 절차 (매 작업 공통, 순서 고정)

```bat
cd /d <repo 루트>
git status -sb        ← 아래 §5의 "불가침 untracked" 외 이상 없어야 함
git log --oneline -5  ← 현재 HEAD를 보고서에 기록할 것
cd workspace-template
py -3.11 tests\test_capability_bench.py   ← 시작 전 통과 확인 (깨져 있으면 작업 중단, 보고)
```

읽기 순서: `plan/STATUS.md` → 본인 `plan/tasks/<ID>-*.md` → task가 지정한
`workspace-template/docs/MASTER_PLAN.md` 절 → (있으면) 직전 리뷰 `plan/reviews/<ID>-r*.md`.

## 2. 환경 기본값

- Python: **`py -3.11`** 로만 실행 (3.14 기본이므로 반드시 명시).
- 콘솔/파일 인코딩: 새 BAT는 UTF-8 no BOM + CRLF, 첫 줄부에 `chcp 65001` +
  `set PYTHONUTF8=1`. Python 파일은 UTF-8, 첫 줄 `# -*- coding: utf-8 -*-`.
- 테스트 스타일: **pytest 금지.** 기존 `check(label, cond)` + 실패 시 `sys.exit(1)` 스타일.
  외부 자원(LLM 서버/앱/포트/인터넷)이 필요한 테스트는 자원이 없을 때
  `SKIP (...— skipped, not failed)` 를 출력하고 **exit 0**.
- 실행 확인 명령(회귀, 작업 종료 전 전부):
  ```bat
  py -3.11 tests\test_toolcall_parser.py
  py -3.11 tests\test_lig_providers.py
  py -3.11 tests\test_lig_runtime.py
  py -3.11 tests\test_resume.py
  py -3.11 tests\test_encoding_paths.py
  py -3.11 tests\test_tool_dispatch.py
  py -3.11 tests\test_agent_e2e.py
  py -3.11 tests\test_agent_cli.py
  py -3.11 tests\test_capability_bench.py
  py -3.11 tests\test_probes.py
  ```

## 2.5 실측 우선 원칙 (probe/)

환경에 대한 가정(설치 앱, Office 버전, 매크로 보안 정책, gateway의 tool-call 방식)이
필요하면 **`probe/results/`의 최신 결과를 먼저 확인**한다. 결과가 있으면 그것이 사실이다
— 추측으로 덮지 마라. 결과가 없으면 "probe 결과 없음 — 가정: X"를 보고서에 명시하고,
가정이 틀렸을 때 되돌리기 쉬운 방식으로 구현한다. (probe 실행은 P00-01, 사용자 담당)

## 3. 불변 규칙 (요약 — 전문은 MASTER_PLAN §6, §7)

1. **기존 테스트가 깨지면**: 원인 파악 → 못 고치면 본인 변경 revert → 사실대로 보고.
   테스트를 약화/삭제해서 통과시키는 것 금지.
2. **상태 어휘만 사용**: implemented / locally validated / locally validated with mock /
   input-grounded / artifact generated / static reviewed / app validation pending /
   company validation pending. mock을 real이라, scaffold를 완성이라 말하지 않는다.
3. **secret/내부 hostname**: 코드·커밋·보고서 어디에도 금지. `lig-api.env` 실값 커밋 금지.
   진단/보고에는 presence flag(설정됨/안 됨)만.
4. **코어는 stdlib-only**: `workspace-template/agent_ops/` 비어댑터부에 외부 패키지 금지.
   외부 패키지는 어댑터/ingest 확장에만, 사용 전 `release/dependencies.json`에 기록.
5. **원본 불가침**: 앱 자동화는 항상 사본 파일에서. 자동 저장 금지. finally에서 앱 프로세스 정리.
6. **Office는 2016 기준**: MASTER_PLAN §6.2 금지 함수 목록 준수.
7. **capability/어댑터 임의 추가 금지**: MASTER_PLAN §5 목록에 있는 것만.
8. 같은 접근 2회 실패 → 접근을 바꾼다. 3회 실패 → 그 항목을 pending으로 보고서에 남기고
   작업의 나머지를 마무리한다 (세션을 통째로 태우지 않는다).

## 4. Git 규칙

- 브랜치: `rebuild/fable5-open-architecture` 에 직접 커밋 (새 브랜치 만들지 않는다).
- 커밋 메시지: `<TASK-ID>: <한 줄 요약>` (예: `P09-01: Add provider profiles and env overrides`).
  한 작업 = 1~3 커밋. 코드 커밋과 보고서/보드 커밋은 분리해도 된다.
- **개별 파일 `git add`만** 사용 (`git add -A` / `git add .` 금지).
- push 전 회귀 전체 통과가 조건. push 실패(충돌) 시 rebase 말고 `git pull --ff-only` 후 재시도,
  안 되면 보고서에 기록하고 중단.

## 5. 파일 소유권 (침범 = 즉시 REJECTED)

| 경로 | 쓰기 권한 |
|------|----------|
| `plan/tasks/`, `plan/reviews/`, `plan/templates/` | Fable 전용 (워커는 읽기만) |
| `plan/reports/<본인 작업 ID>-r*.md` | 워커 |
| `plan/STATUS.md` | 워커는 **본인 작업 행의 상태/보고서 칸만** 수정 |
| repo 루트 untracked 5개: `.gitignore`, `docs/home-lab-status.md`, `logs/`, `tools/`, `validation/` | 불가침 (스테이징 금지) |
| `patches/`, `.github/workflows/` | 이 프로그램 범위 밖 — task가 명시하지 않는 한 수정 금지 |
| 파괴적 git 작업 (force push, filter-repo, reset --hard) | Fable 전용 (P10-01) |

## 6. 보고서 규칙

- 파일: `plan/reports/<ID>-r<라운드>.md`, 템플릿 `plan/templates/report-template.md` **섹션 구조 그대로**.
- 증거 원칙: 주장에는 증거를 붙인다 — 테스트는 **실행한 명령 + 출력 마지막 줄(“ALL n CHECKS …” / SKIP 문구) 원문**을 붙여넣는다. 요약·의역 금지.
- DoD 자가 점검은 task의 DoD 항목을 **하나도 빼지 않고** ✅/❌/부분 으로 표기.
- **계획과 다르게 한 것(deviation)** 은 사소해도 전부 5번 섹션에 적는다. 숨긴 deviation이
  리뷰에서 발견되면 REJECTED.
- 하지 못한 것은 pending으로 정직하게. 빈 섹션은 "없음"으로 명시.

## 7. 리뷰 반영 규칙

- `plan/reviews/<ID>-r<N>.md` 의 **[필수 수정]은 전부** 반영한다. 반영 불가 판단이면
  그 이유를 다음 보고서에 명시하고 해당 항목을 미해결로 표기한다 (몰래 생략 금지).
- [권고]는 선택이나, 채택/미채택을 다음 보고서에 한 줄씩 기록한다.
- 반영 후 `reports/<ID>-r<N+1>.md` 작성 → STATUS를 AWAITING-REVIEW로.
