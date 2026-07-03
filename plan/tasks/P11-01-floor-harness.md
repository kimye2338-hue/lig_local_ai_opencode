# P11-01 — weak-model capability-floor 하네스

| 항목 | 값 |
|------|-----|
| 단계 | P11 (MASTER_PLAN §4 P11) |
| 담당 | codex |
| 선행 | P09-03 |
| 환경 | ANY (하네스 자체는 LLM 불필요 — mock으로 검증) |
| 산출 규모 | 테스트 파일 1개 + 리포트 생성 코드 |

## 목표
로컬 LLM으로 시나리오 10종×3회를 자동 실행해 tool-call 성공률/실패 유형을 집계하는
하네스를 만든다 (실측 자체는 P11-02).

## 먼저 읽기
- `tests/test_real_llm_smoke.py` (P09-03 산출 — 서버 감지/SKIP 패턴 재사용)
- `tests/test_capability_bench.py` (시나리오 재사용 — 새 시나리오 발명 금지)
- `agent_ops/tool_dispatch.py` (실패 유형: tool-dispatch-history.jsonl 형식)

## 작업 항목
1. `tests/test_capability_floor.py`:
   - 서버 부재 → SKIP + exit 0 (P09-03 패턴).
   - 시나리오 10종 = capability bench의 단일 6종 + 복합 4종을 태스크 문자열로 재사용.
   - 각 시나리오 × N회(기본 3, env `FLOOR_REPEAT`로 조정) 실행, 판정: exit 0 + 기대 산출물 존재.
   - 집계를 `agent_ops/results/reports/capability_floor.md`로 저장: 총 성공률, 시나리오별
     성공/실패, 실패 유형 분류(파싱 실패/무한 반복/도구 미사용/기타 — dispatch history 기반).
   - 하네스 로직 자체는 mock 모드 1회 실행으로 검증하는 check 포함 (LLM 없이도 테스트 가능).
2. `doctor.py` artifact_pipeline에 `"capability_floor_report"` 경로 필드 추가.

## 검증 명령
```bat
py -3.11 tests\test_capability_floor.py    (서버 없음 → mock 자가검증 + SKIP)
(회귀 9개 전부)
```

## DoD
- [ ] 서버 없이도 하네스 자가검증 checks 통과 + 실측부 SKIP
- [ ] 리포트 md 형식: 성공률 표 + 실패 유형 표 (예시 출력 보고서에 첨부)
- [ ] 기존 checks 무손상

## 금지
- 시나리오를 쉽게 바꾸거나 판정 기준 완화 금지.
- 리포트에 태스크 외 대화 원문 전체 저장 금지 (실패 사례 요약만 — 용량/노이즈 관리).
