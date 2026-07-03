# P11-A — lig_runtime에 native function calling(tools) 경로 추가

| 항목 | 값 |
|------|-----|
| 단계 | P11 선행 (실측 근거로 신설 2026-07-03) |
| 담당 | codex |
| 선행 | P09-02 (route 선택 완료) |
| 환경 | ANY (mock 검증. gateway 실측은 P11-01/P00-03) |
| 산출 규모 | lig_runtime 확장 ~80줄 + 테스트 |

## 목표
회사 gateway가 OpenAI native function calling을 완전 지원함이 실측됨
(probe/results/company_check_20260703.md: tool_calls_present=True, finish_reason=
"tool_calls"). 취약한 텍스트 파싱 대신 **native tools 경로를 1차**로 만든다.

## 먼저 읽기
- `skills/repo-conventions`
- `agent_ops/lig_runtime.py` (현재 호출 payload 구성 — transport 주입 구조 유지 필수)
- `agent_ops/tool_dispatch.py` (REGISTRY — tools 스키마 생성 원천)
- `agent_ops/toolcall_parser.py` (텍스트 파싱 — fallback으로 유지)

## 작업 항목
1. `lig_runtime.py`:
   - REGISTRY의 도구들을 OpenAI `tools` 스키마(JSON schema) 리스트로 변환하는
     헬퍼 추가 (도구명/설명/parameters). 스키마는 기존 tool 정의에서 파생 — 수기 중복 금지.
   - 호출 payload에 `tools` 포함 옵션 (`use_native_tools`, 기본 True for real/company_gateway,
     mock은 무시). 응답의 `message.tool_calls`를 우선 파싱 → 있으면 그걸로 도구 실행,
     없으면 기존 텍스트 파싱(toolcall_parser)로 **자동 fallback**.
   - finish_reason=="tool_calls" 처리, tool 결과를 `role:"tool"` 메시지로 되돌리는
     멀티턴 루프 (OpenAI 규약). id는 gateway가 "N/A"를 주므로 **자체 생성 id 사용**
     (실측: id 신뢰 불가).
   - 진단(runtime-last.json)에 `tool_call_mode: native|text_fallback` 기록.
2. `mock_transport.py`가 native tools 응답도 흉내 낼 수 있게 확장 (tool_calls 필드 포함
   시나리오 1개) — 기존 mock 시나리오 보존.
3. `tests/test_lig_runtime.py` 확장: native tool_calls 응답 → 도구 실행/멀티턴,
   tool_calls 없는 응답 → 텍스트 파싱 fallback, id 자체생성 확인. 기존 checks 무손상.

## 검증 명령
```bat
py -3.11 tests\test_lig_runtime.py
py -3.11 tests\test_agent_e2e.py
(회귀 전체)
```

## DoD
- [ ] native tool_calls 경로가 mock으로 검증 (도구 실행+멀티턴)
- [ ] tool_calls 없으면 텍스트 파싱으로 자동 fallback (검증)
- [ ] id는 자체 생성 (gateway "N/A" 비의존)
- [ ] 진단에 tool_call_mode 기록, transport 주입 구조/기존 checks 무손상

## 금지
- 텍스트 파싱 경로(toolcall_parser) 삭제 금지 — fallback으로 반드시 유지.
- gateway 응답 id에 의존하는 로직 금지 (실측: "N/A").
