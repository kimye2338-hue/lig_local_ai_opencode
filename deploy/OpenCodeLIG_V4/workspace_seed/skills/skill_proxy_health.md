# skill_proxy_health — 로컬 프록시 상태 점검

## 언제
모델 응답이 없거나, 파일이 안 만들어지거나, "upstream" 오류가 보일 때.

## 절차 (가벼운 것부터)
1. 헬스 체크: bash로 `curl -s http://127.0.0.1:8765/health`
   (curl이 없으면 `python -c` 금지 — 대신 DIAG 실행).
   - 기대값: `"proxy": "LIG generic-toolcall-rescue-v2"`.
   - 응답 없음 → 프록시 미기동: `RUN_OPENCODE_LIG.bat`가 자동 기동하므로 재실행 안내.
2. 설정 확인: read 도구로
   `OpenCodeLIG_USERDATA\opencode_config\opencode.proxy.json`의
   baseURL이 `http://127.0.0.1:8765/v1`인지 확인.
   틀리면 `APPLY_OR_REPAIR_OPENCODE_LIG.bat` 실행 안내.
3. 프록시 로그 꼬리 확인: `OpenCodeLIG\logs\lig_toolcall_proxy.log` 마지막 20줄만 read.
   - `upstream error/unreachable` → 사내 게이트웨이 문제 또는 secrets 미설정
     (`SET_LIG_SECRET.bat` 1회 실행).
4. 그래도 불명확하면 skill_diagnostics로 전체 진단.
