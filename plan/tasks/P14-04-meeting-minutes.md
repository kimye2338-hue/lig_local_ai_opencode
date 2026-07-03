# P14-04 — 회의록(meeting_minutes) capability

| 항목 | 값 |
|------|-----|
| 단계 | P14 (MASTER_PLAN §4 P14 작업 항목 5) |
| 담당 | codex |
| 선행 | P14-02 |
| 환경 | ANY |

## 목표
회의 메모/녹취 텍스트(--input) → 구조화된 회의록.md + 액션아이템의 일정 등록 제안.

## 작업 항목
1. `capabilities.py`에 `meeting_minutes` 등록 (§5 승인 목록): keywords 회의록, 회의 정리,
   미팅 정리, 회의 내용, minutes. artifact_kinds: ["meeting_minutes"].
2. `artifact_generators.py`에 `gen_meeting_minutes(task, out_dir, ctx)`:
   - 출력 `회의록.md`: 개요(일시/참석 — 입력에서 감지 못 하면 "확인 필요"),
     논의 내용(입력 텍스트 문단 요약 배치 — 결정적: 문단 첫 문장 추출 방식),
     결정 사항(입력에서 "결정/합의/승인" 포함 문장 추출), 액션아이템 표
     (#|할 일|담당|기한 — "~하기로", "까지", "담당" 패턴 추출, 못 찾으면 TODO+힌트),
     작업 컨텍스트 블록(기존 _context_block 재사용, input-grounded 규칙 적용).
   - LLM enrich가 붙으면 더 좋아지는 구조로 (deterministic 추출이 baseline).
3. 액션아이템 중 기한 패턴이 파싱되는 항목은 말미에 "일정 등록 제안" 섹션으로 출력:
   `py -3.11 agent_ops\agentops.py schedule add "..."` 명령 나열 (자동 등록 금지 — 제안만).
4. `artifact_quality.py`에 meeting_minutes 규칙: 참석/논의/결정/액션아이템 섹션 존재,
   input-grounded 시 입력 반영(required_terms는 기존 공통 로직).
5. `ARTIFACT_KIND_INFO` + bench: 회의 메모 fixture → 회의록 생성, 결정/액션 추출,
   품질 통과, 일정 등록 제안 존재 checks.

## 검증 명령
```bat
py -3.11 tests\test_capability_bench.py
py -3.11 tests\test_secretary.py
(회귀 9개 전부)
```

## DoD
- [ ] 회의 메모 → 회의록.md (결정/액션 추출 fixture 검증)
- [ ] 일정 자동 등록 없음 — 제안 명령만
- [ ] quality 규칙 + bench 통과
- [ ] 기존 checks 무손상

## 금지
- 자동 일정 등록 금지 (승인 게이트 원칙).
- 추출 실패를 그럴듯한 문장으로 채우기 금지 — "확인 필요"/TODO+힌트로 정직하게.
