# P12-02 — 브라우저 CDP 어댑터 + chrome-debug.bat

| 항목 | 값 |
|------|-----|
| 단계 | P12 (MASTER_PLAN §4 P12) |
| 담당 | codex |
| 선행 | P12-01 |
| 환경 | ANY (실측은 P12-03) |
| 산출 규모 | 코드 ~200줄 + BAT + 테스트(SKIP형) |

## 목표
첫 실행형 어댑터: Chrome DevTools Protocol로 페이지 열기/텍스트 추출/스크린샷.

## 먼저 읽기
- `agent_ops/adapters/__init__.py` (registry 패턴, available 규칙)
- `agent_ops/doctor.py`의 chrome_9222 체크 (재사용)
- MASTER_PLAN §4 P12, §6.3(안전 수칙)

## 작업 항목
1. `agent_ops/adapters/browser_cdp.py`:
   - `execute(action: str, options: dict) -> dict` — action:
     `open_url`(Page.navigate+로드 대기), `get_title`, `extract_text`
     (Runtime.evaluate → document.body.innerText, 최대 길이 옵션),
     `screenshot`(Page.captureScreenshot → RESULTS 아래 png 저장).
   - 연결: `http://127.0.0.1:9222/json`(urllib)으로 탭 목록/신규 탭 →
     webSocketDebuggerUrl로 `ws_min.WsClient` 접속. CDP id 카운터/응답 매칭.
   - 반환: {"ok", "action", "data", "error"} — 예외는 잡아서 ok=False (raise 금지).
   - 9222 미기동 시: ok=False + "chrome-debug.bat을 먼저 실행하세요" 안내.
2. `adapters/__init__.py` browser 항목에 `"execute": browser_cdp.execute` 연결.
   **available은 False 유지** (P12-03 실측 후 전환).
3. `launch/chrome-debug.bat`: 반드시 별도 프로필
   (`--remote-debugging-port=9222 --user-data-dir=%TEMP%\opencodelig_chrome`),
   기존 launch/*.bat 인코딩 규약(PROTOCOL §2) 준수.
4. `tests/test_browser_adapter.py`: 9222 부재 → SKIP+exit 0. 존재 시(개발 환경)
   example.com open→title→extract 검증. 9222 부재 시에도 검증 가능한 checks:
   미기동 안내 메시지, action 라우팅, 잘못된 action 거부.

## 검증 명령
```bat
py -3.11 tests\test_browser_adapter.py
(회귀 9개 전부)
```

## DoD
- [ ] 4개 action 구현 + 미기동/오류 시 안내 반환 (crash 없음)
- [ ] chrome-debug.bat이 별도 user-data-dir 사용
- [ ] available=False 유지 (실측 전)
- [ ] 기존 checks 무손상

## 금지
- 사용자 기본 Chrome 프로필로 디버그 포트 열기 금지.
- 로그인/폼 입력 자동화 구현 금지 (company validation pending 범위).
