# P11-02 — floor 실측 + 파서/프롬프트 보강

| 항목 | 값 |
|------|-----|
| 단계 | P11 (MASTER_PLAN §4 P11) |
| 담당 | codex |
| 선행 | P11-01 |
| 환경 | **LOCAL-LLM 필수** (Ollama + qwen2.5:7b-instruct; 무거우면 3b로 낮추고 기록) |
| 산출 규모 | 실측 리포트 + 보강 패치 |

## 목표
집 PC 로컬 Qwen으로 floor를 실측하고, 실패 유형별로 보강해 7B 성공률 ≥90%를 노린다.
미달이면 **수치 그대로** 보고 (조작 금지).

> **리뷰 반영 (P11-01-r1)**: mock 자가검증이 정본 `capability_floor.md`를 덮어쓴다.
> 이 작업의 첫 커밋에서 실측 리포트 경로를 `capability_floor_<모델명>.md`로 분리하고
> mock 자가검증은 정본 대신 tmp(또는 `capability_floor_mock.md`)에 쓰도록
> `test_capability_floor.py`를 고쳐라 (doctor 필드는 실측 파일 우선으로 갱신).
> P11-01의 native 비율 0/30은 runtime-last.json이 최종 턴 기준이라 생긴 값 —
> 해석 시 이 점을 감안하고, 필요하면 집계 필드를 per-turn으로 바꾸지 말고
> 리포트에 주석으로만 남겨라.

## 작업 항목
1. `py -3.11 tests\test_capability_floor.py` 실측 (7b, 가능하면 3b도) → 리포트 커밋.
2. 실패 유형별 보강 (우선순위 순, 각각 별 커밋):
   - tool-call JSON 깨짐 → `toolcall_parser.py`에 **실측 사례 기반** 규칙 + 사례 테스트
   - 없는 도구 호출 → tool_dispatch 오류 메시지에 사용 가능 도구 목록 포함
   - 반복 실패 → repeated-failure cutoff 파라미터 조정 (구조 변경 금지)
   - 도구 미사용 → 시스템 프롬프트 1줄 보강 (전체 프롬프트+스키마 2.3KB 초과 금지)
3. 보강 후 재실측 → 전/후 성공률을 리포트에 비교 기록.

## 검증 명령
```bat
py -3.11 tests\test_capability_floor.py   (전/후 각 1회 이상)
py -3.11 tests\test_toolcall_parser.py
(회귀 9개 전부)
```

## DoD
- [ ] 전/후 성공률 수치가 리포트와 보고서에 기록 (7B 필수, 3B 참고)
- [ ] 파서 추가 규칙마다 대응 실측 사례 테스트 존재
- [ ] 프롬프트/스키마 총량 측정값 보고 (2.3KB 이하)
- [ ] 기존 checks 무손상

## 금지
- 실측 로그에 없는 형식을 추측으로 파서에 추가 금지.
- 판정 기준/시나리오 변경으로 성공률 부풀리기 금지.
