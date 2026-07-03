---
name: worker-loop
description: plan/ 보드의 작업을 연속 수행하는 워커 루프. 작업 세션을 시작하거나 "다음 작업 진행" 요청을 받으면 사용.
---

# worker-loop

plan/STATUS.md의 READY 작업을 위에서부터 하나씩, 승인 대기 없이 연속으로 닫는 루프.

## Workflow

1. `plan/STATUS.md`에서 첫 READY 작업 1개 선택 → 상태 IN-PROGRESS로 수정(자기 행만) → 커밋.
2. `plan/tasks/<ID>-*.md` 읽기 → [작업 항목] 순서대로 구현. 공통 규칙은
   `skills/repo-conventions`를 따르고 재확인하지 않는다.
3. [검증 명령] 전부 실행 → `skills/self-review` 체크 통과 → 코드 커밋(`<ID>: 요약`).
4. `plan/reports/<ID>-r1.md` 작성(templates/report-template.md 구조 그대로, 증거는 출력
   마지막 줄 원문) → STATUS를 AWAITING-REVIEW로 → push.
5. **auto-advance 판정**: 아래 전부 참이면 리뷰를 기다리지 말고 1로 돌아가 다음 READY 진행:
   - DoD 전 항목 ✅ (❌/부분 없음)
   - 회귀 테스트 전부 exit 0
   - deviation 없음 (계획대로 됨)
   - hard gate 아님 (아래 Rules)
   하나라도 거짓이면 그 자리에서 중단하고 리뷰를 기다린다.
6. `plan/reviews/`에 내 작업의 CHANGES-REQUESTED가 있으면 새 작업보다 **먼저** 반영한다.

## Rules

- **task 지시서의 코드 블록·시그니처·반환 스키마·문구는 그대로 사용한다** (이름/형식
  임의 변경 금지). 지시서가 현재 코드와 안 맞으면(예: "이미 구현됨"이어야 할 것이 다름,
  라인 번호 어긋남) 그 항목을 임의 해석으로 구현하지 말고 — 주변 코드를 다시 읽어
  지시서의 **의도**(델타)만 적용하고, 어긋난 사실을 보고서 deviation에 기록한다.
  같은 이유로, 지시서에 "이미 구현됨"으로 표시된 기능은 절대 다시 만들지 않는다.
- **auto-advance는 연속 최대 3개 작업까지.** 3개를 제출했으면 리뷰를 기다린다
  (약한 실수 하나가 다음 작업들로 번지는 것을 차단).
- hard gate (리뷰 APPROVED 전 진행 금지): adapter `available=True` 전환 / capability·artifact
  kind 추가 / dependencies.json 변경 / 파괴적 git / plan/tasks·reviews/·skills/ 수정 /
  FABLE-ONLY·HUMAN 태그 작업.
- 환경 태그(LOCAL-LLM/CHROME/EXCEL/INTERNET)가 현재 환경과 안 맞으면 착수하지 말고
  STATUS 이력에 한 줄 남기고 다음 READY로.
- 같은 접근 2회 실패 → 접근 변경. 3회 → 해당 항목 pending으로 보고하고 작업의 나머지 완료.
- 한 세션에 동시에 여러 작업 IN-PROGRESS 금지.
