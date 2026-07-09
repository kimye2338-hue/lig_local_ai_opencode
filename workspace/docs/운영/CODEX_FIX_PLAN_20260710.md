# Codex 수정 작업계획 — 2026-07-09 미커밋 변경 검토 결과 (2026-07-10)

Fable(중간) 4영역 상세검토(A 자가개선/기억, B 런처/격리, C 플러그인/게이트, D 패치bat/테스트) 종합.
발견 38건(HIGH 8 · MED 15 · LOW/정보 15). **아래 순서대로, 각 단계 = 검증 후 로컬 커밋 1개.**
전 발견은 파일:라인 근거 실측 확인됨(추측 표기 별도). 수정 전 이 문서 전체를 읽어라.

## 먼저 알아야 할 판정 2가지

1. **실패 테스트는 네 잘못이 아니다(원인 실측 확정)**: `test_final_patch_bat_extracts_and_runs_against_min_install` FAIL은
   에이전트 하니스 셸이 주입하는 `NoDefaultCurrentDirectoryInExePath=1` 때문(cmd가 cwd에서 bat을 못 찾음). 한글 파일명·
   인코딩 무관(ASCII 프로브도 동일 실패, 변수 제거 시 한글 그대로 1 passed 실측). **사내 PC 더블클릭은 영향 없음.**
   → 고칠 것은 bat이 아니라 **테스트**(CF-0).
2. **남은 TUI 지연의 유력 원인은 memory-inject 플러그인이다**: "비블로킹"이라던 setTimeout 안에서 `execFileSync`
   (timeout 10초×러너 2개)가 이벤트 루프를 동기 점유 — 시작 직후 최대 ~20초, idle마다 재발, compaction 시 ~40초(C-1).
   models_fetch off만으로 부족했던 이유가 이것일 가능성이 크다.

---

## CF-0. 즉시: 현 작업 커밋 + 테스트 환경의존 수정  [소유: 전체(커밋만), tests/test_existing_install_hotfix.py]

1. **현재 미커밋 +5,562줄을 논리 단위로 커밋하라**(수정 전 리뷰 가능한 베이스라인 확보, 유실 방지):
   권장 분할 — ①플러그인 4종+테스트 ②런처/launch/ocd ③self_improvement+quality_gate+CLI ④hotfix py+최종_패치파일
   ⑤docs. 커밋 후에 아래 수정을 시작한다(수정 diff가 깨끗해짐).
2. `tests/test_existing_install_hotfix.py:117` 호출을 환경 독립으로:
   - 절대경로 **문자열** 호출: `subprocess.run(f'cmd /c call "{FINAL_BAT}" <nul', shell 아님, 문자열)` — 리스트+내부따옴표는
     list2cmdline이 `\"` 이스케이프해 실패(실측).
   - env 스크럽: `env = {k:v for k,v in os.environ.items() if k.upper() != "NODEFAULTCURRENTDIRECTORYINEXEPATH"}`
     (Windows에서 키가 대문자 저장 — 원 케이스 pop은 안 지워짐, 실측 함정).
검증: 하니스 셸에서 `python -m pytest tests\test_existing_install_hotfix.py -q` 전부 green.

## CF-1. HIGH: 플러그인 성능/안전 (사용자 체감 지연 직결)  [소유: .opencode/plugins/*.ts]

1. **memory-inject 진짜 비동기화** (memory-inject.ts:102-110, 145-149): `execFileSync` →
   `execFile`(비동기) 또는 `spawn(..., {detached, stdio:'ignore'})` + 콜백에서 SESSION_RECALL.md 기록.
   compaction 훅의 2연속 동기 호출도 동일 처리. idle 재트리거(153-155)는 쿨다운(예: 60초) 추가.
2. **session-autosave delta 폭증 중단** (session-autosave.ts:70-105, 176-202): `*.delta` 타입은 파일에 쓰지 말고
   버퍼 누적 → `text.ended`/`step.ended`에서 1회 append. flush 시 log-activity 승격의 execFileSync도 비동기로.
3. **redact 보강** (session-autosave.ts:63-68): `token|secret|credential` 키=값 패턴 추가 + 기동 시 env에서 읽은
   실제 게이트웨이 키 리터럴 마스킹(대화/도구 출력이 위키 sessions에 그대로 감 — 비밀값 유출 방지).
4. **이벤트 로그 상한** (hamster-status.ts:55-64): 신규 타입만 기록(Set dedupe) + 1MB 초과 시 truncate,
   또는 `LIG_DIAG_EVENTS=1` opt-in.
5. compaction 훅 2곳 top-level try/catch (memory-inject.ts:145-149, compaction-handoff.ts:5-28) — 한 줄 방어.
검증: `node --check`(타입 제거 후) 5종 + `pytest tests\test_opencode_lig_plugin_runtime.py -q` + 신규 케이스
(delta가 즉시 append되지 않음, redact 패턴). **실제 지연 해소는 사내망 확인 항목으로 표기.**

## CF-2. HIGH: 햄스터 상태 판정 정확화  [소유: .opencode/plugins/hamster-status.ts]

바이너리 grep 확정(payload/opencode.exe): `session.next.*` 계열·`session.status/idle/error`·
`experimental.session.compacting` **실존**, `task.start/end/ended/done/spawned`·`session.task.*`·`agent_name` **0건**.
1. 존재하지 않는 이벤트명 분기(89-96, 107-111) 제거.
2. `body.includes("subagent")` substring 폴백(97-100) 제거 — text.delta 본문의 단어에도 오탐, "작업 중" 고착 원인.
   subagent 판정이 필요하면 `event.properties.tool === "task"` 같은 **구조적 필드**로만.
3. 남긴 판정 근거(바이너리 grep)를 주석으로. `opencode-event-types.log`로 실세션 이벤트명 수집해 후속 정리.
주의: quality_gate의 `hamster_subagent_status_bridge` 검사가 `task.start` 문자열 존재를 요구해 이 정리를 **막는다** —
CF-5의 계약 단일화와 같은 커밋에서 그 검사를 구조적 기준으로 바꿔라.
검증: plugin_runtime 테스트 갱신 green.

## CF-3. HIGH: self_improvement을 기존 기억 계층으로 통합  [소유: self_improvement.py, tool_dispatch.py, orchestrator.py, agentops.py, memory_manager.py(태그만)]

문제(전부 실측): ①한 실패 = memory 원장 2건 + si 원장 2건, recall --pinned에 같은 교훈 2경로 중복 주입
(tool_dispatch.py:816-833 + agentops.py:1147 `_complete_activity` + :993-1000 주입) ②`_matching_unresolved_error`
(self_improvement.py:204-218)가 status 미갱신+area 단독 매칭 → 무관한 성공이 "해결"로 붙어 허위 lesson,
성공 훅 2곳(tool_dispatch:834+orchestrator:102)이 count≥2 즉시 high 승격 — WS-6 "다른 날 3회" 철학 무력화
③`_rewrite_jsonl`(:81-92, 275-279) 손상 1줄이면 이후 행 전부 소실+무락 경쟁 ④이벤트마다 render_report 전체 재작성.

**방향(권장): 별도 원장 폐기, 기존 계층 흡수** — 검토A의 매핑 그대로:
- `record_error`/`capture_task_result(ok=False)` → 기존 `record_self_error(area, detail, dedupe_day=True)` (dedupe 태그 보유).
- 실패→성공 연계(self_fix) → `add_memory_event("lesson", ..., source="self_fix", tags=[매칭 error의 dedupe 태그])`
  → memory_quality 등급/decay/캡 보호를 공짜로 얻음.
- 반복 승격 → 기존 `auto_maintain.promote_repeated_failures`에 위임(count≥2 즉시승격 삭제).
- 주입 → `core_memory`/`pinned_recall`이 kind=="lesson" AND source=="self_fix" 최근분을 상한 3으로 포함
  (별도 `format_injection_block` 불필요 — 총량/절단 문제(A-7)도 자연 해결).
- on/off → settings 플래그 1개, `_complete_activity`에서 분기. run_id 연결은 lesson body/tags로 표현.
- **si 훅은 `_complete_activity` 한 계층에만** — run_agent_loop 내부(tool_dispatch:816-845)와 orchestrator(:102-131)
  훅 제거(WS-3 단일 후크 원칙 복원).
완전 흡수가 부담이면 최소한: 별도 원장 유지하되 (i)dispatch 레벨 훅 제거 (ii)area 단독 매칭 삭제+resolved 마킹
(iii)`_read_jsonl` 손상라인 skip+재작성 전 id 부분집합 가드+`core.file_lock` (iv)render_report는 CLI/세션종료 시점만.
검증: `test_self_improvement.py` 재작성 green + `test_auto_learning_hooks`(18) `test_memory_quality`(35)
`test_recall_stemming`(9) `test_memory_activity`(7) `test_adapter_tools_maintain`(24) 전부 green +
"실패 1건 → 원장 기록 1건, 주입 1회" 회귀 케이스 신규.

## CF-4. HIGH/MED: 런처 결함 6건  [소유: RUN_OPENCODE_LIG.bat, launch/ocd.bat, launch/_pyw.bat]

1. **[HIGH] 세션/인증 고아화 마이그레이션** (RUN bat:166-181): XDG 교체 직전에 1회 마이그레이션 블록 —
   `opencode_fast_runtime\data`가 비어 있고 `%OPENCODE_USERDATA%\data`가 존재하면 robocopy /E (config/cache 동일).
   없으면 사내 PC 첫 실행에서 세션 이력/auth 소실 체감.
2. **[HIGH] ocd.bat env 누수** (ocd.bat:13-15): `LIG_PROJECT_DIR` set 삭제(ocd.py:66 setdefault로 충분) 또는
   `setlocal EnableExtensions` 추가 — 없으면 같은 CMD에서 두 번째 `ocd`가 이전 프로젝트로 열림. 인접 기존버그
   `%PY_CMD%` 파스타임 확장(:18-21)도 함께(블록 밖으로).
3. 햄스터 폴백 시 `start /D` 고정경로·`LIG_AGENTOPS_HOME` 고정(RUN bat:97,110-122) → HAMSTER_PY가 해석된
   홈 기준으로 분기(미설치/포터블에서 햄스터 미기동+env 오염 방지).
4. `py -3.11` 하드코딩+콘솔창 잔존(:118-122) → `_pyw.bat` 리졸버 경유 + `start /B pythonw`(launch bats 함정규칙 2 준수,
   완전 숨김 복원). RUN bat도 test_launch_bats 검사 대상에 추가 권장.
5. 죽은 config 복사(:83 → 구 `%OPENCODE_USERDATA%\config`) — fast config로 바꾸거나 45행 mkdir와 함께 삭제.
6. `LIG_PROJECT_DIR` denylist 확장(:18-23): 등호 3개 → `%WINDIR%` 접두 일치+드라이브 루트 검사
   (관리자 cmd 기본 C:\Windows에서 시스템 폴더에 .opencode 시드 방지).
참고(LOW·의도 확인): 설치본 우선 정책(:102-103)이 개발리포 실행을 뒤집음 — 최소 경고 로그 1줄.
프록시 전면 해제(:190-198)는 게이트웨이가 프록시 경유면 끊김 — 사내망 스모크 항목으로 표기만.
검증: `py -3.11 tests\test_launch_bats.py`(101+) green, CRLF 유지, pending_check/quality_gate 관련 검사 green.

## CF-5. MED: 진단 계약 단일화  [소유: 신규 agent_ops/release_contracts.py, pending_check.py, quality_gate.py, tests]

- 마커 목록(fast env 12종, 플러그인 5종, 햄스터/autosave 마커)이 pending_check/quality_gate/plugin_runtime 테스트/
  hotfix 4곳에 복제·이미 발산(햄스터 마커 5 vs 8 vs 11) → **`release_contracts.py` 상수 한 곳**으로 추출, 4소비자 import.
- quality_gate 보증 갭: `memory_inject_nonblocking`은 setTimeout 문자열만 봐 실블로킹을 PASS — CF-1 이후 기준을
  "execFileSync가 훅 경로에 없음"으로. `hamster_subagent_status_bridge`는 CF-2와 함께 구조적 기준으로.
  `launcher_ocd_project_dir` 라인 정확일치(:139) → 공백 관용 매칭. report 이중 쓰기(:394-397) 제거,
  테스트는 out=tmp_path(작업트리 오염 방지).
- SESSION_RECALL 경로 규약(추측·검증 필요): agent.md:59 상대경로 vs 플러그인의 LIG_AGENTOPS_HOME 절대경로 —
  cwd가 프로젝트 폴더면 에이전트가 못 찾음. agent.md를 절대경로 기준으로 통일하거나 프로젝트 폴더에도 사본 기록,
  택일 후 테스트로 고정.
검증: pending_check/quality_gate/plugin_runtime 3종 green + drift 재발 방지 테스트(마커 단일소스 import 확인).

## CF-6. MED: 배포 패치 무결성  [소유: patches/existing_install_hotfix_20260709.py, 최종_패치파일.bat, tests]

1. **sync 테스트 추가**: hotfix 내장 블롭 7종(.ts 4, self_improvement, quality_gate, autocad_batch) == 리포 원본
   비교 — 이미 compaction-handoff.ts가 불일치(원본에만 F2 주석) 실측. 이 테스트가 있었으면 즉시 잡혔다.
2. **생성 스크립트 도입**: hotfix py가 문자열 상수 대신 빌드 시 리포 파일을 읽어 임베드 + `최종_패치파일.bat` 재생성을
   스크립트화(수동 재생성 지시 제거).
3. **CR CR LF 교정**: 최종_패치파일.bat 전 라인이 `\r\r\n`(od 실측) — 재생성 시 binary/newline="" 쓰기,
   테스트에 `b"\r\r" not in raw` 추가.
4. 추출 실패 분기에 임시폴더 rmdir 추가, main() 중단 시 "재실행으로 복구(멱등)" 안내 문구.
5. **모든 CF-1~5 반영 후 마지막에 최종_패치파일.bat 재생성**(그 전에 재생성하면 낡은 payload 고착).
검증: `pytest tests\test_existing_install_hotfix.py -q` 전부 green(신규 sync 테스트 포함).

---

## 전체 회귀 게이트 (각 CF 커밋 전 실행)
```cmd
cd workspace
py -3.11 tests\test_tool_dispatch.py           :: 28
py -3.11 tests\test_intelligence_map.py        :: 168+ (self-improve 항목 상태 변경 시 지도 갱신)
py -3.11 tests\test_auto_command.py            :: 27
py -3.11 tests\test_auto_learning_hooks.py     :: 18
py -3.11 tests\test_memory_quality.py          :: 35
py -3.11 tests\test_recall_stemming.py         :: 9
py -3.11 tests\test_launch_bats.py             :: 101+
python -m pytest tests\test_work_command.py tests\test_quality_gate.py tests\test_self_improvement.py tests\test_opencode_lig_plugin_runtime.py tests\test_existing_install_hotfix.py -q
```
깨지면 테스트가 아니라 변경을 고쳐라(단 CF-0의 환경의존, CF-2/5의 낡은 문자열 계약 테스트는 이 계획이 명시한 대로 갱신).

## 불변 규칙 (유지)
- OPENCODE_PURE=1 금지(사용자 지시). 플러그인 유지. opencode.json/게이트웨이 값 불변. USERDATA 삭제 금지.
- .bat CRLF+chcp 65001. command_guard/approval 우회 금지. GitHub push 금지(로컬 커밋만).
- 미검증을 "완료"로 기록 금지 — 사내망 필요 항목은 아래 체크리스트에 남겨라.

## 사내망 확인 체크리스트 (코드로 해결 불가 — 수정 후 사용자 확인)
1. TUI 시작 속도(CF-1 이후 execFileSync 제거 효과) + 햄스터 표시.
2. fast_runtime 마이그레이션 후 기존 세션 이력(/resume)·인증 보존 여부.
3. 프록시 해제(NO_PROXY=*)가 게이트웨이 연결에 영향 없는지 1회 스모크.
4. `opencode-event-types.log`로 실세션 이벤트명 수집 → hamster 판정 최종 정리.
5. session-autosave가 실제 대화를 위키 sessions에 남기는지 + 비밀값 미유출 샘플 점검.
