# P14-02 — schedule CLI + capability 등록

| 항목 | 값 |
|------|-----|
| 단계 | P14 (MASTER_PLAN §4 P14 작업 항목 2) |
| 담당 | codex |
| 선행 | P14-01 |
| 환경 | ANY |
| 산출 규모 | CLI + capability 등록 + bench 확장 |

## 목표
일정을 CLI와 자연어 요청(plan 라우팅) 양쪽에서 다루게 한다.

## 작업 항목
1. `agentops.py`에 `schedule` subcommand:
   `add "제목과 날짜 문장"` / `list [--when today|week|all|overdue]` / `today` /
   `done <id>` / `remove <id>`. add는 title에서 due 문구를 parse_due로 추출
   (실패 시 되묻기 문구 출력 + exit 2). 출력은 표 형태 텍스트 (id/제목/기한/분류/상태).
2. `capabilities.py`에 `schedule_management` 등록 (MASTER_PLAN §5 승인 목록):
   keywords: 일정, 약속, 마감, 리마인드, 캘린더, 스케줄, 미루, 연기, schedule, deadline.
   artifact_kinds: [] (산출물 아닌 상태 조작), pending: [] , status: locally_validated.
   plan_task의 next_exact_command가 이 capability 단독 매칭 시 schedule 명령을 안내하게.
3. remove/변경(제목·기한 수정)은 P13-01 `classify_risk`에서 dangerous로 분류되게 연동
   (CLI에서는 확인 프롬프트, --yes 허용).
4. `test_capability_bench.py` 확장: "금요일까지 진동시험 보고서 마감 일정 등록해줘" →
   schedule_management 라우팅 check + next command 안내 check.
   `tests/test_schedule_store.py`에 CLI subprocess checks (tmp LIG_SCHEDULE_DIR):
   add→today 정합, done, 모호 입력 exit 2, remove 확인 게이트.

## 검증 명령
```bat
py -3.11 tests\test_schedule_store.py
py -3.11 tests\test_capability_bench.py
(회귀 9개 전부)
```

## DoD
- [ ] add→list→done→remove E2E (subprocess, 격리)
- [ ] 자연어 요청이 schedule_management로 라우팅 (bench check)
- [ ] 삭제/변경은 확인 게이트 경유
- [ ] 기존 checks 무손상

## 금지
- capability keywords에 과광범위 단어("등록", "관리" 단독) 금지 — 오라우팅 방지.
