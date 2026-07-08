# OpenCodeLIG 정합 수리 계획 (2026-07-08)

Fable(낮음) 상세검토 49건(높음 8) 종합 → **땜질이 아니라 하나의 정합적 수리**로 처리하기 위한 실행 계획.
관리(상위모델)는 계획·감독·회귀검증만, 실제 수정은 하위모델(Fable) 에이전트에 지시.

베이스라인: `baseline-20260708-review` (commit b7a94b6, 작업트리 clean).
회귀 게이트(각 워크스트림 착수 전/후 실행):
```
cd workspace
py -3.11 tests\test_tool_dispatch.py
python -m pytest tests\test_work_command.py -q
py -3.11 tests\test_knowledge_routing.py      # 라우팅 골든 42/42 유지 필수
python agent_ops\agentops.py doctor
```
(release/ 요구 테스트 3건 실패·실LLM/Office 스모크 스킵은 정상.)

## 0. 확정된 설계 결정

- **기본 모델: Qwen3.6-27B (think_off) 유지.** opencode.json 변경 없음. 근거: 사용자 체감 + Qwen의 에이전트/도구사용 강점(=문제 B). think_off가 바이브코딩에 유리.
- **think strip은 필수 도입.** think-on 라우트가 API에 존재하므로, strip이 있으면 무거운 추론용으로 think-on을 안전하게 옵션 사용 가능(사고 텍스트 누출 차단). 게이트웨이 URL/키/라우트/모델명 값 자체는 불변.
- **split-brain 유의:** python work 명령 기본 provider는 `lig-coding`(EXAONE). TUI(Qwen)와 다름 → WS-INT에서 단일화 검토(값 불변, 소스만).

### 모델/템플릿 (사용자 제공 모델목록 2026-07-08 반영)

내부망 가용: EXAONE-4.5-33B / Qwen3.6-27B / Gemma 4 31B. 각 `{vibe_coding|default}×{think_on|think_off}` 템플릿.
**tool calling 확인된 것은 3개뿐**: EXAONE vibe_think_off ✅, EXAONE default_think_off ✅, Qwen vibe_think_off ✅. 나머지(think_on·Qwen default·Gemma)는 미확인 → 기본값 부적합(에이전트 루프 tool call 의존).

핵심 가설: 이 비서 작업은 대부분 비(非)코딩(문서·대화·공학Q&A)인데 현재 두 provider 다 `vibe_coding`(코딩최적화) → 산문에서 딱딱/단답 = "똑똑하지 못한 느낌(B)"의 한 원인 가능. `default`(대화용) 템플릿이 비서 느낌에 더 유리할 가능성.

조치(사내망 검증 불가 상태 → 미검증 기본값 변경 금지): opencode.json을 **additive 확장**해 tool-confirmed 3종 + think_on 옵션을 TUI 전환 가능하게 노출. 기본값은 회귀 0을 위해 `Qwen vibe_think_off` 유지.
- `lig-gateway-qwen` = Qwen 코딩 (기본, tool✅)
- `lig-exaone-chat` = EXAONE 대화용 (**A/B 1순위 추천**, 한국어·tool✅)
- `lig-gateway` = EXAONE 코딩 (tool✅)
- `lig-qwen-chat` = Qwen 대화용 (tool 미확인)
- `lig-exaone-think` = EXAONE 추론on (사고 strip됨, tool 미확인)

**사용자 A/B 절차(사내망)**: TUI에서 모델 전환(우상단/모델피커) → `lig-exaone-chat` 먼저 체감 비교 → 제일 나은 걸 알려주면 그걸 `model` 기본값으로 고정 + python side(lig-api.env) 단일화. **think strip(WS-A) 덕에 think_on도 안전하나 tool calling 미확인이라 무거운 추론 단발용으로만.**

## 워크스트림 (파일 소유권 기준 — 에이전트 간 파일 충돌 0)

### WS-A · 지능 하네스: 파서/런타임  [착수됨]
소유 파일: `lig_runtime.py`, `toolcall_parser.py`, `config/lig-api.env.example`, `tests/test_think_strip.py(신규)`
- #1 `strip_reasoning()` 공통 함수 + `_message_content_text`/`parse_tool_calls` 적용, `reasoning_content` 무시, think-on 안전화. 회귀테스트 신규.
- #B `_INTENT_RE`(toolcall_parser.py:26) failed 판정 강화: `"name":` + (`arguments`/`tool_call`/알려진 도구명) 동시 존재 시에만 failed. SIMPLIFY_INSTRUCTION은 require_tool_call=True일 때만.
회귀: test_think_strip, test_tool_dispatch.

### WS-B · 지능 하네스: 도구 스키마/디스패치  (WS-A 이후 — lig_runtime 공유 주의)
소유 파일: `tool_dispatch.py` (단독 소유)
- #6-1 excel_app optional에 `sheet,values,out_path,spec,macro` + action별 필수인자 힌트 description. outlook_app에 count/folder.
- #6-2 `_PARAM_DESCRIPTIONS` 중복 키 action(310/323)·count(303/330) 통합.
- #6-3 동적 도구 확장: 미노출 도구 호출 시 REGISTRY에 있으면 그룹 추가 후 같은 턴 재시도(367 고정 서브셋 완화).
- #6-4 max_turns 소진 시 final_content에 마지막 assistant content/실행요약 채움(624).
- #6-5 tool_loop_cutoff 직전 1회 '인자 바꿔라' system 메시지(655).
- #8-2 시스템 주입 블록 전역 예산(6000자) 우선순위 드랍(540-616).
- #8-3 tool 결과 직렬화 시 긴 텍스트 6000~8000자 절단+표기(663), 원본은 tool_results 유지.
- #10-4 matlab 키워드 `.m ` → 정규식 `\.m(\s|$)`(361).
회귀: test_tool_dispatch, test_knowledge_routing (주입 예산 변경 영향).

### WS-C · 기억 적재/회상: agentops + memory + wiki  (agentops.py 단독 순차)
소유 파일: `agentops.py`, `memory_manager.py`, `wiki_manager.py`
- #4-1 add_activity를 office-doc/report-xlsx/report-html/doc-template/agent(성공)/routine run 성공 경로에 배선(cmd_work:895 패턴).
- #4-2 add_memory_event(81-84) consolidate_quietly 스로틀(10분) 또는 touched_topics 증분 → 적재 확대로 인한 쓰기 증폭 방지.
- #7-1 extract_keywords(149) 한글 조사(을/를/이/가/은/는/에/의/로/와/과/도/만/까지/부터) 제거 어간 병행 추가, recall 점수에 `_expand_query_terms` 별칭 적용.
- #7-2 cmd_work(818) core_memory(5)+recall id중복제거 병합 주입(tool_dispatch:547 패턴 일치).
- #7-3 wiki recall_pages 제외(582)에 `0-위키-안내.md`/`0-대시보드.md`(0- 접두) 또는 AUTO_MARK 기준.
- #C-plugin용 `recall --pinned` 플래그 신설: core_memory(5)+pinned_recall()+최근 activity 5건 포맷 출력.
- (효율 겸)#8-4 add_memory_event supersede 없을 때 jsonl 1행 append, render_memory_views는 memorycheck/auto_maintain로 이동, load_memory mtime 캐시.
회귀: test_work_command + 신규 recall 테스트('엑셀 매크로 규칙 기억해' 저장 후 '엑셀로 정리' 회상).

### WS-D · 기억 배선: TUI 플러그인  (WS-C의 recall --pinned 이후)
소유 파일: `.opencode/plugins/memory-inject.ts(신규)`, `.opencode/commands/start.md`, `.opencode/agents/agent.md`
- #2 memory-inject.ts: 세션 시작/첫 user 훅에서 `python agent_ops/agentops.py recall --pinned` 출력을 system context에 additive push(compaction-handoff.ts의 output.context.push 패턴). 경로 `process.env.AGENTOPS_HOME` 우선.
  - **선행 스파이크:** 패치 opencode.exe가 세션시작 컨텍스트 주입 훅을 지원하는지 확인. 미지원이면 (a) event 훅 최초 message 시 1회 주입 or (b) start.md 필수 단계 폴백.
- #4-3 세션 종료/compaction 훅에서 세션 요약 1건 add_activity 적재(플러그인 통합) + agent.md 종료 체크리스트 'remember 1줄'.
회귀: 새 TUI 세션에서 remember 저장 규칙이 첫 응답에 반영되는지(수동).

### WS-E · 효율/IO 다이어트: knowledge_base  (WS-B와 test_knowledge_routing 공유)
소유 파일: `knowledge_base.py`
- #8-1 _iter_notes 모듈 캐시(경로→mtime,meta,terms), 라우팅은 frontmatter+파일명만, 본문 read는 선택 top-2만. detect_domains가 (path,meta,body) 반환해 이중 read 제거.
- #eff _excerpt out[:max_chars] 마지막 절단 제거(섹션 통째 skip), context_for_prompt 합계 max_chars 초과 시 마지막 chunk 드랍.
- #A typing import에 Any 추가(20).
회귀: test_knowledge_routing 42/42 유지 필수.

### WS-F · 자잘한 버그  [햄스터 착수됨]
소유 파일: `launch/hamster.bat`, `ui/hamster_overlay.py`, `core.py`, `input_ingest.py`, `schedule_store.py`
- #5 햄스터 상태/진단 디렉터리 USERDATA 통일. [착수됨]
- #10-1 core.py file_lock stale 해제 경쟁: unlink 전 내용 재확인 or rename-to-claim(203-213).
- #10-2 core.py .bat 검증 ASCII강제→UTF-8+CRLF 완화(293-298, 한글 .bat 관행 일치).
- #10-3 input_ingest _xlsx_facts try/finally wb.close() 전경로(74-108), CSV 마스킹 순서(266).
- #10-5 schedule_store 시간 '30분/반' 파싱(105-111), id str 정규화(275).
- #10-6 agentops watch --max-age 0 허용(269).
- #10-7 hamster_overlay 트레이 '숨기기' 항목(478-485).
회귀: 각 스크립트식 테스트.

### WS-INT · 통합/경로  [최후, 격리 커밋, HIGH RISK]
소유 파일: `RUN_OPENCODE_LIG.bat`, `.opencode/plugins/compaction-handoff.ts`, `.opencode/commands/*.md`, `opencode.json`
- #9-1 ocd 진입 시 opencode 실행 직전 원래 폴더 복귀(if defined AGENTOPS_PROJECT_DIR cd /d AGENTOPS_OUTPUT_DIR).
- #9-2 commands/*.md `python agent_ops/...` → `%AGENTOPS_HOME%` 절대경로, compaction-handoff.ts 경로 process.env.AGENTOPS_HOME 우선. **9-1과 반드시 한 커밋**(안 그러면 커맨드 전부 깨짐).
- #9-3 opencode.json baseURL/apiKey `{env:...}` 보간 or 런처 재생성(값 불변, 소스 단일화). split-brain 단일화 검토.
- #9-4 bat env 로드 따옴표/공백 정규화(73-75).
검증: TUI에서 커맨드 3개+ 실제 실행, ocd로 프로젝트 폴더 열어 파일트리 확인.

## 실행 순서(파일 충돌 회피)

1. **병렬 A**: WS-A(파서), WS-F 햄스터, WS-E(knowledge_base) — 서로 다른 파일. [A·햄스터 착수됨]
2. **순차 B**: WS-B(tool_dispatch 단독) — WS-A의 lig_runtime 변경 머지 후.
3. **순차 C**: WS-C(agentops/memory/wiki 단독).
4. **D**: WS-D(플러그인) — WS-C의 recall --pinned 완료 후. 스파이크 선행.
5. **F 나머지**: core/input_ingest/schedule (WS-F 햄스터와 다른 파일이면 병렬 가능).
6. **INT 최후**: 단독 브랜치성 격리, TUI 실검증.

각 워크스트림 완료 → 상위모델이 diff 검토 + 회귀 게이트 → 워크스트림별 커밋(정합 단위). 전체 통과 후에만 배포 패키지/오버레이 재생성.
