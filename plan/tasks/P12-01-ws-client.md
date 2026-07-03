# P12-01 — stdlib WebSocket 미니 클라이언트

| 항목 | 값 |
|------|-----|
| 단계 | P12 (MASTER_PLAN §4 P12) |
| 담당 | codex |
| 선행 | 없음 |
| 환경 | ANY |
| 산출 규모 | 코드 ~200줄 + 테스트 ~10 checks |

## 목표
Chrome CDP 제어에 필요한 최소 WebSocket 클라이언트를 **stdlib만으로** 구현한다
(외부 패키지 금지 — 코어 원칙).

## 작업 항목
1. `workspace-template/agent_ops/adapters/ws_min.py`:
   - RFC6455 클라이언트: HTTP Upgrade 핸드셰이크(Sec-WebSocket-Key/Accept 검증),
     텍스트 프레임 송수신, 클라이언트 마스킹, 페이로드 길이 3형식(≤125/126/127),
     ping→pong 자동 응답, close 핸드셰이크, recv 타임아웃(socket.settimeout).
   - 범위 제한: 바이너리/fragmentation/압축 확장 미지원 — 미지원 프레임 수신 시
     명시적 예외 (조용한 오동작 금지). `ws://127.0.0.1` 전용 (원격/wss 미지원 명시).
   - API: `WsClient(url, timeout=10)`, `.send_json(obj)`, `.recv_json(timeout=...)`, `.close()`.
2. `tests/test_ws_min.py`: **stdlib socket으로 미니 WS 서버를 테스트 안에 구현**하여
   루프백 검증 — 핸드셰이크, 에코 왕복(짧은/126+/한글 페이로드), ping/pong, close,
   타임아웃, 잘못된 Accept 거부. 외부 네트워크 불필요.

## 검증 명령
```bat
py -3.11 tests\test_ws_min.py
(회귀 9개 전부)
```

## DoD
- [ ] 루프백 테스트로 3가지 페이로드 길이 + 한글 + ping/pong + close 검증
- [ ] 미지원 기능은 예외로 명시 (조용한 skip 없음)
- [ ] 외부 패키지 0 (import 검사 check 포함)
- [ ] 기존 checks 무손상

## 금지
- websocket-client/websockets 등 외부 패키지 도입 금지.
- 범위 확장(서버 구현, wss, 바이너리) 금지 — CDP에 필요한 최소만.
