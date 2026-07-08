# Codex 인계 문서 — OpenCodeLIG 정합 수리 (2026-07-08)

이 문서 하나로 전체 맥락·경로·남은 일·작업방식·주의점을 파악할 수 있게 자립적으로 썼다.
먼저 이 문서 → 그다음 `docs/운영/REMEDIATION_PLAN_20260708.md`(워크스트림 원본) 순으로 읽어라.

---

## 0. 한 줄 요약 + 지금 상태

Fable 상세검토 49건(높음8)을 "땜질 말고 한 번에 정합적으로" 고치는 중. 전체 10개 우선순위 중
**8개 워크스트림이 커밋 완료(green)**. **WS-D(TUI 기억주입 플러그인)** 는 Codex 로컬 이어작업으로
구현·오프라인 검증 완료했다. 남은 건 **WS-INT(경로·통합·config 단일소스)** 와
**모델 A/B(사용자 사내망 확인)** 다.

- 리포: `C:\Users\김예찬\OneDrive\바탕 화면\LIG_OPENCODE` (Git, 브랜치 `codex/offline-release-hardening-20260708`)
- 베이스라인 태그: `baseline-20260708-review` (commit b7a94b6)
- 그 위 커밋 8개(아래 3절). **작업트리 clean.**
- 전 회귀 게이트 green. 실LLM/Office 스모크·release/ 요구 테스트는 스킵/실패가 정상(코드결함 아님).

---

## 1. 프로젝트가 뭔가 (30초)

사내 **망분리(오프라인) 윈도우 PC용 한국어 AI 업무비서**. 패치된 OpenCode TUI(`opencode.exe`) +
파이썬 런타임(`agent_ops`). 사내 H100 게이트웨이의 로컬 LLM(EXAONE-4.5-33B / Qwen3.6-27B / Gemma4-31B)을
OpenAI 호환으로 쓰고, 실제 업무SW(Excel·HWP·SolidWorks·CAD·MATLAB·Outlook·브라우저)를 자동화하며,
배운 걸 Obsidian 위키 기억으로 남긴다. 자세한 건 리포 루트 `CLAUDE.md`.

---

## 2. 파일 경로 (중요 — 두 환경을 구분하라)

### (A) 개발 리포 (지금 Codex가 작업하는 곳)
```
C:\Users\김예찬\OneDrive\바탕 화면\LIG_OPENCODE\
  workspace\                         ← 프로그램 본체(소스). 대부분 작업은 여기.
    agent_ops\                       파이썬 런타임(두뇌·도구·기억·어댑터)
      agentops.py                    CLI 진입점(work/agent/recall/watch/office-doc…)
      tool_dispatch.py               내부 에이전트 루프(도구 노출·주입·디스패치)
      lig_runtime.py                 LLM 호출·응답 파싱
      toolcall_parser.py             툴콜 복구 파서 (+ strip_reasoning)
      memory_manager.py              기억 원장(memory.jsonl)·recall·core_memory
      wiki_manager.py                Obsidian 위키 consolidate·recall_pages
      knowledge_base.py              전공 레퍼런스 자동주입(라우팅)
      core.py                        atomic write·file_lock·validate
      status_writer.py / lig_providers.py  상태/진단 디렉터리 기본값(USERDATA)
      ui\hamster_overlay.py          데스크톱 상태 펫
      ocd.py                         현재 폴더에서 OpenCode 열기(프로젝트-로컬)
    .opencode\
      agents\agent.md                주 에이전트 지침(레시피 표)
      commands\*.md                  슬래시 커맨드 → agentops 서브커맨드
      plugins\                       command-guard.ts / compaction-handoff.ts / hamster-status.ts
    launch\*.bat                     런처(hamster.bat, wiki.bat, probe-gateway.bat …)
    config\lig-api.env.example       게이트웨이 설정 템플릿(실값 포함)
    opencode.json                    TUI provider/model 설정
    RUN_OPENCODE_LIG.bat             통합 런처
    tests\                           테스트(스크립트식 + 일부 pytest)
    docs\운영\                        REMEDIATION_PLAN_20260708.md, 이 문서
```

### (B) 사내망 설치 PC (사용자가 실제로 쓰는 곳 — Codex는 접근 못 함)
- 설치 루트: `%USERPROFILE%\OpenCodeLIG\workspace\...` (사내PC 프로필명 예: `C:\Users\74358\OpenCodeLIG\...`)
- **USERDATA(불가침)**: `%USERPROFILE%\OpenCodeLIG_USERDATA\` — 기억/위키/상태/시크릿/캐시.
  `state\`, `diagnostics\`, `memory\`(+`wiki\`), `secrets\lig-api.env`, `cache\opencode\bin\`(ripgrep).
- **게이트웨이(사내망에서만 접속됨)**: `http://ais.ligdefenseaerospace.com/ai_infra/llm_api/gateway/<모델-템플릿>/v1`
  → **개발 리포에선 게이트웨이·TUI 실접속 검증 불가.** LLM/TUI가 필요한 검증은 "사내망 필요"로 표시하고
  코드만 작성 + 오프라인 테스트로 최대한 확인하라.

---

## 3. 지금까지 무슨 일이 있었나 (커밋 8개)

베이스라인(b7a94b6) 위로, 파일 소유권 기준 워크스트림별로 각 회귀검증 후 커밋:

| 커밋 | 내용 | 회귀 |
|---|---|---|
| 48c03cc | docs: 수리 계획서 | — |
| 492bbcd | **WS-A** `<think>`/reasoning strip 공통함수 + `_INTENT_RE` 견고화 | think_strip 10, tool_dispatch 28, toolcall 15, lig_runtime 26 |
| 38e5ca6 | **WS-F** 햄스터 상태/진단 디렉터리 USERDATA 통일(펫 항상 idle 버그) | hamster_overlay 16 |
| 32f8895 | **WS-E** knowledge_base 노트 캐시 + 이중read 제거 + 절단개선 | routing 42/42 |
| 8a9a933 | **config** tool-calling 확인 모델/템플릿 TUI 전환 노출(additive) | JSON 유효성 |
| 90ffe6b | **WS-F** 소형버그6(락경쟁 rename-claim·xlsx핸들·CSV마스킹·시각30분·.bat검증완화·트레이숨기기) | schedule 70, input_ingest, work_command 20 |
| ec05f15 | **WS-B** tool_dispatch(스키마노출·동적확장·max_turns빈결과·전역주입예산·툴결과절단) | tool_dispatch 28, routing 42 |
| 7dfea37 | **WS-C** 기억(자동적재 전경로·조사스테밍·core_memory일관·`recall --pinned`·consolidate스로틀) | recall_stemming 9, wiki_manager 34, memory_activity 7 |
| 로컬 후속 | **WS-D** TUI 기억 브리지: `memory-inject.ts` 추가, compaction 기억 주입, `SESSION_RECALL.md` 폴백, `/start`·agent 지침 보강 | memory_inject_plugin 10, recall_stemming 9, command coverage 24, Node 로드 스모크 |

### 검토가 진단한 3대 문제(사용자 표현)와 대응 상태
- **(A) 자잘한 버그**: 크래시급 없음. 체감형(햄스터 상태 불일치=WS-F ✅, 소형버그6=WS-F ✅).
- **(B) 모델이 똑똑하지 못한 느낌**: ① `<think>` 누출 방어(WS-A ✅, 단 게이트웨이 이미 think_off라 방어용) ②
  도구 스키마/디스패치 결함(WS-B ✅) ③ **템플릿(vibe_coding vs 대화용) 문제**는 config로 전환 노출만 함 →
  **모델 A/B는 사용자 사내망 몫**(4절). ④ 주입 과다 다이어트(WS-B 전역예산 + WS-E 캐시 ✅).
- **(C) 장기기억/Obsidian 연계 느낌 없음**: 근본원인 = "TUI에 기억 자동주입·자동적재 배선 부재".
  자동적재 확대·회상품질·`recall --pinned`는 WS-C ✅. TUI 기억 브리지 WS-D도 로컬 구현 ✅.
  단, 실제 OpenCode TUI 훅 효과는 사내망/실바이너리 세션에서 최종 확인 필요.

---

## 4. 사용자가 원하는 것 (반드시 지켜라)

1. **3대 문제(A/B/C)를 정합적으로 해결.** 특히 C의 마지막 조각 WS-D.
2. **"땜질 금지, 한 번에 제대로."** "고쳤다"고 하고 안 되는 일이 잦았다 → **실제로 테스트를 돌려 통과를 확인**하고
   보고하라. 미검증을 "완료"로 말하지 말 것. 확신 없으면 솔직히 표기.
3. **짧은 단위 + 잦은 커밋.** 토큰이 끊겨도 이어갈 수 있게. 워크스트림/서브항목 단위로 green 확인 후 커밋.
4. **토큰 최소화 위임 구조**(상위모델이 관리, 하위모델이 수정)는 Codex 자체 판단. 단 검증은 직접.
5. **사내망 검증 불가(사용자 퇴근).** LLM/TUI 실검증이 필요한 건 코드만 완성 + "사내망 필요"로 표시.
6. **모델 A/B**: opencode.json에 tool-calling 확인된 모델을 전환 노출해둠(아래). 사용자가 사내망에서
   TUI 모델 전환으로 `lig-exaone-chat`(EXAONE 대화용)을 먼저 비교 → 제일 나은 걸 알려주면 기본값 고정.
   **기본값은 지금 Qwen vibe_think_off 유지(회귀0). 미검증 기본값 변경 금지.**

### 내부망 가용 모델(사용자 제공) + tool calling
확인됨(기본값 후보): `EXAONE vibe_think_off`, `EXAONE default_think_off`, `Qwen vibe_think_off`.
미확인(무거운 추론 단발용/실험): 모든 `think_on`, `Qwen default`, `Gemma4-31B`.
→ 하네스가 tool call에 의존하므로 **기본값은 반드시 확인된 3개 중 하나.** think strip(WS-A) 덕에
think_on을 옵션으로 안전 사용 가능하나 tool calling 미확인이라 기본값 부적합.

---

## 5. 남은 일 (우선순위 순)

### WS-D — TUI 기억 자동주입/적재 플러그인 [구현 완료, 사내망 실검증 필요]
목표: 사용자가 실제 쓰는 OpenCode TUI 세션에 기억이 자동으로 돌아오고(회상) 자동으로 쌓이게(적재).
현재 파이썬 내부 루프(tool_dispatch)에는 기계 주입이 있으나 TUI엔 없음. `recall --pinned`는 WS-C에서 준비됨.

- **선행 스파이크(중요):** 패치된 `opencode.exe`가 **세션 시작/메시지 전 컨텍스트 주입 훅**을 지원하는지 확인.
  근거: `.opencode/plugins/compaction-handoff.ts`는 `experimental.session.compacting` 훅에서
  `output.context.push(block)`로 주입을 **실증**하지만 이는 compaction 시점만이다.
  `hamster-status.ts`는 `event`(관찰용)·`tool.execute.before/after`·플러그인 init 시점 코드 실행을 보여준다.
  → **세션 시작 시 컨텍스트 주입이 가능한 훅이 있는지 먼저 확인.** 확실한 건 compaction 훅뿐이니:
    - (a) 지원되면: 세션 시작 훅에서 `python agent_ops/agentops.py recall --pinned` 출력을 system context에 push.
    - (b) 미지원이면 폴백: `event` 훅에서 세션당 최초 user 메시지 1회에 주입 시도, 그마저 안 되면
      `.opencode/commands/start.md`(+`continue.md`)에 `recall --pinned` 실행을 필수 단계로 넣고
      `agent.md` 레시피 표 최상단에 "새 작업 시작 시 먼저 recall" 규칙(모델 의존이라 최후수단).
- 신규 파일: `.opencode/plugins/memory-inject.ts`. 경로는 `process.env.AGENTOPS_HOME` 우선, 없으면 `ctx.directory` 폴백.
- 구현 내용: 플러그인 시작 시 `agent_ops/state/SESSION_RECALL.md` 폴백 파일 생성, `experimental.session.compacting`
  훅에서 `recall --pinned` 결과를 `output.context.push` 또는 `output.prompt`에 추가, compaction 요약이 있으면
  `agentops.py remember ... --title "OpenCode TUI session"` 으로 적재.
- 폴백: `.opencode/commands/start.md`가 `recall --pinned`를 먼저 실행하고, `agent.md`가 새 세션 시작 시
  자동 주입/`SESSION_RECALL.md`/수동 recall 순으로 확인하도록 지시한다.
- 검증: `py -3.11 tests\test_memory_inject_plugin.py`, `py -3.11 tests\test_recall_stemming.py`,
  `py -3.11 tests\test_opencode_command_coverage.py`, Node 동적 import 로 `SESSION_RECALL.md` 생성 확인.
  실제 TUI 세션 시작 훅 지원과 compaction 주입 효과는 사내망/실바이너리에서 확인 필요.
- 참고 패턴 파일: `compaction-handoff.ts`(주입), `hamster-status.ts`(훅 형태·init 실행·env 경로).

### WS-INT — 경로·통합·config 단일소스 [HIGH RISK, 사내망 검증 필요, 격리 커밋]
반드시 **한 커밋으로 묶어야** 하는 결합이 있다(경로 바꾸면 커맨드 상대경로가 깨짐). 아래를 한 세트로:
- **#9-1 ocd 폴더 복원**: `ocd`로 프로젝트 폴더에서 열어도 `RUN_OPENCODE_LIG.bat:90 cd /d "%AGENTOPS_HOME%"`
  때문에 TUI 루트가 설치 workspace가 됨. opencode 실행 직전 `if defined AGENTOPS_PROJECT_DIR cd /d "%AGENTOPS_OUTPUT_DIR%"`로
  원래 폴더 복귀. (`ocd.py`가 `AGENTOPS_PROJECT_DIR`/`AGENTOPS_OUTPUT_DIR`를 이미 넘김.)
- **#9-2 커맨드 상대경로 결합 해소**(9-1과 같은 커밋): `.opencode/commands/*.md`의 `python agent_ops/agentops.py …`를
  `%AGENTOPS_HOME%` 절대경로로, `compaction-handoff.ts:10`의 `join(base, "agent_ops/state/…")`를
  `process.env.AGENTOPS_HOME` 우선+`ctx.directory` 폴백으로. **안 그러면 9-1 적용 순간 커맨드 전부 깨짐.**
- **#9-3 opencode.json env 단일소스**(보안 리뷰 지적 완화 겸): baseURL/apiKey 하드코딩 → `{env:LIG_GATEWAY_BASE_URL}` 류
  `{env:...}` 보간으로. OpenCode 빌드가 보간 미지원이면 런처가 env로 opencode.json을 재생성하는 스텝 추가.
  **LLM 설정 값 자체는 불변(CLAUDE.md 규칙) — 소스만 단일화.** 이게 되면 버전관리 JSON에서 키가 빠져 보안지적도 해소.
- **#9-4 bat env 로드 정규화**: `RUN_OPENCODE_LIG.bat:73-75`가 값 끝 따옴표/공백을 그대로 env에 넣음 → 양끝 따옴표 제거.
- **split-brain 단일화**: python work 기본 provider는 `config/lig-api.env.example`의 `LIG_DEFAULT_PROVIDER=lig-coding`(EXAONE),
  TUI(opencode.json)는 Qwen. 모델 A/B 결론 난 뒤 둘을 같은 모델로 맞춰라(값 불변, 기본선택만).
- **검증:** 사내망에서 TUI 커맨드 3개+ 실행 + `ocd`로 프로젝트 폴더 열어 파일트리 확인. → "사내망 필요" 표시.

### 선택/저순위 (여력 되면)
- **효율 #8-4(보류됨, 데이터지속성 위험)**: `memory_manager.add_memory_event`가 이벤트마다 원장 전체 rewrite +
  뷰 5개 재작성. supersede 없을 때 jsonl 1행 append, `render_memory_views`는 memorycheck/auto_maintain로 이동,
  `load_memory` mtime 캐시. **원장 손상 위험 있으니 tmp 격리 테스트 충분히 + 기존 memory 테스트 전부 green 확인.**
- wiki 주제 노이즈: `extract_keywords` stop목록에 업무일반어(산출물/작성/생성/파일/작업/완료) 추가(wiki_manager.py:184 `_topic_map`).
- `wiki_manager.py:587 recall_pages` 스템 미매칭 시 전체 read → `open(p).read(1600)` 부분 read.
- 선제 브리핑(pull→push): `start.md`에 "오늘 첫 세션이면 briefing 실행해 마감임박/OVERDUE 2~3줄 먼저 보고"(secretary.py 이미 구현, 파일 존재로 하루1회 제어).
- `agent.md:30-33` dir/findstr/type 허용 → **실행 셸(cmd vs POSIX) 먼저 확인** 후 list_dir/search_files 우선으로.
- timeline: `agentops watch --auto-doctor` 옵션(stale 시 doctor 요약까지).

전체 49건 원본과 라인별 근거는 `docs/운영/REMEDIATION_PLAN_20260708.md` 및 Fable 검토 결과 참조.

---

## 6. Codex는 이렇게 작업하라

### 회귀 게이트 (변경 전/후 반드시)
```
cd workspace
py -3.11 tests\test_tool_dispatch.py          # ALL 28 CHECKS PASSED
py -3.11 tests\test_knowledge_routing.py      # 42/42 — 절대 깨지 마라, 깨지면 변경을 고쳐라(테스트 X)
py -3.11 tests\test_recall_stemming.py        # ALL PASS (9 checks)
python -m pytest tests\test_work_command.py -q # 4 passed
python agent_ops\agentops.py doctor
```
관련 파일 바꾸면 그 파일 타깃 테스트도(예: `test_schedule_store.py` 70, `test_wiki_manager.py` 34,
`test_memory_activity.py`, `test_hamster_overlay_state.py` 16, `test_input_ingest.py`).
**스크립트식 테스트는 `py -3.11 tests\<파일>`로 개별 실행, green 기준은 각 파일 마지막 줄.**

### 원칙
- **파일 소유권 분리**로 병렬/순차. 한 파일은 한 작업자만. (agentops.py/tool_dispatch.py/memory_manager.py는 크고 중심 → 단독 소유로.)
- **직접 검증 후 커밋.** 워크스트림/서브항목 단위 커밋. 커밋 메시지 규약: 아래 Co-Authored-By/Session 유지.
- **작업 종료 기록 의무.** 작업 단위가 끝날 때마다 이 문서 또는 별도 운영 로그에 아래 5가지를 남긴다:
  1. 완료한 변경 요약(파일/기능 기준)
  2. 왜 그 방향으로 갔는지(설계 판단과 포기한 대안)
  3. 실행한 검증 명령과 결과
  4. 아직 로컬에서 확인 못 한 것(예: 사내망/TUI/실앱 필요)
  5. 다음 사람이 바로 이어갈 첫 명령 또는 첫 파일
  이 기록은 커밋 전후 어디든 남기되, 최종적으로 로컬 커밋에 포함한다. GitHub push 여부와 무관하게 로컬 이력은 남긴다.
- 확신 낮은 부분은 보고에 **솔직히 표기**.
- 실제 `%USERPROFILE%\OpenCodeLIG_USERDATA\`(기억/위키)는 **절대 쓰거나 지우지 마라.** 테스트는 `AGENTOPS_MEMORY_DIR`/`AGENTOPS_ROOT`를 tmp로 격리.

### 불변 규칙 (CLAUDE.md)
- 게이트웨이 URL/키/라우트/모델명(EXAONE/Qwen/Gemma) 값은 사용자 권한 — 함부로 바꾸지 마라(소스 단일화는 OK, 값 유지).
- **.bat/.bat.txt는 CRLF + `chcp 65001`**(파이썬 호출 시 PYTHONUTF8). LF 금지.
- 오프라인 전제(런타임 네트워크 0). 바이너리·wheel은 `tools/`로 반입.
- 안전 가드(command_guard/command-guard.ts 명시 deny)는 어느 승인정책에서도 유지 — 우회 금지.

---

## 7. 신경 쓸 함정 (실제로 물릴 것들)

1. **인코딩**: PowerShell **5.1** `Get-Content`는 UTF-8을 CP949로 오독 → 한글 파손. UTF-8 파일 읽기/쓰기는
   PS7(`pwsh`) 또는 파이썬으로. 콘솔에 한글이 깨져 보여도 파일 자체는 멀쩡한 경우 많음(바이트로 확인).
2. **opencode.json 파손 = 사내망서 치명적**(원격 복구 어려움). 바꾸면 **반드시 `json.load`로 유효성 + default provider/model resolve 검증.**
   provider block은 additive로 추가하는 게 안전(기존 default 안 건드림).
3. **보안**: opencode.json/lig-api.env에 내부 게이트웨이 키(`ai_infra_llm_api_2024_06`)·http URL이 있다. **공개 저장소 push 금지**
   (예전에 이 이유로 push 차단됨). 사내망 내부용이라 설계상 하드코딩이나, WS-INT #9-3로 env 소스화하면 버전관리에서 빠짐.
4. **스키마 바이트예산 초긴축**: `test_tool_dispatch.py`가 도구 스키마 총 바이트 상한(11059)을 검사. 현재 여유 **8바이트**뿐
   (WS-B에서 설명 압축해 통과). 도구/파라미터 설명을 1개라도 늘리면 즉시 초과 → 늘리려면 다른 설명을 줄여 상쇄하거나 상한 근거 재검토.
5. **플러그인 훅 API 미검증**: 세션 시작 컨텍스트 주입 훅 지원 여부 불명(WS-D 스파이크 대상). compaction 훅만 실증됨.
6. **think_on tool calling 미확인**: 기본값으로 쓰면 에이전트 루프가 깨질 수 있음. 확인된 3종만 기본값.
7. **consolidate 스로틀은 activity 한정**(WS-C): 전 kind 스로틀은 `test_wiki_manager.py`(remember→topic page)를 깼다.
   사용자 remember는 즉시 반영이 스펙. 기억 관련 손대면 이 테스트 확인.
8. **max_turns/동적확장(WS-B)**: 동적 도구 확장은 1회당 max_turns 1턴 소모. `lig_runtime.call_llm`은 미노출 도구를
   `unavailable_tool_repeat`로 자체 재시도 후 `ok=False` 반환(그래도 parsed calls는 남음) — WS-B는 확장검사를 `if not llm["ok"]` **앞**에 뒀다. 이 근처 손대면 주의.
9. **release/ 요구 테스트**(test_ocd_profiles/test_patch_build/test_release_manifest/test_launch_bats)와 실LLM/Office 스모크는
   배포 패키지에 소스가 없어 **실패/스킵이 정상.** green 기준에서 제외.

---

## 8. 시작 체크리스트 (Codex 첫 세션)
1. `git log --oneline -10` 로 위 8커밋 확인, `git status` clean 확인.
2. 6절 회귀 게이트 실행해 baseline green 재확인.
3. WS-D는 완료됨. 다음은 WS-INT를 한 커밋 세트로(9-1~9-4+split-brain) 작성 → 오프라인 가능한 것만 검증 → "사내망 실검증 필요" 표시 → 커밋.
5. 여력 되면 5절 선택/저순위. **#8-4는 데이터 위험 크니 tmp 격리 테스트 충분히.**
6. 사용자에게: 모델 A/B 절차(4절)와 사내망 검증 필요 항목 목록을 정리해 전달.
