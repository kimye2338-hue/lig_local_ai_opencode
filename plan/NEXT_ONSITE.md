# NEXT_ONSITE — 다음 회사 방문 때 할 일 (상시 갱신, Fable 관리)

> 사용자↔집↔회사 파일 왕복 루프가 검증됐다 (2026-07-03: probe 3회 왕복으로 gateway
> 404 원인 확정→해소). 이 문서는 **방문 1회의 가치를 극대화**하기 위해 항상 최신
> "회사에서 할 일" 목록을 유지한다. 완료 항목은 지우고 이력에 한 줄 남긴다.

## 준비물 (집에서)

- 최신 CI 아티팩트 `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE` (**PR #8 브랜치 런**에서
  다운로드 — main 아님!) 또는 변경 파일만 USB 반입.

## 회사에서 실행 (순서대로, 총 ~15분)

1. **새 아티팩트 설치** (installer BAT — 기존 설치는 자동 백업됨)
2. **lig-api.env 확인**: `LIG_ROUTE_*` 3줄이 `/gateway/` 접두 포함인지
   (새 기본값이면 3줄 없어도 됨 — 지난번 추가분과 충돌 없음, 동일 값)
3. **`launch\probe-all.bat`** 실행 → 이번 목적:
   - `openai_tools` 결과 — **gateway가 OpenAI function calling을 지원하는가** (3차
     실측에서 `tool_calls` 필드 확인됨 → 지원 가능성 높음. 확정되면 P11 경로 결정)
   - `text_toolcall.raw_content` — EXAONE의 프롬프트 기반 tool-call 원문 (파서 보강 근거)
   - `opencode.version_cmd_seconds` — **강화된 런처 적용 후 기동 시간** (느림 해결 판정)
4. **real agent 스모크 1건**:
   ```bat
   cd /d %USERPROFILE%\OpenCodeLIG\workspace\launch
   run-agent.bat --mode real --task "메모.txt 파일을 읽고 요약해서 요약.md로 저장해줘"
   ```
   (사전에 workspace에 메모.txt 아무 내용으로 생성. 성공 기준: 요약.md 생성)
5. **work 한 명령 E2E 1건** (비서 파이프라인 real 첫 가동):
   ```bat
   py -3.11 ..\agent_ops\agentops.py work --task "이 파일 요약 보고서 만들어줘" --input 메모.txt --mode real --yes
   ```
6. **반출**: `launch\probe_results\*` + `agent_ops\results\reports\work_*.md` +
   `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\runtime-last.json` (secret-free)
   → repo probe/results/ 커밋 또는 채팅 전달.

## 실패해도 가치 있는 것

- 4·5번이 실패하면 그 diagnostics가 바로 P11-02(파서 보강)의 실측 입력이다 —
  실패 로그가 성공만큼 중요하니 그대로 반출.

## 이력

- 2026-07-03: probe env/gateway 3회 왕복 완료 — gateway 3라우트 200(연결 company
  validated), Excel AccessVBOM=1, accoreconsole 확정. (r1~r3 결과는 probe/results/)
