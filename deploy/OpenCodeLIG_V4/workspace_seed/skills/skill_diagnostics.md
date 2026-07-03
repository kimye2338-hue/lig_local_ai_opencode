# skill_diagnostics — 진단 실행과 GO/NO-GO 해석

## 언제
OpenCode/프록시가 이상하거나, 사용자가 "진단해줘"라고 할 때.

## 절차
1. 실행: `C:\Users\74358\OpenCodeLIG\DIAG_OPENCODE_LIG.bat`
   (자동화에서는 `set LIG_NONINTERACTIVE=1` 후
   `python "%USERPROFILE%\OpenCodeLIG\scripts\lig_diag.py"`).
2. 마지막 [RESULT] 블록만 해석한다:
   - `CORE_OK=True` — 프록시/설정/tool_calls 정상.
   - `FILE_CREATE_OK=True` — 고유 마커 파일이 실제 생성됨 (거짓 통과 불가).
   - `STARTUP mode:pure|normal` — 다음 실행부터 자동 적용되는 시작 모드.
   - `GO` — 정상. `NO-GO` — 아래 3단계.
3. NO-GO면: [RESULT] 블록 + 리포트 파일(`OpenCodeLIG_USERDATA\diagnostics\LIG_DIAG_*.txt`)의
   **마지막 섹션만** 사용자에게 전달하도록 안내한다. 로그 전체를 붙이지 않는다.
4. 최근 결과 요약은 `OpenCodeLIG_USERDATA\diagnostics\LAST_RESULT.json`에 있다.

## 금지
- 리포트/로그 전문을 채팅에 출력.
- rc=0 또는 "파일이 존재함"만으로 성공 판정.
