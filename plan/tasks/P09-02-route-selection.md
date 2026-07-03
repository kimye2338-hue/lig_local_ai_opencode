# P09-02 — 작업 유형→라우트 자동 선택 + 진단

| 항목 | 값 |
|------|-----|
| 단계 | P9 (MASTER_PLAN §4 P9 작업 항목 2~3) |
| 담당 | codex |
| 선행 | P09-01 |
| 환경 | ANY |
| 산출 규모 | 코드 ~80줄 + 테스트 ~6 checks |

## 목표
계획된 capability에 따라 EXAONE coding/chat/Qwen fallback 라우트를 자동 선택하고,
선택 근거를 진단에 남긴다 (mock transport로 검증 — real 호출은 P09-03).

## 먼저 읽기
- `workspace-template/agent_ops/lig_runtime.py` (transport 주입 구조 — 유지 필수)
- `workspace-template/agent_ops/capabilities.py` (`plan_task` 반환 형식)
- `workspace-template/tests/test_lig_runtime.py` (기존 14 checks)

## 작업 항목
1. `lig_providers.py`에 `select_route(capability_ids: list) -> str` 추가:
   - {macro_generation, office_cad_automation, browser_automation, file_ops,
     spreadsheet_generation} 중 하나라도 있으면 `"lig-coding"`,
   - 아니면 (document/presentation/mail/meeting 계열) `"lig-chat"`,
   - 빈 목록/미지 id → `"lig-coding"` (기본). 결정 규칙은 dict 상수로 (if/else 나열 금지).
2. `lig_runtime.py`: 호출 시 라우트 인자를 받을 수 있게 확장(기본값 = 기존 동작).
   호출 실패→fallback 전환은 기존 정책 재사용. 진단 파일(runtime-last.json 계열)에
   `"route_selected"`, `"route_reason"`(매칭 capability id), `"profile"` 기록 — host 문자열 금지.
3. `agentops.py`의 agent 경로에서 task를 `plan_task`로 분류해 select_route 적용
   (mock 모드 동작 불변 — mock은 라우트 무시).
4. `tests/test_lig_runtime.py`에 checks 추가: 매크로 task→lig-coding, 문서 task→lig-chat,
   미지→기본, 진단에 route_selected 기록, host 미노출.

## 검증 명령
```bat
py -3.11 tests\test_lig_runtime.py
py -3.11 tests\test_agent_e2e.py
py -3.11 tests\test_agent_cli.py
(회귀 9개 전부)
```

## DoD
- [ ] capability→라우트 매핑이 상수 테이블 기반 (신규 capability 추가 시 한 줄)
- [ ] 진단에 선택 근거 기록, host/key 미포함
- [ ] mock 모드 기존 동작/테스트 완전 보존
- [ ] 기존 checks 무손상

## 금지 / 가드레일
- transport 주입 구조 변경 금지 (mock 테스트 14개의 전제).
- 라우트별 분기를 agent loop 곳곳에 흩뿌리지 말 것 — 선택은 select_route 한 곳에서만.
