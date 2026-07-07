# OpenCodeLIG 운영 RUNBOOK

원칙: **증상 → 파일 → 대응**, 3분 안에 1차 조치한다. 새 진단 체계를 만들지 말고 이미 남는 diagnostics, audit, schedule, results 파일을 먼저 본다. 아래 diagnostics 경로는 기본 사용자 데이터 폴더 `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\` 기준이다.

| 증상 | 먼저 볼 진단 파일 | 확인 명령 | 대응 |
|------|-------------------|-----------|------|
| LLM 무응답/timeout | diagnostics `runtime-last.json`의 `fallback_trigger`/`trail` | `py -3.11 agent_ops\agentops.py doctor` | `lig-api.env` 라우트 3줄(`/gateway/` 접두 — 누락 시 404) 확인 → doctor 재실행 → 필요 시 `launch\probe-gateway.bat` |
| tool-call 반복 실패 | `tool-dispatch-history.jsonl` + `agent-loop-last.json`(outcome=tool_loop_cutoff) | `type "%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\agent-loop-last.json"` | task 문구를 단순화해 재시도, `--mode mock`으로 파이프라인 자체는 정상인지 분리 확인 |
| 콘솔/파일 한글 깨짐 | 진단 파일 없음 — 증상 즉시 식별 | `launch\run-agent.bat --mode mock --task "한글 테스트"` | 반드시 `launch\*.bat` 경유 실행(chcp 65001 + PYTHONUTF8=1 보장). 직접 `py` 실행이 원인 |
| 오픈코드 입력창 한글이 밀림(타자 지연) | 진단 파일 없음 — 어느 터미널에서 열었는지 확인 | `echo %WT_SESSION%` (비어 있으면 구형 콘솔) | 구형 콘솔(conhost)의 IME 조합 지연이 주범. 새 런처([오픈코드] 바로가기)는 Windows Terminal 이 설치돼 있으면 자동으로 그쪽에서 연다. wt 미설치 PC면: 시작메뉴 `Windows Terminal` 설치 요청 또는 콘솔 속성→'레거시 콘솔 사용' 해제 후 재시도. (런처 변경은 회사 PC 실측 대기) |
| 어댑터 행/앱 프로세스 잔류 | `audit.jsonl` 마지막 기록(어느 앱·어느 파일에서 멈췄나) | `py -3.11 agent_ops\agentops.py doctor` | 작업관리자에서 EXCEL.EXE 등 종료 → 원본이 아닌 `사본_*` 파일만 쓰였는지 확인 → 재시도 |
| 일정 파일 손상 | schedule 저장 폴더의 `.bak` | `py -3.11 agent_ops\agentops.py schedule list --when all` | `.bak`을 원본 이름으로 복사해 복구(P14-01 백업 규약) |
| gateway 설정 오류 | `agentops.py doctor` 출력의 gateway/providers 섹션 | `py -3.11 agent_ops\agentops.py doctor` | env 파일 키 이름·라우트 접두 확인, presence flag만 보고 실값은 노출 금지 |
| 디스크 부족 | `results/` 폴더 크기 | `powershell -NoProfile -Command "Get-ChildItem agent_ops\results -Recurse | Measure-Object Length -Sum"` | 오래된 `results/artifacts/<run_id>/` 정리. audit는 자동 회전(`audit_*.jsonl.bak`)되므로 삭제 불필요 |

## 진입점 (이 오프라인 패키지)

- 오픈코드 채팅: `%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat`
- AI비서 번호 메뉴: `%USERPROFILE%\OpenCodeLIG\workspace\launch\menu.bat` (7=상태 진단, 8=지식책)
- 전역 기억(`%USERPROFILE%\OpenCodeLIG_USERDATA\memory`)은 모든 작업이 공유한다.
- 참고: `oc`/`ocd`/`ai` 명령, `%USERPROFILE%\OpenCodeLIG\bin` PATH 등록, 폴더 전용 비서(`.opencodelig\` 프로필)는 이 오프라인 TUI 패키지에는 포함되지 않는다(소스 저장소의 full agent_ops 번들 설치기에서만 제공). 이 패키지에서는 위 두 진입점을 쓴다.

## 운영 위치

- diagnostics: `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\`
- audit: `%USERPROFILE%\OpenCodeLIG_USERDATA\audit\audit.jsonl`
- results: `agent_ops\results\`
- doctor report: `agent_ops\reports\DOCTOR_REPORT.md`

## 기본 순서

1. `py -3.11 agent_ops\agentops.py doctor`
2. 위 표에서 증상에 맞는 진단 파일 확인
3. mock 경로와 real/app 경로를 분리해 재현
4. 원본 파일이 아닌 `사본_*` 또는 새 산출물만 사용됐는지 확인
