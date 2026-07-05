# gateway 3차 실측 — /gateway/ 접두 적용 후 (2026-07-03, 사용자 제공, sanitized)

## 결과: **3개 라우트 전부 200** ✅

| 라우트 | 모델 | 결과 |
|--------|------|------|
| lig-coding (`/gateway/EXAONE-4.5-33B-vibe_coding_think_off/v1`) | EXAONE-4.5-33B | 200, "1+1은?" → "2" |
| lig-chat (`/gateway/EXAONE-4.5-33B-default_think_off/v1`) | EXAONE-4.5-33B | 200, 동일 |
| lig-fallback (`/gateway/Qwen3.6-27B-vibe_coding_think_off/v1`) | Qwen3.6-27B | 200, 동일 |

## 상태 갱신 (정직 어휘)

- **company validated (연결·기본 응답 한정)**: 3라우트 도달 + chat completion 정상.
- 여전히 pending: tool-call 실동작(agent loop 실측 — P19/P11), 스트리밍/타임아웃 특성.

## 파서/런타임에 유용한 응답 형식 관찰 (vLLM 계열)

- OpenAI 호환 스키마에 `tool_calls` 필드 존재(null) → **OpenAI function calling 지원
  가능성 높음** — P11/P19에서 tools 파라미터 실측 가치 큼.
- `reasoning_content` 필드 존재(빈 문자열) → think 계열 파서 탑재 서버. think_on 라우트가
  있다면 이 필드로 추론이 분리될 것.
- `id: "N/A"` — 응답 id에 의존하는 로직 금지.
- 확정 사실: 기본 라우트 셋(vibe_coding/default/Qwen 3종 모두)이 실존 — 기본값 유효.
