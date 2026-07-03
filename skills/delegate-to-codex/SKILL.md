---
name: delegate-to-codex
description: (Fable/사용자용) Codex에게 plan/ 작업을 위임할 때의 프롬프트 계약과 검증. Fable 토큰을 아끼고 Codex가 대량 작업을 수행하게 한다.
---

# delegate-to-codex

Codex는 독립 워커다 — 두 번째 손이지, 절대 기준이 아니다. 위임의 산출물은
코드가 아니라 **검증 가능한 보고서**이고, 최종 판정은 리뷰(Fable)가 한다.

## Workflow

1. 위임 프롬프트는 짧게 — 절차를 재설명하지 말고 repo 문서를 가리킨다. 표준 원라인:
   ```text
   Read AGENTS.md, then follow skills/worker-loop/SKILL.md:
   work through plan/STATUS.md READY tasks with auto-advance until blocked.
   ```
   특정 작업만 시킬 때: `... execute only P12-01, then stop.`
2. 실행 형태: 이 repo 클론에서 workspace-write 권한으로. 장문 지시가 필요하면
   프롬프트에 쓰지 말고 task 파일을 고쳐라 (단일 진실 소스 유지).
3. 회수(Fable): Codex가 push한 뒤 리뷰는 **배치**로 —
   `git log --oneline <last-reviewed>..` + `plan/reports/`의 미리뷰 보고서만 읽는다.
   diff 전체 정독은 hard-gate 작업과 보고서가 수상한 경우로 제한.
4. 리뷰 판정은 보고서의 증거(테스트 출력 원문, DoD 대응물)를 재현 명령으로 스팟 확인.
   발견사항은 `plan/reviews/<ID>-rN.md`에 파일:위치 단위로.

## Rules

- 한 위임 = 한 목표. "P12-01 하고 겸사겸사 리팩터링도"처럼 섞지 않는다.
- hard gate 목록(worker-loop 참조)은 위임 프롬프트에서 풀어줄 수 없다 — 리뷰로만.
- Codex 보고가 없거나 증거가 빈 커밋은 revert 대상이지 재해석 대상이 아니다.
- Fable이 직접 구현하는 것은: hard-gate 자체(P10 purge 등), 리뷰에서 2회 반려된 작업,
  task 설계 변경뿐. 나머지는 위임이 기본값.
