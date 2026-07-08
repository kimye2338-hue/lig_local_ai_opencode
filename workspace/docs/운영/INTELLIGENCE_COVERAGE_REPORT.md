# OpenCodeLIG 지능 연결 범위 보고서 (WS-0, 2026-07-08)

## 시작 전 철학 체크

- 이 작업이 줄이는 사용자 부담: 사용자가 명령, 도구, 어댑터의 존재와 상태를 직접 추적하지 않아도 된다.
- 연결되는 지능층: command, capability, artifact, tool, adapter, context, memory, maintenance, safety, packaging.
- 사용자가 선택하지 않아도 되게 만드는 부분: 이후 `/auto`가 전체 기능 후보를 중앙 지도에서 찾고 누락 여부는 테스트가 잡는다.
- 반드시 멈춰야 하는 위험: USERDATA 손상, LLM 설정 변경, 안전 가드 우회, 검증되지 않은 기능을 자동 가능으로 과장하는 것.
- 작업 결과가 돌아갈 기억/평가/위키/유지보수 경로: 이 보고서와 `intelligence_map.py`가 이후 route trace, evaluation, 유지보수의 기준 지도가 된다.

## WS-0 산출물

- `workspace/agent_ops/intelligence_map.py`: 전체 지능 항목의 명시적 지도.
- `workspace/tests/test_intelligence_map.py`: 실제 command/capability/artifact/tool/adapter 목록과 지도의 drift를 잡는 테스트.
- `workspace/docs/운영/INTELLIGENCE_COVERAGE_REPORT.md`: 사람이 읽는 범위 보고서와 작업 체크 기록.

## 현재 분류 원칙

- `auto`: 일반 요청에서 자동 경로가 선택할 수 있거나, 자동 컨텍스트/기억/후처리에 이미 참여하는 항목.
- `advanced`: 사용자/운영자/진단/명시적 실행용으로 남겨야 하는 항목.
- `pending`: 기능은 존재하지만 앱, 의존성, 사내 환경, 또는 안전 검증이 끝나지 않아 자동 기본 경로로 과장하면 안 되는 항목.
- `deprecated`: 폐기 후보. 현재 WS-0 기준으로는 의도적으로 폐기한 항목이 없다.

## 현재 집계

총 141개 지능 항목을 지도에 등록했다. WS-1에서 `/auto` command가 추가되어 command auto 항목이 1개 늘었다.

| kind | auto | advanced | pending | deprecated |
| --- | ---: | ---: | ---: | ---: |
| command | 16 | 27 | 0 | 0 |
| capability | 13 | 0 | 0 | 0 |
| artifact | 8 | 1 | 1 | 0 |
| tool | 29 | 0 | 0 | 0 |
| adapter | 6 | 0 | 4 | 0 |
| context | 13 | 0 | 0 | 0 |
| memory | 4 | 0 | 0 | 0 |
| maintenance | 6 | 3 | 0 | 0 |
| safety | 4 | 1 | 0 | 0 |
| packaging | 0 | 4 | 1 | 0 |

## 검증 범위

`test_intelligence_map.py`는 다음을 코드에서 직접 읽어 검증한다.

- `.opencode/commands/*.md`의 모든 slash command
- `agentops.py`에 존재하는 CLI command 표면
- `capabilities.CAPABILITIES`의 모든 capability id
- `capabilities.ARTIFACT_KIND_INFO`와 capability가 선언한 모든 artifact kind
- `tool_dispatch.REGISTRY`의 모든 tool id
- `adapters.ADAPTERS`의 모든 adapter id
- `agent_ops/adapters/*.py` 구현 파일의 소유 adapter
- 모든 항목의 `kind`, `status`, `owner_files`, `route/reason` 계약

## 현재 주의 항목

- `solidworks`, `fluent`, `ocr_screen`, `desktop_ui`는 기능 표면이 있으나 검증/반입 상태 때문에 `pending`으로 둔다.
- `fluent_journal`, `ansys_script`는 산출물 생성 표면은 있으나 실제 실행 검증 또는 수동 앱 콘솔 절차가 필요하므로 자동 실행으로 과장하지 않는다.
- queue/orchestrator, safe-write, safety-check, doctor/verify/status 계열은 사용자를 돕는 핵심 지능이지만 기본 자동 실행이 아니라 `advanced`로 둔다.
- `.opencode` 전용 helper command는 실제 `agentops.py` CLI와 이름이 다를 수 있어 alias로 검증한다.

## 다음 작업으로 넘기는 계약

WS-1은 `/auto`를 구현할 때 `intelligence_map.py`를 읽어 자동 가능 항목과 고급/보류 항목을 구분해야 한다.
새 command, capability, artifact, tool, adapter를 추가하는 작업자는 같은 커밋에서 지도를 갱신해야 하며, 갱신하지 않으면
`test_intelligence_map.py`가 실패해야 한다.

## WS-0 종료 후 철학 체크

- 줄어든 사용자 선택: 기능이 어디에 있는지 사용자가 추적하지 않아도 되도록, command/capability/artifact/tool/adapter/context/memory/maintenance/safety/packaging 표면을 중앙 지도에 묶었다.
- 새로 연결된 지능: `intelligence_map.py`가 실제 source inventory와 연결되고, `test_intelligence_map.py`가 drift를 잡는다.
- 남긴 trace/report/evaluation/memory: 실행 trace는 아직 WS-1 대상이다. 이번 단계에서는 `INTELLIGENCE_COVERAGE_REPORT.md`와 테스트 출력이 기준 report 역할을 한다.
- 보호한 안전 조건: USERDATA, LLM 설정, command_guard/approval/safety 동작은 수정하지 않았다. pending 기능은 자동 가능으로 과장하지 않았다.
- 아직 이어지지 않은 부분과 이유: `/auto` 라우팅, policy, evaluation, memory quality는 후속 WS 대상이다. WS-0은 전체 지도를 고정하는 단계다.
- 다음 작업자가 먼저 봐야 할 파일: `workspace/agent_ops/intelligence_map.py`, `workspace/tests/test_intelligence_map.py`, `workspace/docs/운영/AUTO_ORCHESTRATION_PLAN_20260708.md`.

## WS-0 검증 결과

- `py -3.11 tests\test_intelligence_map.py`: PASS, ALL 162 CHECKS PASSED.
- `py -3.11 tests\test_tool_dispatch.py`: PASS, ALL 28 CHECKS PASSED.
- `py -3.11 tests\test_capability_bench.py`: PASS, ALL 222 CHECKS PASSED.

## 다음 단계

WS-1은 `/auto` 단일 진입점을 구현한다. 시작 전 `BUILD_PHILOSOPHY_20260708.md`의 시작 체크를 다시 작성하고,
`intelligence_map.py`의 `auto`, `advanced`, `pending` 상태를 참고해 사용자가 선택하지 않아도 되는 기본 경로를 만든다.

## WS-1 시작 전 철학 체크

- 이 작업이 줄이는 사용자 부담: 사용자가 `/work`, `/agent`, `/schedule`, `/wiki` 중 무엇을 골라야 하는지 판단하지 않아도 된다.
- 연결되는 지능층: command, capability, artifact, tool, schedule, routine, memory/wiki, diagnostics trace.
- 사용자가 선택하지 않아도 되게 만드는 부분: 자연어 요청을 `command_native`, `artifact`, `tool_agent`, `memory_wiki`, `plan_only` 중 하나로 자동 분기한다.
- 반드시 멈춰야 하는 위험: 위험 실행을 `/auto`가 몰래 실행하는 것, `--yes` 없는 승인 우회, LLM/provider 기본값 변경, USERDATA 손상.
- 작업 결과가 돌아갈 기억/평가/위키/유지보수 경로: WS-1은 route trace와 work report를 남기는 기반을 만든다. 실제 공통 학습/evaluation 후크는 WS-3/WS-8에서 표준화한다.

## WS-1 종료 후 철학 체크

- 줄어든 사용자 선택: 사용자가 `/work`, `/agent`, `/schedule`, `/wiki`, `/book`, `/recall`, `/remember`, `/routine` 중 하나를 직접 고르지 않아도 `/auto`가 안정적인 하위 경로를 먼저 고른다.
- 새로 연결된 지능: `capabilities.plan_task`의 capability/artifact 판단, command-native 일정/루틴/기억 명령, artifact 생성 경로, tool-agent 경로, diagnostics trace를 한 입구에 연결했다.
- 남긴 trace/report/evaluation/memory: 실행 또는 dry-run마다 `diagnostics/auto-route-last.json`에 request, routing, planner_mode, capability_ids, artifact_kinds, selected_path, command, model/provider 불변 메모, context source, verification, memory hook 예정, safety/fallback을 남긴다. 공통 evaluation/memory 적재는 WS-3/WS-8 계약으로 보류 상태를 trace에 명시했다.
- 보호한 안전 조건: `/auto`는 기존 command 함수를 위임 호출하고 approval/command_guard를 우회하지 않는다. LLM/provider 기본값과 USERDATA는 수정하지 않았다.
- 아직 이어지지 않은 부분과 이유: WS-1은 얇은 자동 입구라 policy engine, 공통 completion hook, evaluation record, 기억 품질 승격은 아직 구현하지 않았다. 이들은 WS-3, WS-7, WS-8, WS-9에서 route trace를 입력으로 이어진다.
- 다음 작업자가 먼저 봐야 할 파일: `workspace/agent_ops/agentops.py`의 `_auto_command_hint`/`cmd_auto`, `workspace/tests/test_auto_command.py`, `workspace/agent_ops/intelligence_map.py`, `workspace/docs/운영/AUTO_ORCHESTRATION_PLAN_20260708.md`의 WS-2.

## WS-1 검증 결과

- `py -3.11 tests\test_auto_command.py`: PASS, ALL 14 CHECKS PASSED.
- `py -3.11 tests\test_intelligence_map.py`: PASS, ALL 163 CHECKS PASSED.
- `py -3.11 tests\test_opencode_command_coverage.py`: PASS, ALL 25 CHECKS PASSED.
- `py -3.11 tests\test_tool_dispatch.py`: PASS, ALL 28 CHECKS PASSED.
- `py -3.11 tests\test_capability_bench.py`: PASS, ALL 222 CHECKS PASSED.
- `$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; python -m pytest tests\test_work_command.py -q`: PASS, 4 passed.

## 다음 단계

WS-2는 capability 기준으로 도구/스킬/컨텍스트 선택 메타데이터를 정렬한다. `/auto`가 남기는 route trace를 입력으로 삼되, 안전과 USERDATA 보호는 계속 상위 원칙으로 둔다.

## WS-2 시작 전 철학 체크

- 이 작업이 줄이는 사용자 부담: 사용자가 같은 요청을 할 때 어떤 명령은 도구를 알고 어떤 명령은 모르는 식의 차이를 신경 쓰지 않아도 된다.
- 연결되는 지능층: capability planning, tool exposure, process skill injection, context source trace, route alignment tests.
- 사용자가 선택하지 않아도 되게 만드는 부분: 자연어 키워드가 약하거나 우회 표현이어도 capability id가 있으면 관련 도구와 절차 스킬이 먼저 선택된다.
- 반드시 멈춰야 하는 위험: 도구를 너무 많이 열어 약한 모델의 선택 정확도를 떨어뜨리는 것, schema byte budget을 깨는 것, capability와 tool registry drift를 테스트 없이 방치하는 것.
- 작업 결과가 돌아갈 기억/평가/위키/유지보수 경로: WS-2의 alignment 메타데이터는 `/auto` route trace와 WS-3 공통 completion hook에서 "왜 이 도구/스킬이 보였는가"를 설명하는 근거가 된다.

## WS-2 종료 후 철학 체크

- 줄어든 사용자 선택: 사용자가 웹/메일/MATLAB/CAD/보고서 같은 작업에서 어떤 도구나 절차 스킬을 열어야 하는지 고르지 않아도 capability id가 하위 선택을 이끈다.
- 새로 연결된 지능: `CAPABILITY_ROUTE_HINTS`가 capability planning, `tool_dispatch.tool_definitions`, `skill_router.detect_skill/context_for_prompt`, `/auto` route trace를 연결한다.
- 남긴 trace/report/evaluation/memory: `/auto` trace의 `route_hints`에 capability, tools, skill_sections, context_sources가 기록된다. evaluation과 memory 승격은 WS-3/WS-8/WS-9로 이어질 입력만 만든 상태다.
- 보호한 안전 조건: tool registry에 없는 도구명은 노출하지 않으며, 기존 schema 설명을 늘리지 않아 tool schema byte budget을 유지했다. USERDATA, LLM/provider 설정, approval/command_guard는 수정하지 않았다.
- 아직 이어지지 않은 부분과 이유: 실행 결과를 공통 activity/evaluation/memory로 보내는 후처리는 아직 없다. 이 연결은 WS-3에서 `_complete_activity`류 공통 후크로 구현한다.
- 다음 작업자가 먼저 봐야 할 파일: `workspace/agent_ops/capabilities.py`의 `CAPABILITY_ROUTE_HINTS`, `workspace/agent_ops/tool_dispatch.py`의 `tool_definitions(..., capability_ids=...)`, `workspace/agent_ops/skill_router.py`, `workspace/tests/test_routing_alignment.py`, WS-3 계획.

## WS-2 검증 결과

- `py -3.11 tests\test_routing_alignment.py`: PASS, ALL 9 CHECKS PASSED.
- `py -3.11 tests\test_tool_dispatch.py`: PASS, ALL 28 CHECKS PASSED.
- `py -3.11 tests\test_skill_router.py`: PASS, ALL 11 CHECKS PASSED.
- `py -3.11 tests\test_intelligence_map.py`: PASS, ALL 163 CHECKS PASSED.
- `py -3.11 tests\test_auto_command.py`: PASS, ALL 18 CHECKS PASSED.
- `py -3.11 tests\test_capability_bench.py`: PASS, ALL 222 CHECKS PASSED.
- `$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; python -m pytest tests\test_work_command.py -q`: PASS, 4 passed.

## WS-3 완료 (2026-07-08, 커밋 854505f + c79ae88)

- 새로 연결된 지능: 실행 결과(성공/실패/보류) → 공통 후크 `_complete_activity` → activity(low) 또는 error_pattern(당일·동일원인 중복억제) → recall 재주입. 어느 경로(work/agent/auto/report-*/office-doc/doc-template/routine)로 실행하든 동일 표준.
- 새 항목: `command:log-activity`(advanced, 플러그인 내부용) — TUI compaction 요약을 high-priority remember 대신 low-priority activity로 적재. 지도 항목 수 163→164.
- 보호한 안전: USERDATA는 add_activity/record_self_error 경유만, 적재 실패가 본 작업 미차단, 승인/가드/LLM 설정 무변경. recall --pinned activity 출력 200자 절단(원장 불변).
- 검증: test_auto_learning_hooks(18), test_memory_inject_plugin(23), test_intelligence_map(164), test_opencode_command_coverage(25), test_memory_activity(7), test_recall_guarantee(7), test_wiki_manager(34), pytest test_work_command(4) PASS.
- 미검증(사내망 필요): 실 TUI compaction 훅에서 log-activity 동작·recall 주입 체감.

## WS-4 완료 (2026-07-08, 커밋 70e5e95)

- 새로 연결된 지능: 사람이 쓴 `wiki/manual/*.md`가 `recall_pages`를 통해 자동 회상 대상이 됨(source=auto/manual 구분). auto+manual 동시 매칭 시 manual 최소 1개 포함, tool_dispatch limit=2로 둘 다 주입.
- 보호한 안전: manual 원본 읽기전용(역주입/수정/삭제 없음, 내용 해시 불변 테스트). USERDATA 미접촉.
- 검증: test_wiki_manager(41), test_tool_dispatch(28), test_recall_guarantee(7), test_knowledge_routing(42) PASS.

## WS-5 부분완료 (2026-07-08) — 사내망-gated

- 오프라인 완료(무위험): `test_opencode_config.py` 신규(27 checks) — opencode.json JSON 유효성 + 기본 model resolve + provider 구조 + baseURL 사내 게이트웨이 + **기본 라우트 think_off(tool-calling 안전)** 불변식 고정.
- 보류(사내망 필요): 48개 커맨드 `.md` 경로 정규화 + ocd cwd 복원 + env 보간 + 모델 기본값 단일화. **패치 opencode.exe bash 셸(cmd/POSIX) 미확인**이라 블라인드 치환 시 전 커맨드가 깨질 위험 → 셸 확인 선행. 절차는 AUTO_ORCHESTRATION_PLAN 9절 WS-5 기록 참조.

## WS-6 완료 (2026-07-08, 커밋 6dcc314)

- 새로 연결된 지능: 유지보수 루프(maybe_maintain)가 반복 실패를 error_pattern 승격(opt-in, 다른 날 3회)으로 정제하고 stall을 계측 → recall 우선순위/관측성 강화. 원장 append 최적화는 미룸(계측 먼저).
- 보호한 안전: 승격은 태그/우선순위만(삭제·병합 없음), user_rule/preference 미대상, 원본 비파괴 테스트 고정, USERDATA 미접촉.
- 검증: test_adapter_tools_maintain(24), test_memory_activity(7), test_recall_guarantee(7), test_wiki_manager(41) PASS.

## WS-7 완료 (2026-07-08, 커밋 a840562)

- 새로 연결된 지능: cmd_auto가 실행 전 `auto_policy.choose_execution_policy`로 execute/plan_only/ask_user/blocked 결정. 되돌릴 수 있으면 조용히 실행, 위험/불가역만 확인/차단. context:auto_policy 지도 등록(165).
- 보호한 안전: safety는 `max(base,floor)` 단방향 강등만 — 승인/가드 우회 불가(구조적). ask_user 남발 방지. 모델 기본값 미변경.
- 검증: test_auto_policy(23), test_auto_command(27), test_intelligence_map(165), test_capability_bench(222), test_auto_learning_hooks(18) PASS.

## 다음 단계

WS-8 자기평가/성장 루프(`evaluation_loop.py`): score_run(trace, outcome) → diagnostics/evaluations append. **평가는 정책 보조 신호일 뿐 안전 미대체, 단일 성공 과잉승격 금지.** 첫 파일: `workspace/agent_ops/evaluation_loop.py`, `workspace/tests/test_evaluation_loop.py`.
