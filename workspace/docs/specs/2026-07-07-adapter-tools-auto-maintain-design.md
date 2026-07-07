# 설계: 앱 어댑터 대화형 노출 + 자율 기억·위키 유지

작성 2026-07-07. 승인: 사용자(어댑터 전체 노출 / 자동유지 하루 2회).

## 목표
1. **Part A** 대화형 에이전트가 앱 어댑터(Excel/Outlook/HWP/SolidWorks/AutoCAD/Fluent/MATLAB/OCR/데스크톱UI)를 도구로 직접 호출(기존엔 `work --execute` 경로만).
2. **Part B** 사용자가 아무것도 호출하지 않아도 기억·위키가 알아서 쌓이고 정리·최적화된다. 정리 패스는 하루 약 2회 자동 수행.

## Part A — 어댑터 도구
`tool_dispatch.REGISTRY`에 어댑터 패밀리별 도구 1개씩 추가(전체 노출, action 파라미터로 세부):
- action형: `excel_app`(office_convert 포함), `outlook_app`, `hwp_app`, `solidworks_app`, `ocr_screen`, `desktop_ui` → `execute(action, options)`
- 경로형: `matlab_run`(script_path), `fluent_run`(journal_path)
- 특수: `autocad_run`(dwg_path, scr_path)

원칙:
- action은 어댑터의 `ACTIONS`에 대해 검증(LLM이 임의 호출 못 하게) — browser_action과 동일 패턴.
- 앱/COM/엔진 미설치 시 어댑터 `execute`가 이미 `{ok:False, error}` 우아하게 반환 → 래퍼가 `root_cause_category:"app_unavailable"`로 정규화(크래시 없음).
- 옵션은 action 외 인자를 그대로 전달. 결과는 `{ok, data}`로 정규화.
- 기존 `work --execute` 경로·browser 도구는 그대로 유지(중복 아님, 상호보완).

## Part B — 자율 유지 (`auto_maintain.py`)
- `maybe_maintain()`: 마커(USERDATA/state/last_maintenance.json)로 스로틀. 마지막 실행 후 약 11.5h 이상 지났을 때만 수행 → 활동 시 하루 약 2회.
- 유지 내용(각각 best-effort, 실패해도 저장/작업 안 막음):
  1. 위키 consolidate 최신화 + lint(중복/모순/정체 탐지 → log)
  2. 기억 중복 정리: 정규화 제목이 같은 active 기억 중 최고가치 1개만 남기고 나머지 아카이브. **source=user/priority=high는 항상 보호**.
  3. 지식책 재생성.
  4. 마커 갱신.
- 트리거: `add_memory_event` 꼬리(consolidate 직후)에서 `maybe_maintain()` 호출. 기억 저장은 remember/add_activity/record_self_error로 평상시 작업 중 발생하므로 사용자 무개입으로 자동 실행.

## 테스트
- Part A: 각 도구가 REGISTRY/tool_definitions에 뜨고, 앱 없는 환경에서 우아한 실패 반환. 잘못된 action 거부.
- Part B: 마커 없으면 실행·마커 생성, 11.5h 내 재호출은 skip, 중복 기억 아카이브되되 user/high 보호, 실패해도 add_memory_event 정상.
- 전 회귀 green 유지.
