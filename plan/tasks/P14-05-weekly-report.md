# P14-05 — 주간보고 초안(weekly_report)

| 항목 | 값 |
|------|-----|
| 단계 | P14 (MASTER_PLAN §4 P14 작업 항목 6) |
| 담당 | codex |
| 선행 | P13-01(audit), P14-02(schedule) |
| 환경 | ANY |

## 목표
지난 7일의 audit log + 완료 일정 + 생성 산출물로 "이번 주 한 일" 초안을 자동 생성 —
연구원 사무업무 체감 효과가 가장 큰 비서 기능.

## 리뷰 반영 (r1→r2) — reviews/P14-05-r1.md 필수 수정 1건 (r2 단일 진실 소스)

1. **키워드 경계화**: `capabilities.py`의 `weekly_report.keywords`에서 bare `"weekly"`를
   `"weekly report"`로 교체. `biweekly` 같은 상위어에 substring 오라우팅되지 않아야 함.
   bench negative check 추가: `plan_task("biweekly 회의 잡아줘")`가 weekly_report로
   라우팅되지 않음. (검증 코드는 reviews/P14-05-r1.md "되는 방법" 그대로.)

> 나머지(3개 원천 반영/초안 TODO/기록-only 집계/document kind 재사용)는 r1에서 확인됨 — 유지.

## 작업 항목
1. `capabilities.py`에 `weekly_report` 등록 (§5): keywords 주간보고, 주간 보고, 위클리,
   weekly. artifact_kinds: ["document"] 재사용 (전용 kind 불필요).
2. `agentops.py`에 `weekly` subcommand (+ work 라우팅):
   `results/reports/weekly_<YYYYMMDD>.md` 생성 —
   - 수행 업무: audit.jsonl 지난 7일 집계 (kind별 건수, 대표 task 문구)
   - 완료 일정: schedule done (지난 7일) / 다음 주 예정: open 항목
   - 생성 산출물: results/artifacts 지난 7일 폴더/파일 목록 (개수+대표)
   - 각 섹션 빈 경우 "없음", 자료 원천(audit/schedule/artifacts 경로) 명시
   - 말미: "TODO: 정성 성과/이슈는 직접 보완" (초안임을 명시 — 완성 보고서로 포장 금지)
3. `tests/test_secretary.py` 확장: tmp 격리 fixture(audit 3건, done 일정 2건, artifact 1개)
   → weekly md에 전부 반영 + 빈 fixture에서 "없음" checks.

## 검증 명령
```bat
py -3.11 tests\test_secretary.py
py -3.11 tests\test_capability_bench.py
(회귀 9개 전부)
```

## DoD
- [ ] 3개 원천(audit/schedule/artifacts) 반영 증명
- [ ] 초안 명시("TODO: 직접 보완") 포함
- [ ] 기존 checks 무손상

## 금지
- audit에 없는 활동을 추정 서술 금지 — 기록된 것만.
