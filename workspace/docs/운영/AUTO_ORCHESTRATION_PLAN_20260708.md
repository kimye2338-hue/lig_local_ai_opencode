# OpenCodeLIG 자동 운영 루프 개선 계획 (2026-07-08)

목표: 사용자가 기능을 고르지 않아도 자연어로 요청만 하면 내부에서 가장 적절한 경로를 선택하고,
실행 결과를 검증하고, 배운 내용을 기억/위키/지식책에 축적하며, 시간이 지나도 스스로 정리·효율화하는 구조를 만든다.

이 문서는 로컬 작업 기준이다. GitHub push는 별도 지시 전까지 하지 않는다.

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
1. `cmd_auto(args)` 추가.
2. `capabilities.plan_task()` 결과에 따라 실행 경로 선택:
   - `schedule_management` 단독 고신뢰 → `cmd_schedule add` 경로로 위임
   - 산출물 필요 → 기존 `cmd_work` 경로 재사용
   - 파일/브라우저/앱 조작 중심 → `cmd_agent` 경로 재사용
   - 애매하면 안전한 `plan` + 사용자 확인 보고
3. 라우팅 trace를 `diagnostics/auto-route-last.json`에 저장.
4. OpenCode 기본 레시피는 `/auto`를 1순위로 안내하고, 세부 명령은 고급/직접 실행용으로 남긴다.

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
1. capability id 기준으로 tool group/skill hint를 연결하는 작은 메타데이터를 추가한다.
2. `tool_dispatch`는 prompt 키워드만 보지 않고, 가능하면 `capability_ids`를 우선 사용한다.
3. `skill_router`도 capability 기반 우선순위를 받도록 옵션을 둔다.
4. 키워드 중복을 당장 완전 제거하지는 말고, 테스트로 drift를 먼저 막는다.

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
1. `agentops.py`에 `_complete_activity(task, outcome, kind, files, route)` 같은 공통 후크 추가.
2. `work`, `agent`, `report-html`, `report-xlsx`, `office-doc`, `doc-template`, `routine run`, `briefing` 성공 경로가 공통 후크를 사용하게 정리.
3. 실패는 `record_self_error()`로 들어가되, 같은 날/같은 원인 중복 억제.
4. `memory-inject.ts` compaction summary는 `remember`가 아니라 low priority activity 또는 별도 CLI 경로를 사용하도록 낮은 등급화한다. 최소한 hash/day 중복 억제를 넣는다.
5. `recall --pinned`의 최근 activity 개수/길이를 제한해 세션 시작 컨텍스트 오염을 줄인다.

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
1. `wiki/manual/*.md`를 `recall_pages()` 후보에 포함하되, 자동 페이지와 구분되는 source를 표시한다.
2. manual 노트는 원장으로 역동기화하지 않는다. 사람이 쓴 노트는 원본을 보존하고 recall에서만 사용한다.
3. manual/auto 양쪽에서 같은 키워드가 잡히면 manual을 1개 우선 포함한다.

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
1. `AGENTOPS_HOME`을 모든 명령/플러그인의 기준 경로로 확립한다.
2. `.opencode/commands/*.md`의 `python agent_ops/...` 상대경로를 `%AGENTOPS_HOME%\agent_ops\...` 기준으로 정규화한다.
3. `RUN_OPENCODE_LIG.bat`는 OpenCode 실행 직전 `AGENTOPS_OUTPUT_DIR`가 있으면 그 폴더로 cwd를 복원한다.
4. `.bat` env 로더는 값 양끝 따옴표/공백을 정리한다.
5. `opencode.json` env 단일소스화는 두 단계로 한다.
   - 1단계: 현재 값 유지, 테스트로 JSON 유효성과 provider/model 기본값을 고정
   - 2단계: 사내망에서 OpenCode env 보간 지원 확인 후 적용. 미확인이면 런처가 `opencode.generated.json`을 생성하는 방식으로 우회
6. 모델 기본값 단일화는 사용자 A/B 확인 전에는 변경하지 않는다.

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
1. 유지보수 실행 결과에 consolidate/book/lint 횟수와 skip reason을 기록한다.
2. audit/timeline에서 반복 실패나 긴 stall을 감지해 `error_pattern`으로 승격하는 opt-in 배치를 추가한다.
3. `remember` 1회에서 위키/책 재생성 중복 호출을 줄인다.
4. 위험도가 큰 `memory.jsonl` append 최적화는 마지막 단계로 미룬다. 먼저 계측과 테스트를 만든 뒤 진행한다.

**검증**
- `py -3.11 tests\test_adapter_tools_maintain.py`
- `py -3.11 tests\test_memory_activity.py`
- `py -3.11 tests\test_wiki_manager.py`
- tmp USERDATA 격리 테스트

**서브에이전트 배정**
- 구현: `worker`, `gpt-5.4`, 파일 소유 `auto_maintain.py`, `activity_timeline.py`, 관련 테스트
- 검토: `gpt-5.5` 또는 main agent, 데이터 손상 위험 검토

---

### WS-7. 전체 지능망 최종 리뷰

**목표:** 구현이 끝난 뒤 "기능 몇 개를 붙였다"가 아니라 전체 지능망이 닫힌 루프인지 검토한다.

**파일**
- 수정: `workspace/docs/운영/INTELLIGENCE_COVERAGE_REPORT.md`
- 수정: `workspace/docs/운영/AUTO_ORCHESTRATION_PLAN_20260708.md`
- 필요 시 수정: 발견된 누락 테스트/문서

**작업**
1. `INTELLIGENCE_COVERAGE_REPORT.md`를 최신 코드 기준으로 갱신한다.
2. `auto` route trace 샘플을 최소 6개 남긴다.
   - 문서 작성
   - 데이터/HTML 리포트
   - 일정/비서 요청
   - Obsidian/wiki/recall 요청
   - 앱/브라우저/파일 조작 요청
   - 공학/전공 KB 질문
3. 각 샘플에서 모델/provider, context, tools, verification, memory/wiki hook이 기록되는지 확인한다.
4. `gpt-5.5` reviewer 또는 main agent 최종 검토로 다음을 판정한다.
   - 미연결 지능 0개
   - 안전 장치 우회 0개
   - USERDATA 위험 변경 0개
   - GitHub push 없음
   - 사내망 실기기 필요 항목은 별도 체크리스트로 분리

**검증**
- `py -3.11 tests\test_intelligence_map.py`
- `py -3.11 tests\test_auto_command.py`
- `py -3.11 tests\test_routing_alignment.py`
- `py -3.11 tests\test_auto_learning_hooks.py`
- `py -3.11 tests\test_wiki_manager.py`
- `py -3.11 tests\test_launch_bats.py`
- `python -m pytest tests\test_work_command.py -q`
- `python agent_ops\agentops.py doctor`

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
9. WS-7 전체 지능망 최종 리뷰.
10. 작업 종료 기록 업데이트 + 로컬 커밋. GitHub push는 사용자 지시 전까지 금지.

---

## 7. 서브에이전트 운용 원칙

- main agent가 설계, 파일 소유권, 통합, 최종 판단을 맡는다.
- 구현 작업은 파일 소유권이 겹치지 않을 때만 병렬화한다.
- 단순 테스트/문서/단일 파일 작업은 `gpt-5.4-mini`.
- 다중 파일 통합 구현은 `gpt-5.4`.
- 전체 설계 검토, 데이터 손상 가능성, 최종 브랜치 리뷰는 `gpt-5.5`.
- 각 서브에이전트는 GitHub push 금지, USERDATA 삭제 금지, 다른 작업자 변경 되돌리기 금지.
- 각 작업은 완료 후 다음을 남긴다:
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
- 내부는 요청을 command-native, artifact, tool-agent, schedule, wiki/memory 경로 중 하나로 자동 선택한다.
- 모든 실행은 route trace와 work report를 남긴다. trace에는 선택된 capability, command/tool 경로, model/provider,
  context source, verification, memory/wiki hook이 포함된다.
- 성공은 activity/lesson으로, 실패 반복은 error_pattern으로 자동 축적된다.
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
- 다음 첫 작업: 바로 `cmd_auto` 구현으로 들어가지 말고 `workspace/agent_ops/intelligence_map.py`와
  `workspace/tests/test_intelligence_map.py`를 먼저 작성해 전체 지능 목록을 고정한다.
