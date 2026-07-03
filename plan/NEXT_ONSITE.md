# NEXT_ONSITE — 다음 회사 방문 때 할 일 (상시 갱신, Fable 관리)

> 사용자↔집↔회사 파일 왕복 루프가 검증됐다 (2026-07-03: probe 3회 왕복으로 gateway
> 404 원인 확정→해소). 이 문서는 **방문 1회의 가치를 극대화**하기 위해 항상 최신
> "회사에서 할 일" 목록을 유지한다. 완료 항목은 지우고 이력에 한 줄 남긴다.

## ★ 가장 빠른 길: 계측기 하나만 반입

`probe/company_check.py` **파일 하나**를 회사 PC로 가져가 `py -3.11 company_check.py`
실행 → 생기는 `company_check_result.md`/`.json`을 전달하면, 아래 목록의 측정 대부분이
한 번에 끝난다 (gateway function calling / Excel VBProject / MATLAB·Chrome 실동작 /
OpenCode 기동 시간 / 앱·정책 전수). 사용법은 `probe/COMPANY_CHECK.md`.

## 준비물 (집에서) — 전체 재설치까지 할 경우

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

## 회귀 전수 Windows baseline (파일럿 전 1회 — 리뷰가 대체 못 하는 검증)

리뷰(Fable)는 리눅스 환경이라 `test_agent_cli.py`(run-agent.bat)·`test_encoding_paths.py`
(cmd.exe/CRLF/chcp)·`test_probes.py`(%USERPROFILE% 마스킹) 3개를 **독립 재현하지 못한다**
— 지금까지 워커의 Windows 실행 보고 + diff 무접촉으로 갈음해 왔다. P17-04(오프라인
리허설)/P19(파일럿) 전에 **한 번은** Windows에서 전수 1회를 돌려 단일 green baseline을 남긴다:

```bat
cd /d %USERPROFILE%\OpenCodeLIG\workspace
for %f in (tests\test_*.py) do py -3.11 %f
```

각 파일 마지막 줄(“ALL n …” / SKIP)만 모아 `probe/results/`에 커밋하면, 크로스파일
상호작용까지 포함한 독립 baseline이 확보된다.

## 실패해도 가치 있는 것

- 4·5번이 실패하면 그 diagnostics가 바로 P11-02(파서 보강)의 실측 입력이다 —
  실패 로그가 성공만큼 중요하니 그대로 반출.

## 남은 회사 실측 (시나리오 실증으로 대부분 종결 — 이제 사실상 1개)

1. **새 아티팩트 재설치** (PR #8 브랜치 CI): 강화 런처 적용 → TUI 체감 속도 확인 +
   company_check 재실행으로 env 적용(PURE 등 True)과 기동 시간 판정. **이게 마지막 큰 항목.**
2. (P11-A 머지 후) real `work` E2E 1건: `work --task "..." --input 메모.txt --mode real --yes`
   — 시나리오 ①로 회로는 이미 실증됐으므로 제품 경로 확인용.
3. Outlook/AutoCAD 재검은 어댑터(P15-03/P16-02)가 수정 접근법으로 구현된 뒤 company_check
   재실행으로 자동 커버 (별도 준비 불필요).

## 이력

- 2026-07-03: company_check 종합 실측 완료 — gateway native function calling 지원 확정,
  전 앱 COM/MATLAB/Chrome 실동작 성공, Excel 자동주입 가능. 리스크 대부분 해소.
- 2026-07-03: probe env/gateway 3회 왕복 — gateway 3라우트 200, /gateway/ 접두 확정.
