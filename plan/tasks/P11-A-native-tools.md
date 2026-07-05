# P11-A — native function calling 왕복을 실증 형식으로 완성

| 항목 | 값 |
|------|-----|
| 단계 | P11 선행 (실측 근거로 신설 2026-07-03, **실코드 기준 재작성** 2026-07-03 밤) |
| 담당 | codex |
| 선행 | P09-02 (APPROVED) |
| 환경 | ANY (mock 검증. gateway 실측은 P00-03/P11-01) |
| 산출 규모 | 델타 ~40줄 + 테스트 확장 3파일 |

## 목표

회사 gateway에서 **전체 tool 왕복이 실증됨** (tool_calls 수신 → 도구 실행 → role:"tool"
반환 → 최종 답변이 파일 내용 정확 반영 — probe/results/company_check_20260703_r2_scenarios.md ①).
실증에 쓴 메시지 형식 원형은 `probe/company_check.py`의 `scn_gateway_agent()` (506~543행).

제품 코드는 왕복 루프 대부분을 **이미** 갖고 있고, 실증 형식과 다른 점은 딱 두 가지다:
assistant 메시지의 tool_calls 항목에 `id`가 없고, tool 메시지에 `tool_call_id`가 없다.
이 task는 그 델타만 메운다. **아래 표의 "이미 구현됨" 항목을 다시 만들면 안 된다.**

## 현재 코드 사실 (시작 전 눈으로 재확인 — 이미 있는 것 재구현 금지)

| 기능 | 위치 | 상태 |
|------|------|------|
| payload에 `tools` 포함 (`payload["tools"] = tools`) | `agent_ops/lig_runtime.py` `call_llm` (122~124행 부근) | **이미 구현됨** |
| native `message.tool_calls` 1차 파싱 + 텍스트 복구 fallback (parse_status: ok/repaired/none/failed) | `agent_ops/toolcall_parser.py` `parse_tool_calls` | **이미 구현됨** |
| 멀티턴 tool 루프 (assistant→tool→반복) | `agent_ops/tool_dispatch.py` `run_agent_loop` | **이미 구현됨** |
| REGISTRY→OpenAI tools 스키마 | `agent_ops/tool_dispatch.py` `tool_definitions()` | **이미 구현됨** |
| tool_calls 항목의 `id` + tool 메시지의 `tool_call_id` | 어디에도 없음 | **이번 task** |
| 진단 `tool_call_mode` | 없음 | **이번 task** |

## 먼저 읽기
- `skills/repo-conventions`
- `probe/company_check.py`의 `scn_gateway_agent()` 506~543행 (실증 메시지 형식 — 목표 형태)
- `agent_ops/tool_dispatch.py` `run_agent_loop` 226~257행 (수정 지점)
- `agent_ops/toolcall_parser.py` `_normalize_one` 96~110행 (수정 지점)

## 작업 항목 (순서 고정 — 각 항목의 코드는 그대로 사용)

### 1. `toolcall_parser.py` — normalized call에 `id` 보존

`_normalize_one`에서 id를 캡처한다. **주의: 현재 코드가 `obj = obj["function"]`으로
재할당하므로, id는 그 재할당 이전에 읽어야 한다.**

```python
def _normalize_one(obj: Any) -> Optional[Dict[str, Any]]:
    # (기존 dict 확인 로직 유지)
    raw_id = obj.get("id") if isinstance(obj, dict) else None
    call_id = raw_id.strip() if isinstance(raw_id, str) else ""
    if call_id.upper() == "N/A":
        call_id = ""          # 실측: gateway는 id="N/A"를 반환 — 신뢰 불가
    if isinstance(obj.get("function"), dict):
        obj = obj["function"]
    # (기존 name/args 로직 그대로)
    return {"name": name.strip(), "arguments": args, "id": call_id}
```

텍스트 복구 경로로 만들어진 call은 자연히 `id == ""`가 된다 (원문에 id가 없으므로).
반환 계약: **normalized call = `{"name": str, "arguments": dict, "id": str}`** (id는 "" 가능).

기존 테스트가 `{"name", "arguments"}` 정확 비교로 깨지면, 기대값에 `"id"` 키를 추가하는
갱신만 허용한다 (비교 완화·삭제 금지). 갱신 내역은 보고서 deviation 섹션에 기록.

### 2. `tool_dispatch.py` `run_agent_loop` — 실증 메시지 형식으로

id는 **항상 자체 발급**한다 (파서가 보존한 id도 왕복에는 쓰지 않는다 — 결정성과
"N/A" 비의존을 위해). 239~243행의 assistant 메시지와 254~255행의 tool 메시지를
아래처럼 바꾼다:

```python
        call_ids = ["call_%d_%d" % (turns, i + 1) for i in range(len(calls))]
        messages.append({"role": "assistant", "content": llm.get("content", "") or "",
                         "tool_calls": [{"id": call_ids[i], "type": "function", "function": {
                             "name": c["name"],
                             "arguments": json.dumps(c.get("arguments", {}), ensure_ascii=False),
                         }} for i, c in enumerate(calls)]})
        cutoff = False
        for i, call in enumerate(calls):
            # (repeated_failure / dispatch 로직은 기존 그대로)
            messages.append({"role": "tool", "tool_call_id": call_ids[i],
                             "name": call.get("name", ""),
                             "content": json.dumps(result, ensure_ascii=False)})
```

이 형식(`assistant.tool_calls[].id` ↔ `tool.tool_call_id` 대응)이 회사에서 실증된
scn_gateway_agent의 537~542행 형식과 동일 구조다.

### 3. `lig_runtime.py` `call_llm` — 진단에 `tool_call_mode`

result dict(175~190행 부근)에 필드 1개 추가:

```python
    tool_call_mode = {"ok": "native", "repaired": "text_fallback"}.get(
        parse.get("parse_status", ""), "none")
```

result에 `"tool_call_mode": tool_call_mode,` 추가. runtime-last.json은 result 복사본을
기록하므로 자동 포함된다 (별도 기록 코드 추가 금지).

### 4. `mock_transport.py` — 실측 gateway 형태 재현

`_tool_response`가 실측과 동일한 형태(id="N/A", finish_reason="tool_calls")를 내도록
교체한다. 기존 write→read-back→최종 시나리오 흐름은 그대로 유지:

```python
def _tool_response(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    # 실측 gateway 형태 재현: id는 "N/A" — 제품 코드가 자체 발급해야 함
    return {"choices": [{"finish_reason": "tool_calls", "message": {"content": "", "tool_calls": [
        {"id": "N/A", "type": "function", "function": {"name": name,
                                          "arguments": json.dumps(args, ensure_ascii=False)}}
    ]}}]}
```

이로써 기존 mock 플로우 전체가 "id 자체발급" 경로를 기본으로 검증하게 된다.

### 5. 테스트 확장 (기존 각 파일의 `check` 헬퍼·격리 패턴 그대로 사용)

(a) `tests/test_toolcall_parser.py`에 3 checks 추가:

```python
r = parse_tool_calls({"choices": [{"message": {"content": "", "tool_calls": [
    {"id": "N/A", "type": "function",
     "function": {"name": "read_file", "arguments": "{\"path\": \"a.txt\"}"}}]}}]},
    available_tools=["read_file"])
check("native id N/A -> empty string", r["tool_calls"][0]["id"] == "")
r2 = parse_tool_calls({"choices": [{"message": {"content": "", "tool_calls": [
    {"id": "call_abc", "type": "function",
     "function": {"name": "read_file", "arguments": "{}"}}]}}]})
check("native real id preserved", r2["tool_calls"][0]["id"] == "call_abc")
r3 = parse_tool_calls('{"tool_calls": [{"name": "read_file", "arguments": {"path": "b.txt"}}]}')
check("text-repaired call has empty id",
      bool(r3["tool_calls"]) and r3["tool_calls"][0].get("id", "") == "")
```

(b) `tests/test_tool_dispatch.py`에 메시지 형식 캡처 checks 추가 (기존 tmp 격리 헬퍼 사용):

```python
from agent_ops.mock_transport import make_mock_transport, MOCK_ENV
inner = make_mock_transport()
seen_payloads = []
def capturing(url, payload, headers, timeout):
    seen_payloads.append(payload)
    return inner(url, payload, headers, timeout)
result = run_agent_loop("메모를 작성해줘", tmp_root, env=MOCK_ENV,
                        transport=capturing, diag_dir=tmp_diag)
final_msgs = seen_payloads[-1]["messages"]
assistant_tcs = [tc for m in final_msgs
                 if m.get("role") == "assistant" and m.get("tool_calls")
                 for tc in m["tool_calls"]]
tool_ids = [m.get("tool_call_id") for m in final_msgs if m.get("role") == "tool"]
check("assistant tool_calls carry self-issued id",
      assistant_tcs and all(tc.get("id") and tc["id"] != "N/A" for tc in assistant_tcs))
check("tool msgs tool_call_id matches assistant ids",
      tool_ids == [tc["id"] for tc in assistant_tcs])
```

(c) `tests/test_lig_runtime.py`에 3 checks 추가 (기존 fake transport 헬퍼 재사용):
- native tool_calls 응답 → `r["tool_call_mode"] == "native"`
- content에 JSON 텍스트만 있는 응답 → `"text_fallback"`
- 일반 텍스트 응답 → `"none"`

## 검증 명령

```bat
py -3.11 tests\test_toolcall_parser.py
py -3.11 tests\test_tool_dispatch.py
py -3.11 tests\test_lig_runtime.py
py -3.11 tests\test_agent_e2e.py
py -3.11 tests\test_agent_cli.py
(이후 회귀 전체 — PROTOCOL §2)
```
기대: 각 파일 마지막 줄 "ALL n CHECKS PASSED" (n은 기존보다 증가).

## DoD
- [ ] mock 전체 플로우가 실증 형식(id ↔ tool_call_id 대응)으로 돈다 — 캡처 테스트 증빙
- [ ] id는 항상 자체 발급, 메시지 어디에도 "N/A"가 등장하지 않음 (테스트로 증명)
- [ ] call_llm 결과·runtime-last.json에 tool_call_mode(native|text_fallback|none) 기록
- [ ] 텍스트 복구(fallback) 경로 무손상 — 기존 repaired 테스트 전부 통과
- [ ] 기존 checks 무손상 (id 키 추가로 인한 기대값 갱신만 허용, deviation에 기록)

## 금지
- "이미 구현됨" 표 항목 재구현·구조 변경 금지 — 위 델타만 적용.
- toolcall_parser 텍스트 복구 경로 삭제·약화 금지 (fallback으로 반드시 유지).
- gateway가 주는 id를 메시지 왕복에 사용 금지 (파서가 보존한 id는 진단·테스트용).
- `call_llm`/`run_agent_loop`의 transport 주입 시그니처 변경 금지.
