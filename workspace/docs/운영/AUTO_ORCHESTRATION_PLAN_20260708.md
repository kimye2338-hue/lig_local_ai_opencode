# OpenCodeLIG 자동 운영 루프 개선 계획 (2026-07-08)

목표: 사용자가 기능을 고르지 않아도 자연어로 요청만 하면 내부에서 가장 적절한 경로를 선택하고,
실행 결과를 검증하고, 배운 내용을 기억/위키/지식책에 축적하며, 시간이 지나도 스스로 정리·효율화하는 구조를 만든다.

이 문서는 로컬 작업 기준이다. GitHub push는 별도 지시 전까지 하지 않는다.

구현을 시작하기 전과 각 워크스트림을 끝낸 뒤에는
`workspace/docs/운영/BUILD_PHILOSOPHY_20260708.md`를 읽고, 시작 전/종료 후 체크 질문에 답을 남긴다.
이 철학 문서는 코딩 규칙이 아니라 제품이 가야 할 방향을 잊지 않기 위한 기준이다.

---

## 1. 현재 결론

현재 프로그램은 기능 자체는 많이 갖춰져 있다. 다만 기능들이 다음처럼 분리되어 있어 사용자가 체감하기에는
"알아서 한다"보다 "맞는 명령을 골라야 한다"에 가깝다.

- `agentops.py work`: 입력 → 계획 → 산출물/에이전트 루프 → 보고서 → activity 기억 적재
- `agentops.py agent`: LLM tool-call 루프 → 파일/브라우저/앱 도구 실행 → 실패 패턴 기억
- `capabilities.py`: 자연어 요청을 capability/artifact로 분해
- `tool_dispatch.py`: 실제 도구 노출/실행과 기억·KB·스킬 주입
- `memory_manager.py`/`wiki_manager.py`: 원장 기억 → Obsidian 위키 → recall
- `.opencode/plugins/memory-inject.ts`: TUI 세션 시작/compaction 기억 주입
- `RUN_OPENCODE_LIG.bat`/`opencode.json`: TUI 실행/모델/환경

핵심 결함은 네 가지다.

1. 자연어 요청이 `work`/`agent`/`schedule`/`wiki`/`routine` 중 어디로 가야 하는지 단일 자동 입구가 없다.
2. capability 키워드, tool 노출 키워드, skill 키워드, agent.md 레시피가 흩어져 drift 위험이 있다.
3. 실행 후 검증·기억·위키·지식책 갱신은 일부 경로에만 붙어 있고 전체 성공/실패 후크로 표준화되어 있지 않다.
4. TUI/Python 런타임/ocd/런처의 cwd·환경변수·기본 모델 소스가 갈라져 있다.

---

## 2. 설계 방향

새로운 대원칙은 **자동 운영 루프**다.

```text
사용자 요청
  → auto/do 단일 진입점
  → 입력 파일 감지/요약
  → capability + command-native routing
  → 가장 안전한 실행 경로 선택
  → 산출/도구 실행
  → 검증/보고
  → activity/error/preference 기억 적재
  → wiki/book/maintain 스로틀 갱신
  → 다음 실행에서 recall/KB/skill 자동 주입
```

설계 판단:

- 기존 `work`와 `agent`는 버리지 않는다. 위에 얇은 `auto` 조율 계층을 얹어 하위 경로를 고르게 한다.
- 위험한 앱 실행은 자동화하되 기존 approval/command_guard를 유지한다. "알아서"는 위험 차단 해제가 아니다.
- 모델 판단은 보조로만 쓴다. 오프라인/망분리 안정성을 위해 deterministic router를 기본으로 두고,
  semantic planner는 provider 준비 시 선택적 개선으로 둔다.
- 기억은 많이 쌓되 잡음은 낮은 등급과 중복 억제로 제어한다. 사용자 규칙은 high/user로 보호하고,
  자동 로그는 low/activity 또는 self_observed/error_pattern으로 제한한다.
- 문서/명령/라우터는 실제 코드와 테스트로 동기화한다. 설명서만 바꿔서 "자동"이라고 말하지 않는다.

---

## 2.1 개발 대원칙과 연동 계약

이 계획의 최우선 목표는 기능을 많이 붙이는 것이 아니라 **기능들이 한 방향으로 자라게 만드는 것**이다.
따라서 모든 작업은 아래 계약을 따른다.

1. **단일 입구 원칙**
   - 일반 사용자는 기본 대화 또는 `/auto`만 써도 된다.
   - `/work`, `/agent`, `/recall`, `/routine`, `/schedule` 같은 직접 명령은 고급/진단/우회 경로로 유지한다.
   - 새 기능은 먼저 `auto`에서 접근 가능한지 검토하고, 불가능하면 `intelligence_map.py`에 `advanced` 또는 `pending` 사유를 남긴다.

2. **단일 판단 근거 원칙**
   - 요청 분류의 기준 이름은 capability id로 통일한다.
   - tool group, skill hint, KB hint, artifact type, verification policy는 capability id에서 파생된다.
   - 키워드 라우터는 남기되 capability metadata와 불일치하면 테스트가 실패해야 한다.

3. **Trace가 공개 계약이다**
   - 자동 경로는 모두 `AutoRouteTrace` 형태의 기록을 남긴다.
   - trace에는 request, capability ids, selected path, model/provider, context sources, tools exposed, verification, memory hooks,
     safety decision, fallback reason이 들어간다.
   - 다른 모듈은 내부 구현을 추측하지 않고 trace/metadata를 보고 후속 처리를 한다.

4. **후처리 단일 후크 원칙**
   - 성공/실패/보류/사용자확인 필요 결과는 모두 `_complete_activity()` 같은 공통 후크를 통과한다.
   - 기억, 위키, 지식책, audit, 성장 평가, status writer는 이 후크 뒤에만 붙인다.
   - 개별 명령이 자기 방식으로 기억을 쓰면 중복/누락이 생기므로 테스트로 막는다.

5. **기억 위생 우선 원칙**
   - 장기 기억은 사용자 규칙/업무 선호/반복 검증된 패턴만 승격한다.
   - 단일 실행 로그는 activity에 남기고, 반복된 실패만 error_pattern으로 승격한다.
   - Obsidian manual 노트는 사람이 쓴 원본이므로 자동 원장으로 역주입하지 않는다. recall 대상에만 포함한다.

6. **사용자 선택 최소화 원칙**
   - 애매하지만 되돌릴 수 있는 일은 시스템이 합리적 기본값으로 진행한다.
   - 사용자에게 묻는 경우는 위험 실행, 외부 파괴 변경, 모델/게이트웨이 기본값 변경, 의미가 둘 이상으로 갈리는 업무 목표로 제한한다.
   - 질문이 필요하면 선택지를 줄이고, 질문 자체도 trace에 남겨 다음에는 덜 묻게 만든다.

7. **안전 불변 원칙**
   - approval, command_guard, deny rule, USERDATA 보호는 자동화보다 상위 계층이다.
   - 어떤 WS도 안전 장치를 우회하거나 약화할 수 없다.
   - 자동화 실패 시 fallback은 안전한 plan/report이지 강제 실행이 아니다.

8. **관측 후 최적화 원칙**
   - 성능/토큰/메모리 최적화는 먼저 계측을 만들고, 그 다음 정책을 바꾼다.
   - "더 똑똑해 보이는" 변경이라도 trace와 평가 점수가 없으면 기본 경로로 승격하지 않는다.

---

## 3. "모든 지능을 잇는다"의 정확한 정의

여기서 말하는 "모든 지능"은 단순히 기능 목록을 많이 호출한다는 뜻이 아니다. 사용자가 자연어로 요청했을 때
아래 지능층들이 하나의 경로 안에서 서로 이어지고, 어떤 기능도 방치되지 않으며, 실행 결과가 다음 실행의
맥락으로 돌아오는 상태를 뜻한다.

완료 정의:

- 모든 command/capability/tool/adapter/plugin/knowledge/memory/wiki/maintain 기능은 `auto`, 고급 직접 명령,
  문서화된 보류, 폐기 후보 중 하나로 분류되어야 한다.
- 자동 경로에 포함되는 기능은 route trace에 "왜 선택됐는지", "어떤 모델/컨텍스트/도구/검증/기억 후크를 썼는지"를 남긴다.
- 고급 직접 명령으로만 남기는 기능은 이유가 있어야 한다. 예: 위험 실행, 대용량 배치, 수동 승인 필요, 사내망 실기기 필요.
- 실행 결과는 성공/실패/보류 모두 공통 후크로 들어가고, activity/error_pattern/preference/wiki/book 중 적절한 곳으로 축적된다.
- 안전 장치는 자동화 대상이 아니다. approval, command_guard, deny rule, USERDATA 보호는 어느 경로에서도 유지된다.
- 모델/provider 설정은 단일 소유자를 가져야 하며, 자동 모델 변경은 사용자 확인 전에는 하지 않는다.

---

## 4. 지능층 연결 지도

아래 표가 이번 계획의 기준선이다. 구현은 이 표를 코드/테스트로 고정하는 것부터 시작한다.

| 지능층 | 현재 대표 파일/기능 | 현재 연결 상태 | 계획상 연결 방식 |
| --- | --- | --- | --- |
| 사용자 의도/대화 | `.opencode/agents/agent.md`, `.opencode/commands/*.md`, `RUN_OPENCODE_LIG.bat`, `ocd.py` | 레시피는 있으나 명령 선택을 사용자가 해야 함 | WS-1에서 `/auto`를 기본 입구로 만들고 기존 명령은 고급 직접 실행으로 유지 |
| 의도 분류/라우팅 | `capabilities.py`, `tool_dispatch.py`, `skill_router.py`, agent.md 레시피 | 판단 근거가 여러 곳에 분산 | WS-0에서 지능 지도 생성, WS-2에서 capability 기준 메타데이터로 정렬 |
| 모델/provider | `lig_providers.py`, `lig_runtime.py`, `opencode.json`, `config/lig-api.env.example` | TUI/Python 기본 모델과 설정 소스가 갈라짐 | WS-5에서 경로/설정 소유권 정리. 모델 기본값 변경은 별도 사용자 확인 |
| 도구 실행 | `tool_dispatch.REGISTRY`, `adapters/*`, approval/command_guard | agent 루프에서는 잘 쓰이나 work/schedule/wiki와 통합 약함 | WS-1/2에서 route 결과가 도구 노출을 결정하게 하고 안전 가드는 유지 |
| 컨텍스트 주입 | `memory_manager.py`, `knowledge_base.py`, `api_reference.py`, `design_guidance.py`, `domain_context.py`, `skill_router.py` | 일부 경로에 자동 주입, 근거 trace는 제한적 | WS-2/3에서 선택된 컨텍스트를 route trace와 work report에 기록 |
| 산출물 생성 | `artifact_generators.py`, `artifact_quality.py`, `office_writer.py`, `doc_templates.py`, `html_report.py` | work 중심으로 강함, agent/tool 경로와 자연 연결 부족 | WS-1에서 산출물 요청은 자동으로 artifact 경로를 타고, 필요 시 agent 도구 후속 실행 |
| 데스크톱/앱 자동화 | `browser_cdp.py`, `office_adapter.py`, `hwp_adapter.py`, `solidworks_adapter.py`, `autocad_adapter.py`, `matlab_adapter.py`, `fluent_adapter.py`, `ocr_screen.py`, `desktop_ui.py` | tool agent에서 사용 가능, 사용자 명령 선택 의존 | WS-0에서 adapter별 상태 분류, WS-1/2에서 요청 유형별 자동 노출 |
| 기억/학습 | `memory_manager.py`, `wiki_manager.py`, `wiki_vault.py`, `knowledge_book.py`, `memory-inject.ts`, `compaction-handoff.ts` | work/activity와 TUI 주입은 있으나 일부 중복/누락 | WS-3/4/6에서 공통 학습 후크, manual wiki recall, 중복 억제 |
| 검증/자가치유 | `doctor`, verifier, `auto_maintain.py`, `activity_timeline.py`, `status_writer.py`, `watch`, `secretary` | 기능은 있으나 전체 실행 종료 후 표준화 부족 | WS-3에서 post-run 검증 후크, WS-6에서 반복 실패 승격과 유지보수 계측 |
| 반복/재사용 | routine, schedule, queue/orchestrator, briefing/weekly | 개별 명령으로 존재 | WS-1에서 command-native routing 대상에 포함하고 실행 후 기억 후크 적용 |
| 안전/감사 | `command_guard`, approval 정책, audit, RUNBOOK | 유지 중 | 모든 WS의 불변 조건. 자동화가 안전 차단을 우회하지 않도록 테스트 |
| 패키징/오프라인 | installer, wheelhouse, `tools/`, launch bats, `SHA256SUMS.txt` | 배포 구조 존재 | 이번 자동지능 연결과 직접 충돌 없게 유지. 새 런처/명령 변경은 CRLF/오프라인 테스트 |

---

## 5. 워크스트림

### WS-0. 지능 지도와 고아 기능 방지 테스트

**목표:** "모든 지능을 이었다"는 말을 감으로 하지 않고, 프로그램 안의 지능 요소를 먼저 목록화한 뒤
연결 상태를 테스트로 고정한다.

**파일**
- 생성: `workspace/agent_ops/intelligence_map.py`
- 생성: `workspace/tests/test_intelligence_map.py`
- 생성: `workspace/docs/운영/INTELLIGENCE_COVERAGE_REPORT.md`
- 수정: `workspace/docs/운영/AUTO_ORCHESTRATION_PLAN_20260708.md`

**작업**
0. `BUILD_PHILOSOPHY_20260708.md`의 시작 전 체크를 읽고, 이 작업이 줄이는 사용자 부담과 연결되는 지능층을 기록한다.
1. `intelligence_map.py`에 command/capability/tool/adapter/plugin/knowledge/memory/wiki/maintain 항목을 선언한다.
2. 각 항목은 다음 필드를 가진다.
   - `id`: 안정적인 식별자
   - `kind`: `command`, `capability`, `tool`, `adapter`, `context`, `memory`, `maintenance`, `safety`, `packaging`
   - `owner_files`: 대표 파일 목록
   - `status`: `auto`, `advanced`, `pending`, `deprecated`
   - `route`: 자동 경로에 포함되면 capability/command/tool group 이름
   - `reason`: advanced/pending/deprecated 사유
   - `safety`: approval/guard/readonly/userdata 보호 필요 여부
3. `test_intelligence_map.py`는 다음을 실패 조건으로 둔다.
   - `.opencode/commands/*.md` 중 지도에 없는 명령
   - `tool_dispatch.REGISTRY` 중 지도에 없는 tool
   - `agent_ops/adapters/*adapter*.py` 또는 주요 adapter 파일 중 지도에 없는 adapter
   - `capabilities.py`의 capability id 중 지도에 없는 항목
   - `status`가 비어 있거나 `pending`인데 사유가 없는 항목
4. `INTELLIGENCE_COVERAGE_REPORT.md`는 자동/고급/보류/폐기 목록과 미연결 0개 여부를 사람이 읽기 좋게 남긴다.
5. 이후 모든 WS는 새 기능을 추가하거나 상태를 바꾸면 이 지도를 함께 갱신한다.
6. 작업 종료 후 `BUILD_PHILOSOPHY_20260708.md`의 종료 후 체크를 기록한다.

**검증**
- `py -3.11 tests\test_intelligence_map.py`
- `py -3.11 tests\test_tool_dispatch.py`
- `py -3.11 tests\test_capability_bench.py`

**서브에이전트 배정**
- 구현: `worker`, `gpt-5.4`, 파일 소유 `intelligence_map.py`, `test_intelligence_map.py`
- 검토: `codebase-explorer`, `gpt-5.4-mini`, 실제 파일 목록과 지도 누락 여부만 독립 확인

---

### WS-1. 자동 진입점 `auto` / `do`

**목표:** 사용자가 `/work`, `/agent`, `/schedule`를 구분하지 않아도 요청 하나로 적절한 경로를 탄다.

**파일**
- 수정: `workspace/agent_ops/agentops.py`
- 수정: `workspace/.opencode/commands/work.md`
- 생성: `workspace/.opencode/commands/auto.md` 또는 `do.md`
- 생성/수정: `workspace/tests/test_auto_command.py`

**작업**
0. `BUILD_PHILOSOPHY_20260708.md`의 시작 전 체크를 읽고, 사용자가 더 이상 골라야 하지 않아도 되는 부분을 명시한다.
1. `cmd_auto(args)` 추가.
2. `capabilities.plan_task()` 결과에 따라 실행 경로 선택:
   - `schedule_management` 단독 고신뢰 → `cmd_schedule add` 경로로 위임
   - 산출물 필요 → 기존 `cmd_work` 경로 재사용
   - 파일/브라우저/앱 조작 중심 → `cmd_agent` 경로 재사용
   - 애매하면 안전한 `plan` + 사용자 확인 보고
3. 라우팅 trace를 `diagnostics/auto-route-last.json`에 저장.
4. OpenCode 기본 레시피는 `/auto`를 1순위로 안내하고, 세부 명령은 고급/직접 실행용으로 남긴다.
5. 작업 종료 후 `BUILD_PHILOSOPHY_20260708.md`의 종료 후 체크를 기록한다.

**검증**
- `py -3.11 tests\test_auto_command.py`
- `py -3.11 tests\test_capability_bench.py`
- `python -m pytest tests\test_work_command.py -q`

**서브에이전트 배정**
- 구현: `worker`, `gpt-5.4`, 파일 소유 `agentops.py`, `commands/auto.md`, `test_auto_command.py`
- 검토: `verification-runner`, `gpt-5.4-mini`, 위 테스트와 라우팅 trace 확인

---

### WS-2. 라우팅 단일 근거화와 drift 방지

**목표:** capability/tool/skill/문서 레시피가 서로 다른 판단을 하지 않게 한다.

**파일**
- 수정: `workspace/agent_ops/capabilities.py`
- 수정: `workspace/agent_ops/tool_dispatch.py`
- 수정: `workspace/agent_ops/skill_router.py`
- 생성: `workspace/tests/test_routing_alignment.py`

**작업**
0. `BUILD_PHILOSOPHY_20260708.md`의 시작 전 체크를 읽고, 서로 갈라져 있던 판단 근거를 어디서 하나로 묶을지 기록한다.
1. capability id 기준으로 tool group/skill hint를 연결하는 작은 메타데이터를 추가한다.
2. `tool_dispatch`는 prompt 키워드만 보지 않고, 가능하면 `capability_ids`를 우선 사용한다.
3. `skill_router`도 capability 기반 우선순위를 받도록 옵션을 둔다.
4. 키워드 중복을 당장 완전 제거하지는 말고, 테스트로 drift를 먼저 막는다.
5. 작업 종료 후 `BUILD_PHILOSOPHY_20260708.md`의 종료 후 체크를 기록한다.

**검증**
- `py -3.11 tests\test_routing_alignment.py`
- `py -3.11 tests\test_tool_dispatch.py`
- `py -3.11 tests\test_skill_router.py`
- `py -3.11 tests\test_capability_bench.py`

**서브에이전트 배정**
- 구현: `worker`, `gpt-5.4`, 파일 소유 `capabilities.py`, `tool_dispatch.py`, `skill_router.py`
- 검토: `codebase-explorer`, `gpt-5.4`, 라우팅 drift/스키마 예산 확인

---

### WS-3. 실행 후 자동 검증·기억·위키 표준 후크

**목표:** 성공/실패 결과가 어느 경로에서 나와도 같은 방식으로 검증되고 축적된다.

**파일**
- 수정: `workspace/agent_ops/agentops.py`
- 수정: `workspace/agent_ops/memory_manager.py`
- 수정: `workspace/agent_ops/wiki_manager.py`
- 수정: `workspace/.opencode/plugins/memory-inject.ts`
- 생성: `workspace/tests/test_auto_learning_hooks.py`

**작업**
0. `BUILD_PHILOSOPHY_20260708.md`의 시작 전 체크를 읽고, 결과가 기억/평가/위키/유지보수 중 어디로 돌아가야 하는지 기록한다.
1. `agentops.py`에 `_complete_activity(task, outcome, kind, files, route)` 같은 공통 후크 추가.
2. `work`, `agent`, `report-html`, `report-xlsx`, `office-doc`, `doc-template`, `routine run`, `briefing` 성공 경로가 공통 후크를 사용하게 정리.
3. 실패는 `record_self_error()`로 들어가되, 같은 날/같은 원인 중복 억제.
4. `memory-inject.ts` compaction summary는 `remember`가 아니라 low priority activity 또는 별도 CLI 경로를 사용하도록 낮은 등급화한다. 최소한 hash/day 중복 억제를 넣는다.
5. `recall --pinned`의 최근 activity 개수/길이를 제한해 세션 시작 컨텍스트 오염을 줄인다.
6. 작업 종료 후 `BUILD_PHILOSOPHY_20260708.md`의 종료 후 체크를 기록한다.

**검증**
- `py -3.11 tests\test_auto_learning_hooks.py`
- `py -3.11 tests\test_memory_activity.py`
- `py -3.11 tests\test_recall_guarantee.py`
- `py -3.11 tests\test_memory_inject_plugin.py`
- `py -3.11 tests\test_wiki_manager.py`

**서브에이전트 배정**
- 구현 A: `worker`, `gpt-5.4`, 파일 소유 `agentops.py`, `test_auto_learning_hooks.py`
- 구현 B: `worker`, `gpt-5.4-mini`, 파일 소유 `memory-inject.ts`, `test_memory_inject_plugin.py`
- 검토: `verification-runner`, `gpt-5.4`, memory tmp 격리와 중복 억제 확인

---

### WS-4. Obsidian/manual 노트와 위키 recall 강화

**목표:** 사용자가 Obsidian에서 수동으로 남긴 지식도 자동 회상 대상이 되게 한다.

**파일**
- 수정: `workspace/agent_ops/wiki_manager.py`
- 수정: `workspace/docs/기능/OBSIDIAN_WIKI.md`
- 생성/수정: `workspace/tests/test_wiki_manager.py`

**작업**
0. `BUILD_PHILOSOPHY_20260708.md`의 시작 전 체크를 읽고, 사람이 쓴 노트와 자동 기억의 경계를 기록한다.
1. `wiki/manual/*.md`를 `recall_pages()` 후보에 포함하되, 자동 페이지와 구분되는 source를 표시한다.
2. manual 노트는 원장으로 역동기화하지 않는다. 사람이 쓴 노트는 원본을 보존하고 recall에서만 사용한다.
3. manual/auto 양쪽에서 같은 키워드가 잡히면 manual을 1개 우선 포함한다.
4. 작업 종료 후 `BUILD_PHILOSOPHY_20260708.md`의 종료 후 체크를 기록한다.

**검증**
- `py -3.11 tests\test_wiki_manager.py`
- `py -3.11 tests\test_wiki_vault.py`

**서브에이전트 배정**
- 구현: `worker`, `gpt-5.4-mini`, 파일 소유 `wiki_manager.py`, `OBSIDIAN_WIKI.md`, 관련 테스트
- 검토: `codebase-explorer`, `gpt-5.4-mini`, 자동 페이지 재생성/수동 페이지 보존 확인

---

### WS-5. 실행/설정 통합 WS-INT

**목표:** TUI, Python 런타임, ocd 프로젝트 모드가 같은 환경과 경로를 보게 한다.

**파일**
- 수정: `workspace/RUN_OPENCODE_LIG.bat`
- 수정: `workspace/.opencode/plugins/compaction-handoff.ts`
- 수정: `workspace/.opencode/commands/*.md`
- 수정: `workspace/opencode.json`
- 수정: `workspace/config/lig-api.env.example`
- 수정/생성: `workspace/tests/test_launch_bats.py`, `workspace/tests/test_opencode_command_coverage.py`

**작업**
0. `BUILD_PHILOSOPHY_20260708.md`의 시작 전 체크를 읽고, 오프라인 예측 가능성과 안전하게 멈춰야 하는 조건을 기록한다.
1. `AGENTOPS_HOME`을 모든 명령/플러그인의 기준 경로로 확립한다.
2. `.opencode/commands/*.md`의 `python agent_ops/...` 상대경로를 `%AGENTOPS_HOME%\agent_ops\...` 기준으로 정규화한다.
3. `RUN_OPENCODE_LIG.bat`는 OpenCode 실행 직전 `AGENTOPS_OUTPUT_DIR`가 있으면 그 폴더로 cwd를 복원한다.
4. `.bat` env 로더는 값 양끝 따옴표/공백을 정리한다.
5. `opencode.json` env 단일소스화는 두 단계로 한다.
   - 1단계: 현재 값 유지, 테스트로 JSON 유효성과 provider/model 기본값을 고정
   - 2단계: 사내망에서 OpenCode env 보간 지원 확인 후 적용. 미확인이면 런처가 `opencode.generated.json`을 생성하는 방식으로 우회
6. 모델 기본값 단일화는 사용자 A/B 확인 전에는 변경하지 않는다.
7. 작업 종료 후 `BUILD_PHILOSOPHY_20260708.md`의 종료 후 체크를 기록한다.

**검증**
- `py -3.11 tests\test_launch_bats.py`
- `py -3.11 tests\test_opencode_command_coverage.py`
- `python -m json.tool workspace\opencode.json`
- `python agent_ops\agentops.py doctor`
- `rg "python agent_ops" workspace\.opencode\commands workspace\.opencode\plugins`

**사내망 검증**
- `ocd`로 임의 프로젝트 폴더에서 TUI 열기
- `/doctor`, `/auto`, `/work`, `/recall` 실행
- compaction handoff와 memory inject가 둘 다 동작하는지 확인
- `lig-gateway-qwen`, `lig-exaone-chat`, `lig-gateway` tool calling A/B

**서브에이전트 배정**
- 구현: `worker`, `gpt-5.4`, 파일 소유 `RUN_OPENCODE_LIG.bat`, commands, compaction plugin, launch tests
- 검토: `verification-runner`, `gpt-5.4`, CRLF/JSON/경로 회귀
- 최종 판단: main agent 또는 `gpt-5.5` reviewer, 사내망 미검증 항목 분리

---

### WS-6. 자동 유지보수/효율화

**목표:** 축적이 많아질수록 느려지거나 잡음이 커지지 않게 한다.

**파일**
- 수정: `workspace/agent_ops/auto_maintain.py`
- 수정: `workspace/agent_ops/memory_manager.py`
- 수정: `workspace/agent_ops/knowledge_book.py`
- 수정: `workspace/agent_ops/activity_timeline.py`
- 생성/수정: `workspace/tests/test_adapter_tools_maintain.py`, `workspace/tests/test_memory_activity.py`

**작업**
0. `BUILD_PHILOSOPHY_20260708.md`의 시작 전 체크를 읽고, 유지보수가 기억을 정제하는지 오염시키는지 기준을 기록한다.
1. 유지보수 실행 결과에 consolidate/book/lint 횟수와 skip reason을 기록한다.
2. audit/timeline에서 반복 실패나 긴 stall을 감지해 `error_pattern`으로 승격하는 opt-in 배치를 추가한다.
3. `remember` 1회에서 위키/책 재생성 중복 호출을 줄인다.
4. 위험도가 큰 `memory.jsonl` append 최적화는 마지막 단계로 미룬다. 먼저 계측과 테스트를 만든 뒤 진행한다.
5. 작업 종료 후 `BUILD_PHILOSOPHY_20260708.md`의 종료 후 체크를 기록한다.

**검증**
- `py -3.11 tests\test_adapter_tools_maintain.py`
- `py -3.11 tests\test_memory_activity.py`
- `py -3.11 tests\test_wiki_manager.py`
- tmp USERDATA 격리 테스트

**서브에이전트 배정**
- 구현: `worker`, `gpt-5.4`, 파일 소유 `auto_maintain.py`, `activity_timeline.py`, 관련 테스트
- 검토: `gpt-5.5` 또는 main agent, 데이터 손상 위험 검토

---

### WS-7. 정책 엔진과 사용자 선택 최소화

**목표:** 기능 선택을 사용자에게 떠넘기지 않고, 내부 정책이 안전하고 일관되게 기본 선택을 하게 한다.

**파일**
- 생성: `workspace/agent_ops/auto_policy.py`
- 수정: `workspace/agent_ops/agentops.py`
- 수정: `workspace/agent_ops/capabilities.py`
- 수정: `workspace/agent_ops/intelligence_map.py`
- 생성: `workspace/tests/test_auto_policy.py`
- 생성/수정: `workspace/tests/test_auto_command.py`

**작업**
0. `BUILD_PHILOSOPHY_20260708.md`의 시작 전 체크를 읽고, 사용자에게 묻지 않아야 할 것과 반드시 물어야 할 것을 구분한다.
1. `auto_policy.py`에 `choose_execution_policy(request, capabilities, context, safety)`를 만든다.
2. 정책 결과는 다음 필드를 가진다.
   - `mode`: `execute`, `plan_only`, `ask_user`, `blocked`
   - `path`: `artifact`, `tool_agent`, `command_native`, `memory_wiki`, `routine`, `schedule`
   - `priority`: `speed`, `quality`, `safety`, `learning`
   - `requires_confirmation`: bool
   - `reason`: 사람이 읽을 수 있는 한 문장
   - `fallback`: 실패 시 이동할 안전 경로
3. 기본 정책:
   - 되돌릴 수 있는 산출물 생성/읽기/분석/recall은 `execute`
   - 파일 삭제, 앱에서 저장, 외부 시스템 변경, 모델 기본값 변경은 `ask_user`
   - 앱/도구 준비가 안 된 기능은 `plan_only` 또는 `blocked`
   - 일정/루틴처럼 command-native가 더 안정적인 요청은 해당 명령으로 위임
4. `cmd_auto`는 capability 결과를 바로 실행하지 않고 `auto_policy`를 거쳐 실행한다.
5. 정책 결정은 route trace에 저장하고, 사용자가 선택한 답변도 다음 평가에 쓰도록 기록한다.
6. 작업 종료 후 `BUILD_PHILOSOPHY_20260708.md`의 종료 후 체크를 기록한다.

**연동 주의**
- `auto_policy`는 safety를 우회하지 않는다. safety 결과를 입력받아 더 보수적으로만 바꿀 수 있다.
- 모델/provider 선택은 정책에 기록하되, 기본값 변경은 하지 않는다.
- policy가 `ask_user`를 남발하면 사용자 선택 최소화 원칙 위반으로 본다.

**검증**
- `py -3.11 tests\test_auto_policy.py`
- `py -3.11 tests\test_auto_command.py`
- `py -3.11 tests\test_intelligence_map.py`

**서브에이전트 배정**
- 구현: `worker`, `gpt-5.4`, 파일 소유 `auto_policy.py`, `agentops.py`, `test_auto_policy.py`
- 검토: `gpt-5.5` 또는 main agent, 사용자 선택 전가/안전 우회 여부 검토

---

### WS-8. 자기평가와 성장 루프

**목표:** 시스템이 실행 후 "잘했는지"를 평가하고, 다음 실행에서 더 좋은 선택을 하도록 근거를 축적한다.

**파일**
- 생성: `workspace/agent_ops/evaluation_loop.py`
- 수정: `workspace/agent_ops/agentops.py`
- 수정: `workspace/agent_ops/memory_manager.py`
- 수정: `workspace/agent_ops/auto_maintain.py`
- 생성: `workspace/tests/test_evaluation_loop.py`
- 생성/수정: `workspace/docs/운영/INTELLIGENCE_COVERAGE_REPORT.md`

**작업**
0. `BUILD_PHILOSOPHY_20260708.md`의 시작 전 체크를 읽고, 이번 작업이 무엇을 평가하고 어떻게 성장으로 이어지는지 기록한다.
1. `evaluation_loop.py`에 `score_run(trace, outcome)`을 만든다.
2. 평가 항목:
   - `route_confidence`: 라우팅 확신도
   - `tool_success`: 도구 실행 성공/실패/재시도
   - `artifact_quality`: 산출물 검증 결과
   - `user_friction`: 사용자 질문/확인/수정 요구 횟수
   - `learning_value`: 기억으로 남길 가치
   - `safety_margin`: 안전 차단 또는 보수적 fallback 여부
3. 평가 결과는 `diagnostics/evaluations/*.jsonl` 또는 기존 diagnostics 구조에 누적한다.
4. 반복적으로 좋은 결과를 낸 route는 policy에서 선호도를 높인다.
5. 반복 실패 route는 `error_pattern` 후보로 만들고, 바로 장기 기억으로 승격하지 않는다.
6. 성장 리포트는 주간 단위로 다음을 보여준다.
   - 자동 선택된 기능
   - 사용자에게 물어본 횟수
   - 반복 실패에서 개선된 항목
   - 새로 승격된 기억/선호
   - 아직 보류 중인 기능
7. 작업 종료 후 `BUILD_PHILOSOPHY_20260708.md`의 종료 후 체크를 기록한다.

**연동 주의**
- 평가 점수는 정책의 보조 신호다. 안전 정책을 덮어쓸 수 없다.
- 사용자 피드백이 없는 상태에서 단일 성공만으로 장기 선호를 만들지 않는다.
- 평가 저장은 USERDATA 손상 위험이 없도록 append-only 또는 tmp 후 교체로 한다.

**검증**
- `py -3.11 tests\test_evaluation_loop.py`
- `py -3.11 tests\test_auto_learning_hooks.py`
- `py -3.11 tests\test_memory_activity.py`

**서브에이전트 배정**
- 구현: `worker`, `gpt-5.4`, 파일 소유 `evaluation_loop.py`, 평가 테스트
- 검토: `verification-runner`, `gpt-5.4-mini`, tmp USERDATA 격리와 중복 누적 확인

---

### WS-9. 기억 품질 관리와 장기 지식 승격

**목표:** 기억이 많이 쌓일수록 더 똑똑해지는 구조를 만들되, 잡음과 오래된 정보가 판단을 망치지 않게 한다.

**파일**
- 생성: `workspace/agent_ops/memory_quality.py`
- 수정: `workspace/agent_ops/memory_manager.py`
- 수정: `workspace/agent_ops/wiki_manager.py`
- 수정: `workspace/agent_ops/knowledge_book.py`
- 수정: `workspace/agent_ops/auto_maintain.py`
- 생성: `workspace/tests/test_memory_quality.py`

**작업**
0. `BUILD_PHILOSOPHY_20260708.md`의 시작 전 체크를 읽고, 좋은 기억과 잡음의 경계를 기록한다.
1. 기억 등급을 명확히 분리한다.
   - `user_rule`: 사용자가 명시한 규칙. 가장 높은 우선순위, 자동 삭제 금지
   - `preference`: 반복 확인된 사용자 선호
   - `project_fact`: 프로젝트별 사실
   - `activity`: 실행 로그와 요약
   - `error_pattern`: 반복 실패/주의사항
   - `candidate`: 승격 전 후보
2. `memory_quality.py`에 dedupe/decay/promote 규칙을 둔다.
3. 승격 조건:
   - 같은 패턴이 여러 번 관측되거나
   - 사용자가 명시적으로 확인했거나
   - 평가 루프에서 충분히 높은 learning_value가 반복된 경우
4. 감쇠 조건:
   - 오래된 activity
   - 한 번만 관측된 낮은 가치 기록
   - 최신 규칙과 충돌하는 자동 기록
5. recall은 `user_rule`, `preference`, `project_fact`, `manual wiki`를 우선하고 activity는 제한적으로만 넣는다.
6. Obsidian wiki는 자동 정리 페이지와 manual 페이지를 계속 분리한다.
7. 작업 종료 후 `BUILD_PHILOSOPHY_20260708.md`의 종료 후 체크를 기록한다.

**연동 주의**
- 사용자가 직접 남긴 기억과 manual wiki는 자동 감쇠/삭제하지 않는다.
- 기억 품질 관리는 recall 품질을 높이기 위한 것이며, 원본 로그를 조용히 파괴하지 않는다.
- 품질 점수는 route trace와 evaluation 결과를 참고하지만, 안전 결정을 대체하지 않는다.

**검증**
- `py -3.11 tests\test_memory_quality.py`
- `py -3.11 tests\test_recall_guarantee.py`
- `py -3.11 tests\test_memory_activity.py`
- `py -3.11 tests\test_wiki_manager.py`

**서브에이전트 배정**
- 구현: `worker`, `gpt-5.4`, 파일 소유 `memory_quality.py`, memory/wiki 테스트
- 검토: `gpt-5.5` 또는 main agent, 기억 손상/과잉 승격/수동 노트 보존 검토

---

### WS-10. 전체 지능망 최종 리뷰

**목표:** 구현이 끝난 뒤 "기능 몇 개를 붙였다"가 아니라 전체 지능망이 닫힌 루프인지 검토한다.

**파일**
- 수정: `workspace/docs/운영/INTELLIGENCE_COVERAGE_REPORT.md`
- 수정: `workspace/docs/운영/AUTO_ORCHESTRATION_PLAN_20260708.md`
- 필요 시 수정: 발견된 누락 테스트/문서

**작업**
0. `BUILD_PHILOSOPHY_20260708.md`의 시작 전 체크를 읽고, 최종 검토가 확인해야 할 사용자 부담 감소와 지능 연결 기준을 기록한다.
1. `INTELLIGENCE_COVERAGE_REPORT.md`를 최신 코드 기준으로 갱신한다.
2. `auto` route trace 샘플을 최소 8개 남긴다.
   - 문서 작성
   - 데이터/HTML 리포트
   - 일정/비서 요청
   - Obsidian/wiki/recall 요청
   - 앱/브라우저/파일 조작 요청
   - 공학/전공 KB 질문
   - 반복 루틴 요청
   - 위험하거나 애매해 사용자 확인이 필요한 요청
3. 각 샘플에서 모델/provider, context, tools, policy, verification, evaluation, memory/wiki hook이 기록되는지 확인한다.
4. `gpt-5.5` reviewer 또는 main agent 최종 검토로 다음을 판정한다.
   - 미연결 지능 0개
   - 안전 장치 우회 0개
   - USERDATA 위험 변경 0개
   - GitHub push 없음
   - 사내망 실기기 필요 항목은 별도 체크리스트로 분리
5. 작업 종료 후 `BUILD_PHILOSOPHY_20260708.md`의 종료 후 체크를 기록한다.

**검증**
- `py -3.11 tests\test_intelligence_map.py`
- `py -3.11 tests\test_auto_command.py`
- `py -3.11 tests\test_routing_alignment.py`
- `py -3.11 tests\test_auto_learning_hooks.py`
- `py -3.11 tests\test_auto_policy.py`
- `py -3.11 tests\test_evaluation_loop.py`
- `py -3.11 tests\test_memory_quality.py`
- `py -3.11 tests\test_wiki_manager.py`
- `py -3.11 tests\test_launch_bats.py`
- `python -m pytest tests\test_work_command.py -q`
- `python agent_ops\agentops.py doctor`

---

## 5.1 워크스트림 간 연동 계약

| WS | 입력 | 산출물 | 다음 WS가 의존하는 계약 | 깨지면 안 되는 것 |
| --- | --- | --- | --- | --- |
| WS-0 지능 지도 | 실제 commands/tools/adapters/capabilities 파일 목록 | `intelligence_map.py`, coverage report, orphan test | 모든 기능은 `auto/advanced/pending/deprecated` 중 하나 | 지도에 없는 새 기능 추가 금지 |
| WS-1 자동 진입점 | capability 결과, intelligence map | `cmd_auto`, `/auto`, route trace | 모든 일반 요청은 selected path와 fallback을 가진다 | 기존 직접 명령의 호환성 |
| WS-2 라우팅 정렬 | capability ids, tool registry, skill router | capability metadata, routing alignment test | tool/skill/context 선택은 capability id에서 파생 | 키워드 라우터와 문서 레시피 drift |
| WS-3 공통 후크 | auto/work/agent/command 결과 | `_complete_activity`, learning hook tests | 실행 결과는 outcome 하나로 후처리된다 | 기억 중복, 실패 누락, USERDATA 손상 |
| WS-4 Obsidian recall | wiki auto/manual pages, recall query | manual-aware recall | manual wiki는 recall 대상이지만 원장 역주입 금지 | 사용자가 쓴 Obsidian 노트 |
| WS-5 실행/설정 통합 | launcher/env/TUI/plugin paths | AGENTOPS_HOME 기준 실행 경로 | 모든 명령은 같은 workspace/userdata를 본다 | BAT CRLF, LLM 설정 불변, 오프라인성 |
| WS-6 유지보수 | memory/wiki/evaluation/audit data | maintain metrics, error promotion | 정리/승격/skip reason이 기록된다 | 원본 로그 파괴, 과잉 최적화 |
| WS-7 정책 엔진 | capability, safety, context, evaluation hints | execution policy | 사용자 질문/실행/보류 기준이 일관된다 | safety 우회, 모델 기본값 임의 변경 |
| WS-8 자기평가 | route trace, outcome, verification | evaluation records, growth report | 다음 정책은 평가를 보조 신호로 쓴다 | 단일 성공을 장기 선호로 과잉 승격 |
| WS-9 기억 품질 | memory records, wiki, evaluation | dedupe/decay/promote rules | recall은 정제된 기억 우선순위를 따른다 | user_rule/manual wiki 자동 삭제 |
| WS-10 최종 리뷰 | 모든 테스트와 trace 샘플 | intelligence coverage final report | 제품 완성 판단의 기준 문서 | 미검증 항목을 완료로 표시 |

공통 인터페이스:

- `IntelligenceItem`: 기능 존재와 연결 상태를 나타내는 지도 항목.
- `AutoRouteTrace`: 요청에서 실행 후크까지의 단일 추적 기록.
- `ExecutionPolicy`: 실행/계획/질문/차단 결정을 나타내는 정책 결과.
- `ActivityOutcome`: 성공/실패/보류 결과와 산출 파일, 오류, 검증 결과를 담는 후처리 입력.
- `EvaluationRecord`: 실행 품질, 사용자 마찰, 학습 가치를 담는 자기평가 기록.
- `MemoryQualityDecision`: 기억 유지/승격/감쇠/중복 억제 판단.

이 인터페이스 이름은 계획상 계약명이다. 구현 시 실제 class/dataclass/dict 이름은 코드 스타일에 맞춰도 되지만,
테스트와 문서에는 위 역할이 보존되어야 한다.

---

## 6. 실행 순서

1. Baseline 확인:
   - `git status --short --branch`
   - `cd workspace`
   - `py -3.11 tests\test_tool_dispatch.py`
   - `py -3.11 tests\test_knowledge_routing.py`
   - `py -3.11 tests\test_recall_stemming.py`
   - `python -m pytest tests\test_work_command.py -q`
   - `python agent_ops\agentops.py doctor`

2. WS-0 지능 지도와 고아 기능 방지 테스트 구현. 이 단계가 실패하면 WS-1로 넘어가지 않는다.
3. WS-1 `auto` 단일 진입점 구현.
4. WS-2 라우팅 alignment 테스트와 capability 기반 도구/스킬 연결.
5. WS-3 공통 완료/학습 후크와 compaction 중복 억제.
6. WS-4 Obsidian manual recall 강화.
7. WS-5 WS-INT 경로/설정 통합. 이 단계는 한 커밋으로 묶는다.
8. WS-6 유지보수/효율화.
9. WS-7 정책 엔진과 사용자 선택 최소화.
10. WS-8 자기평가와 성장 루프.
11. WS-9 기억 품질 관리와 장기 지식 승격.
12. WS-10 전체 지능망 최종 리뷰.
13. 작업 종료 기록 업데이트 + 로컬 커밋. GitHub push는 사용자 지시 전까지 금지.

---

## 7. 서브에이전트 운용 원칙

- main agent가 설계, 파일 소유권, 통합, 최종 판단을 맡는다.
- 구현 작업은 파일 소유권이 겹치지 않을 때만 병렬화한다.
- 단순 테스트/문서/단일 파일 작업은 `gpt-5.4-mini`.
- 다중 파일 통합 구현은 `gpt-5.4`.
- 전체 설계 검토, 데이터 손상 가능성, 최종 브랜치 리뷰는 `gpt-5.5`.
- 각 서브에이전트는 GitHub push 금지, USERDATA 삭제 금지, 다른 작업자 변경 되돌리기 금지.
- 각 작업은 완료 후 다음을 남긴다:
  - `BUILD_PHILOSOPHY_20260708.md` 시작 전/종료 후 체크 답변
  - 변경 요약
  - 방향성/설계 판단
  - 검증 명령과 결과
  - 미검증 항목
  - 다음 작업자가 볼 첫 파일/명령

---

## 8. 완료 기준

사용자 관점 완료 기준:

- `test_intelligence_map.py` 기준 미분류/고아 지능 요소가 0개다.
- 사용자는 `/auto <요청>` 또는 기본 에이전트 대화만으로 대부분의 업무를 시작할 수 있다.
- 내부는 요청을 command-native, artifact, tool-agent, schedule, wiki/memory, routine 경로 중 하나로 자동 선택한다.
- 선택 전에 `ExecutionPolicy`가 실행/계획/질문/차단을 결정하고, 사용자 질문은 위험하거나 의미가 갈리는 경우로 제한된다.
- 모든 실행은 route trace와 work report를 남긴다. trace에는 선택된 capability, command/tool 경로, model/provider,
  context source, policy, verification, evaluation, memory/wiki hook이 포함된다.
- 성공은 activity/lesson으로, 실패 반복은 error_pattern으로 자동 축적된다.
- 실행 품질은 evaluation record로 남고, 반복적으로 좋은 선택만 다음 정책의 선호 신호가 된다.
- 장기 기억은 품질 관리 규칙으로 승격/감쇠/중복 억제되고, user_rule과 manual wiki는 보호된다.
- Obsidian 자동 위키와 manual 노트가 다음 작업 recall에 반영된다.
- 런처/ocd/TUI/Python이 같은 경로와 설정을 본다.
- 위험 실행은 여전히 approval/command_guard에 걸린다.
- 사내망에서만 가능한 항목은 명확한 체크리스트로 분리되어 있다.

---

## 9. 이번 계획 작업 기록

- 완료한 변경 요약: 세 개의 탐색 서브에이전트로 라우팅/기억/런처 통합을 읽기 전용 감사했고, 그 결과를 통합해 이 계획 문서를 작성했다.
- 방향성: 기존 기능을 새로 대체하지 않고 `auto` 조율 계층과 공통 후크로 엮는다. 기능 목록을 늘리는 대신 기본 흐름으로 만든다.
- 검증: 이 단계는 계획 수립이라 코드 테스트는 실행하지 않았다. 탐색 에이전트들은 파일 수정과 GitHub push를 하지 않았다.
- 미검증: 실제 TUI env 보간, ocd 실행, 모델 A/B, 사내 게이트웨이 tool calling은 사내망 필요.
- 보강 기록: 사용자 지적에 따라 기존 계획을 "자동 루프" 수준에서 "모든 지능층 연결" 수준으로 강화했다. WS-0 지능 지도,
  고아 기능 방지 테스트, 지능층 연결 지도, WS-7 전체 지능망 최종 리뷰를 추가했다.
- 추가 보강 기록: 완성 제품 수준으로 가기 위해 개발 대원칙, 워크스트림 간 연동 계약, 정책 엔진, 자기평가 루프,
  기억 품질 관리, 사용자 선택 최소화 기준을 추가했다. 최종 리뷰는 WS-10으로 이동했다.
- 다음 첫 작업: 바로 `cmd_auto` 구현으로 들어가지 말고 `workspace/agent_ops/intelligence_map.py`와
  `workspace/tests/test_intelligence_map.py`를 먼저 작성해 전체 지능 목록을 고정한다.
- WS-0 완료 기록: `workspace/agent_ops/intelligence_map.py`, `workspace/tests/test_intelligence_map.py`,
  `workspace/docs/운영/INTELLIGENCE_COVERAGE_REPORT.md`를 추가했다. 140개 지능 항목을 분류했고
  `test_intelligence_map`, `test_tool_dispatch`, `test_capability_bench`, `test_opencode_command_coverage`가 통과했다.
  다음 작업은 WS-1 `/auto` 단일 진입점이다.
- WS-1 완료 기록: `workspace/agent_ops/agentops.py`에 `auto` CLI와 `_auto_command_hint`/`cmd_auto`를 추가하고,
  `workspace/.opencode/commands/auto.md`를 새로 만들었다. 자연어 요청은 먼저 `capabilities.plan_task`를 통과한 뒤
  `command_native`, `artifact`, `tool_agent`, `memory_wiki`, `plan_only` 중 하나로 위임된다.
  `diagnostics/auto-route-last.json`에는 selected path, command, capability, artifact, provider 불변 메모,
  context source, verification, memory hook 예정, safety/fallback이 남는다.
  파일 읽기류 요청이 "메모" 때문에 문서 산출물로 과대 라우팅되지 않도록 `file_ops`가 최상위일 때 tool-agent를 우선한다.
  `test_auto_command`, `test_intelligence_map`, `test_opencode_command_coverage`, `test_tool_dispatch`,
  `test_capability_bench`, `test_work_command`가 통과했다.
  다음 작업은 WS-2 capability metadata와 tool/skill/context alignment다.
- WS-2 완료 기록: `workspace/agent_ops/capabilities.py`에 `CAPABILITY_ROUTE_HINTS`와
  `route_hints_for_capabilities()`를 추가해 capability id가 tool/skill/context 선택의 공통 근거가 되게 했다.
  `tool_dispatch.tool_definitions(..., capability_ids=...)`는 capability 기반 도구를 먼저 열고 기존 키워드 그룹은 보조로 유지한다.
  `skill_router.detect_skill/context_for_prompt(..., capability_ids=...)`도 capability 기반 절차 스킬을 우선한다.
  `/auto` trace에는 `route_hints`가 추가되어 tools, skill_sections, context_sources가 남는다.
  `test_routing_alignment`, `test_auto_command`, `test_tool_dispatch`, `test_skill_router`, `test_intelligence_map`,
  `test_capability_bench`, `test_work_command`가 통과했다.
  다음 작업은 WS-3 공통 실행 완료/학습 후크다.
- WS-3 완료 기록(2026-07-08, 커밋 854505f + c79ae88):
  - 변경 요약: `agentops.py`에 공통 완료 후크 `_complete_activity(task, outcome, *, ok, kind, files, route, error_detail)`를
    추가하고 `_log_activity`를 그 래퍼로 격상했다. 성공 경로 7곳(work/agent/report-html/xlsx/office-doc/doc-template/routine)은
    무변경으로 새 후크를 탄다(이중적재 없음). 실패는 `record_self_error`가 당일+동일원인(area|detail sha1) 중복억제하도록
    확장했고, 해시 태그 없는 legacy 행은 종전 규칙(제목+날짜)으로 보수 판정해 기존 호출처 동작을 넓히지 않는다.
    `cmd_auto`는 위임 경로별로 이중적재를 회피하며(work/agent는 하위 명령이 적재, command_native/memory_wiki/plan_only만 자체 적재)
    `memory_hooks` trace를 실값으로 남긴다. `recall --pinned`는 activity 출력만 200자로 절단(원장 불변).
    `memory-inject.ts`의 compaction 요약은 high-priority `remember` → low-priority `log-activity`(신규 CLI, 고정 title로 일 중복억제)로
    낮춰 장기기억 오염을 제거했다. 신규 `log-activity`는 intelligence_map에 advanced로 등록.
  - 철학 종료 체크: (줄어든 사용자 선택) 어느 경로로 실행하든 결과가 같은 방식으로 기억/audit에 축적돼 "이건 기억되나"를
    사용자가 신경쓸 필요가 없다. (새로 연결된 지능) 실행 결과 → activity/error_pattern 단일 후크 → recall 재주입.
    (남긴 trace) auto-route-last.json의 memory_hooks 실값, error_pattern dedupe 태그. (안전) USERDATA는 add_activity/
    record_self_error 경유만, 적재 실패가 본 작업을 막지 않음, 승인/가드 무변경. (미검증) memory-inject.ts는 실 TUI 실행이
    사내망 필요 — 오프라인에선 node --check 구문검증 + log-activity CLI 동작만 확인.
  - 검증: `test_auto_learning_hooks`(18), `test_memory_inject_plugin`(23), `test_memory_activity`(7), `test_recall_guarantee`(7),
    `test_recall_stemming`(9), `test_auto_command`(18), `test_intelligence_map`(164), `test_tool_dispatch`(28),
    `test_wiki_manager`(34), `test_opencode_command_coverage`(25), `pytest test_work_command`(4) 통과.
  - 미검증/사내망 필요: 실 TUI compaction 훅에서 log-activity 적재·중복억제 체감, recall --pinned 주입 효과.
  - 다음 작업: WS-4 Obsidian/manual 노트 recall 강화(`wiki_manager.recall_pages`에 manual 노트 포함, 원장 역주입 금지).
    첫 파일: `workspace/agent_ops/wiki_manager.py`, `workspace/tests/test_wiki_manager.py`.
- WS-4 완료 기록(2026-07-08, 커밋 70e5e95):
  - 변경 요약: `recall_pages`가 auto 주제페이지(WIKI_DIR 루트)뿐 아니라 사람이 쓴 `wiki/manual/*.md`도 스캔·점수화하고
    반환 dict에 `source`(auto/manual)를 additive로 추가했다(기존 topic/excerpt 키 유지 → 호출처 tool_dispatch 무변경).
    auto·manual 동시 매칭 시 manual을 최소 1개 우선 포함하고, frontmatter 없는 manual 노트도 본문이 보존되게 조건부 파싱으로
    바꿨다. recall_pages는 읽기 전용 — manual 원본을 역주입/수정/삭제하지 않는다(테스트로 내용 해시 불변 고정).
    tool_dispatch의 recall_pages 호출을 limit=1→2로 올려 manual이 rich한 auto 페이지를 밀어내지 않고 함께 주입되게 했다
    (총량은 WS-8 전역 주입예산 6000자로 보호).
  - 철학 종료 체크: (줄어든 사용자 선택) Obsidian에 손으로 적은 지식이 다음 작업에서 자동 회상돼 "이거 참고해"라고
    말할 필요가 없다. (새로 연결된 지능) manual 위키 ↔ recall. (남긴 trace) 반환 항목의 source 구분. (안전) 사람이 쓴
    원본 불변·역주입 금지를 테스트로 고정, USERDATA 미접촉. (미검증) 실제 사용자 vault의 manual 노트 품질·양은 사내망 실사용에서 관측.
  - 검증: `test_wiki_manager`(41, was 34), `test_wiki_vault`, `test_recall_guarantee`(7), `test_recall_stemming`(9),
    `test_tool_dispatch`(28), `test_knowledge_routing`(42) 통과.
  - 미검증/사내망 필요: 실 vault manual 노트 recall 체감, manual/auto 혼합 주입의 프롬프트 효과.
  - 다음 작업: WS-5(구 WS-INT) 실행/설정 통합 — AGENTOPS_HOME 기준 경로 통일, 커맨드 상대경로 정규화, ocd 폴더 복원,
    opencode.json env 단일소스(1단계 JSON 유효성 고정), bat env 따옴표 정리. **한 커밋으로 묶고, 모델 기본값·env 보간 2단계는
    사내망 검증 필요**. 첫 파일: `workspace/RUN_OPENCODE_LIG.bat`, `workspace/.opencode/commands/*.md`,
    `workspace/.opencode/plugins/compaction-handoff.ts`, `workspace/tests/test_launch_bats.py`, `test_opencode_command_coverage.py`.
- WS-5 부분완료 + 사내망-gated 기록(2026-07-08, 커밋 대기):
  - **판단(안전 우선)**: WS-5의 핵심(48개 커맨드 .md의 `python agent_ops/…` 상대경로 정규화 + ocd cwd 복원)은
    **패치 opencode.exe 의 bash 도구 셸이 cmd.exe 인지 POSIX sh 인지 미확인**이라 블라인드로 하면 안 된다.
    셸이 POSIX면 `%AGENTOPS_HOME%`가 리터럴 쓰레기가 되고(`$AGENTOPS_HOME`이 맞음), 반대면 그 역. 잘못 치환하면
    48개 커맨드가 사내망에서 전부 깨지고 원격 복구가 불가하다. cwd 복원과 커맨드 치환은 결합돼 있어(한쪽만 하면 깨짐)
    한 커밋으로 묶어야 하므로 **셸 확인 전에는 착수 금지**. 현재 런처는 사내망에서 정상 작동 중이므로 건드리지 않는다.
  - **오프라인에서 완료한 것(무위험)**: `workspace/tests/test_opencode_config.py` 신규 — opencode.json 1단계 무결성 고정
    (JSON 유효성, 기본 model이 정의된 provider/model로 resolve, 모든 provider의 baseURL/apiKey/models, baseURL이 사내
    게이트웨이 형식, **기본 라우트 think_off = tool-calling 안전**). 27 checks PASS. 이로써 모델 A/B로 기본값을 바꾸더라도
    think_off 불변식이 회귀로 지켜진다. (opencode.json 자체는 커밋 8a9a933에서 tool-confirmed 모델 additive 노출 완료.)
  - **사내망 실행 절차(다음 작업자/사용자)**:
    1. 셸 확인: TUI 에서 `echo %AGENTOPS_HOME%`(cmd면 경로 출력, POSIX면 리터럴) 또는 `echo $AGENTOPS_HOME` 로 판별.
    2. 셸에 맞는 절대경로 토큰 결정(cmd=`%AGENTOPS_HOME%\agent_ops\agentops.py`, POSIX=`"$AGENTOPS_HOME/agent_ops/agentops.py"`).
    3. `.opencode/commands/*.md`(48파일, 92참조)를 그 토큰으로 일괄 치환 + `compaction-handoff.ts:10`을 `process.env.AGENTOPS_HOME`
       우선으로 + `RUN_OPENCODE_LIG.bat`에 opencode 실행 직전 `if defined AGENTOPS_PROJECT_DIR cd /d "%AGENTOPS_OUTPUT_DIR%"` 추가
       — **반드시 한 커밋**. 그 후 TUI 에서 커맨드 3개+ 실제 실행 + `ocd`로 프로젝트 폴더 열어 파일트리 확인.
    4. `RUN_OPENCODE_LIG.bat:73-75` env 로더 값 양끝 따옴표 정리(#9-4)는 위와 같은 커밋에서, 사내망 게이트웨이 연결 재확인 후.
    5. opencode.json env 보간(2단계): OpenCode 빌드가 `{env:…}` 보간을 지원하는지 확인 후 적용, 미지원이면 런처가
       `opencode.generated.json` 생성 방식. 모델 기본값 단일화(python `LIG_DEFAULT_PROVIDER` ↔ TUI)는 **사용자 A/B 확정 후**.
  - 철학 종료 체크: (안전) 검증 불가한 변경으로 작동 중인 런처를 깨지 않았다 — "오프라인=예측가능성" 원칙. (남긴 trace)
    config 불변식을 테스트로 고정, 사내망 절차를 문서로 남겨 다음 작업자가 셸 확인부터 이어받는다. (미검증) 커맨드 경로/ocd/
    env 보간/모델 기본값 = 전부 사내망 필요.
  - 다음 작업: WS-6 자동 유지보수/효율화(오프라인 가능). 첫 파일: `workspace/agent_ops/auto_maintain.py`,
    `workspace/agent_ops/activity_timeline.py`, `workspace/tests/test_adapter_tools_maintain.py`.
- WS-6 완료 기록(2026-07-08, 커밋 6dcc314):
  - 변경 요약: `auto_maintain.promote_repeated_failures(min_count=3)` 신규 — error_pattern을 dedupe 해시(없으면 제목)로
    묶어 **서로 다른 날 3회 이상** 관측된 그룹만 priority high + "반복확인됨" 태그로 승격(태그/우선순위만, 삭제·병합·status
    변경 없음, source=user 제외, 멱등). `activity_timeline.recent_stalls()` 순수조회 계측 추가. `maybe_maintain` summary에
    promoted/stalls 키 + book 신선도 skip 사유. 기존 스로틀/마커 구조·WS-C의 activity consolidate 스로틀은 불변. **위험한
    memory.jsonl append 최적화는 계획대로 미룸**(계측 먼저).
  - 철학 종료 체크: (관측 후 최적화) 승격/stall을 먼저 계측·기록만 하고 자동 개입은 하지 않는다. (기억 정제) 반복 확인된
    실패만 승격해 recall 우선순위를 올리되 잡음(1~2회 관측)은 승격 안 함. (안전) 원본 로그 비파괴를 테스트(개수 불변)로 고정,
    user_rule/preference 미대상, USERDATA 미접촉. (남긴 trace) maybe_maintain summary에 promoted/stalls.
  - 검증: `test_adapter_tools_maintain`(24), `test_memory_activity`(7), `test_recall_guarantee`(7), `test_wiki_manager`(41) 통과.
  - 미검증: 실제 장기 누적 원장에서 승격 빈도·stall 패턴(사내망 실사용 관측).
  - 다음 작업: WS-7 정책 엔진(`auto_policy.py`)과 사용자 선택 최소화 — cmd_auto가 capability 결과를 바로 실행하지 않고
    `choose_execution_policy`(execute/plan_only/ask_user/blocked)를 거치게. 첫 파일: `workspace/agent_ops/auto_policy.py`(신규),
    `workspace/agent_ops/agentops.py`(cmd_auto), `workspace/tests/test_auto_policy.py`. **safety는 우회 못 하고 더 보수적으로만.**
- WS-7 완료 기록(2026-07-08, 커밋 a840562):
  - 변경 요약: 신규 `auto_policy.choose_execution_policy(request, capabilities, context, safety, hint)` →
    `{mode(execute/plan_only/ask_user/blocked), path, priority, requires_confirmation, reason, fallback, question}`.
    되돌릴 수 있는 산출물/조회/recall/plan은 execute, 삭제·앱저장·외부전송·모델기본값 변경 신호만 ask_user, pending 도구는
    plan_only, deny/불가역(초기화·format·rm -rf)은 blocked. **safety는 severity ladder에서 `max(base, floor)` 단방향 강등만** —
    execute를 낮출 순 있어도 ask_user를 execute로 올릴 수 없다(승인/가드 우회 불가, 구조적). ask_user 남발 방지(append/조회는 execute).
    cmd_auto가 `classify_action(task)`+hint를 정책에 넣어 trace에 policy/effective_mode/question 기록 후 mode로 실행 분기.
    plan_only/ask_user/blocked는 cmd_plan+안내(exit 0), `--yes`/`--execute`는 ask_user만 승격(blocked 불가). **WS-3 후크 보존**:
    위임 적재는 effective_mode==execute일 때만(정책이 plan으로 돌리면 auto가 자체 적재, 이중/누락 없음). intelligence_map에
    `context:auto_policy` 등록(165 checks).
  - 철학 종료 체크: (사용자 선택 최소화) 되돌릴 수 있으면 묻지 않고 실행 — ask_user는 위험/불가역/의미분기만. (안전) safety
    단방향 강등으로 자동화가 안전을 우회 불가, blocked는 안전 plan/report로 fallback. (남긴 trace) policy 전체+질문을 trace에
    기록해 WS-8 평가 입력이 된다. (모델) 기본값 미변경.
  - 검증: `test_auto_policy`(23), `test_auto_command`(27), `test_intelligence_map`(165), `test_capability_bench`(222),
    `test_auto_learning_hooks`(18), `pytest test_work_command`(4) 통과.
  - 미검증: 실 대화에서 ask_user 빈도·프롬프트 체감(사내망), `--yes` 승격 end-to-end(코드경로만 확인).
  - 다음 작업: WS-8 자기평가/성장 루프(`evaluation_loop.py`) — score_run(trace, outcome)로 route_confidence/tool_success/
    artifact_quality/user_friction/learning_value/safety_margin 채점, diagnostics/evaluations/*.jsonl append. **평가는 정책의
    보조 신호일 뿐 안전을 못 덮고, 단일 성공을 장기 선호로 과잉 승격하지 않는다.** 첫 파일: `workspace/agent_ops/evaluation_loop.py`(신규),
    `workspace/tests/test_evaluation_loop.py`.
- WS-8 완료 기록(2026-07-08, 커밋 afe7f59):
  - 변경 요약: 신규 `evaluation_loop.py` — `score_run(trace, outcome)`가 route_confidence/tool_success/artifact_quality/
    user_friction/learning_value/safety_margin(각 0~1, 순수·결정적, 시계 비의존)을 채점. `append_evaluation`은
    `DIAG_DIR/evaluations.jsonl`에 append-only(best-effort, USERDATA 미접촉). `route_preferences(min_samples=3)`는 표본 3 미만
    route를 선호로 안 올림(단일 성공 과잉승격 금지, 읽기전용 — auto_policy 미변경). `growth_report` 요약. cmd_auto는 **기존
    코드 무수정**, 헬퍼 `_append_auto_evaluation`을 dry_run 반환 직전·정상 outcome 확정 후 2지점에만 삽입(WS-3 후크·WS-7 정책·
    trace 필드 보존). intelligence_map에 `maintenance:evaluation_loop` 등록(166).
  - 철학 종료 체크: (성장) 실행마다 채점 근거가 diagnostics에 쌓여 다음 정책의 보조 신호가 된다. (겸손한 평가) min_samples=3로
    단일 성공을 장기 선호로 만들지 않고, route_preferences는 신호만 노출하며 정책·안전을 바꾸지 않는다. (안전) append-only +
    tmp 격리, auto_policy/memory_manager 미접촉. (남긴 trace) trace["evaluation"] 점수 + evaluations.jsonl.
  - 검증: `test_evaluation_loop`(29), `test_auto_command`(27), `test_auto_policy`(23), `test_auto_learning_hooks`(18),
    `test_intelligence_map`(166), `pytest test_work_command`(4) 통과.
  - 미검증: 실 누적 평가에서 route_preferences/growth_report의 유효성(사내망 장기 관측).
  - 다음 작업: WS-9 기억 품질 관리(`memory_quality.py`) — user_rule/preference/project_fact/activity/error_pattern/candidate
    등급 분리 + dedupe/decay/promote 규칙. **user_rule/manual wiki는 자동 감쇠·삭제 금지, 원본 로그 비파괴.** 첫 파일:
    `workspace/agent_ops/memory_quality.py`(신규), `workspace/tests/test_memory_quality.py`. **memory.jsonl append 최적화는 여전히 신중히(계측 후).**
- WS-9 완료 기록(2026-07-09, 커밋 ebfd08c):
  - 변경 요약: 신규 `memory_quality.py` — `classify_grade`(user_rule/preference/project_fact/activity/error_pattern/candidate),
    `quality_decisions`(순수: promote=다른날 3회 관측 candidate 태그/priority 상향, decay=60일↑ activity status=archived 또는
    저가치 candidate priority=low, dedupe_superseded=완전동일 중복만 status=superseded). `apply_quality`는 file_lock 안에서
    status/priority/tags만 갱신, **행 삭제 없음** — 쓰기 직전 `ids_after==ids_before` 가드로 개수 불변 보장, protected
    (user_rule/preference/project_fact/source=user)는 `continue`로 미접촉, 파괴적 연산(unlink/del/pop) 미사용.
    memory_manager.recall은 등급 가중 8줄(user_rule/preference/project_fact 우선, 비user activity ×0.5 감쇠=제외 아님,
    시그니처·core_memory 불변, append/rewrite 무변경). auto_maintain 스로틀에 apply_quality 배선(2d). error_pattern 승격은
    WS-6에 위임(중복 없음). intelligence_map에 `memory:memory_quality` 등록(167). **memory.jsonl append 최적화는 미룸(계측 우선).**
  - 철학 종료 체크: (기억은 정제) 반복 확인·검증된 것만 승격, 오래된 일회성 로그만 감쇠(삭제 아님)해 recall 품질↑. (안전)
    user_rule/preference/manual 비감쇠, 원장 행 개수 불변을 가드+테스트로 이중 보장, 원본 비파괴. (남긴 trace) maybe_maintain
    summary.quality{promoted,decayed,superseded,protected_untouched}.
  - 검증: `test_memory_quality`(35, 안전회귀 포함), `test_recall_guarantee`(7), `test_memory_activity`(7), `test_recall_stemming`(9),
    `test_wiki_manager`(41), `test_adapter_tools_maintain`(24), `test_intelligence_map`(167) 통과.
  - 미검증: decay/promote 임계값(60일·3회·importance 0.45)의 운영 적정성은 사내망 장기 누적에서 튜닝.
  - 다음 작업: WS-10 전체 지능망 최종 리뷰 — INTELLIGENCE_COVERAGE_REPORT 최신화, auto route trace 8종 샘플, 미연결 0/안전
    우회 0/USERDATA 위험 0/GitHub push 0 판정, 사내망 필요 항목 체크리스트 분리.
