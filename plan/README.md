# plan/ — OpenCodeLIG 작업 관리 시스템 (진입점)

이 저장소의 **agent_ops 구축 프로그램**은 이 폴더만 보면 파악·수행·검토가 가능하다.
구현 워커(Codex 등 AI 모델)는 이 파일부터 읽는다.

## 역할

| 역할 | 담당 | 하는 일 |
|------|------|--------|
| 발주자 | 사용자 (kimye2338) | 목표/우선순위 결정, 승인 |
| 설계/리뷰어 | Claude Fable 5 | 작업 지시서(tasks/) 작성, 보고서 검토, 리뷰(reviews/) 작성 |
| 구현 워커 | Codex 등 | tasks/ 를 순서대로 구현, 보고서(reports/) 작성 |

## 폴더 구조

```text
plan/
  README.md        ← 이 파일 (시스템 설명)
  PROTOCOL.md      ← 워커 필수 규약 (읽지 않고 작업 시작 금지)
  STATUS.md        ← 작업 보드 = 유일한 진행 상태 진실 소스
  tasks/           ← 작업 지시서 (Fable만 작성/수정)
  reports/         ← 워커가 작업 후 작성하는 보고서
  reviews/         ← Fable이 작성하는 리뷰/피드백 (워커는 읽기 전용)
  templates/       ← 보고서/리뷰/지시서 템플릿
```

전략 문서(왜 이 순서인지, 환경 확정값, 호환 규칙)는
`workspace-template/docs/MASTER_PLAN.md` — 각 task가 필요한 절을 지정해 준다.

## 작업 생명주기 (워커는 이 순서만 따른다)

```text
1. plan/STATUS.md 에서 위에서부터 첫 READY 작업 1개를 고른다 (동시에 1개만).
2. 그 작업의 plan/tasks/<ID>-*.md 와 PROTOCOL.md 를 읽는다.
3. STATUS.md 에서 자기 작업 행의 상태를 IN-PROGRESS 로 바꾸고 커밋한다.
4. 구현 → 검증 명령 실행 → DoD 자가 점검.
5. plan/reports/<ID>-r1.md 작성 (templates/report-template.md 그대로).
6. STATUS.md 상태를 AWAITING-REVIEW 로 바꾸고, 코드+보고서+보드를 push 한다.
7. Fable 리뷰 대기. plan/reviews/<ID>-r1.md 가 생기면:
   - verdict: APPROVED      → 끝. 다음 READY 작업으로.
   - verdict: CHANGES-REQUESTED → "필수 수정"을 전부 반영하고
     reports/<ID>-r2.md 작성 → 상태 AWAITING-REVIEW → push. (r3, r4 반복)
```

## 상태 정의

| 상태 | 의미 |
|------|------|
| BLOCKED | 선행 작업 미완료 — 착수 금지 |
| READY | 착수 가능 |
| IN-PROGRESS | 워커 작업 중 |
| AWAITING-REVIEW | 보고서 제출됨, Fable 리뷰 대기 |
| CHANGES-REQUESTED | 리뷰 반영 필요 (reviews/ 확인) |
| APPROVED | 완료 확정 (Fable만 이 상태로 변경 가능) |
| SKIPPED | 사용자/Fable 결정으로 건너뜀 (사유는 리뷰 파일에) |

## 지금 바로 시작하려면 (워커에게 주는 원라인 프롬프트)

```text
Read AGENTS.md, then follow skills/worker-loop/SKILL.md:
work through plan/STATUS.md READY tasks with auto-advance until blocked.
```

- auto-advance: DoD 전부 ✅ + 회귀 green + deviation 없음 + hard gate 아님이면
  리뷰를 기다리지 않고 다음 READY로 계속 간다 (조건/hard gate 목록은
  `skills/worker-loop/SKILL.md`). 리뷰어(Fable)는 쌓인 보고서를 배치로 검토한다.
- 수동으로 하려면: PROTOCOL.md 정독 → STATUS.md 첫 READY → 해당 tasks/ 파일 수행.
