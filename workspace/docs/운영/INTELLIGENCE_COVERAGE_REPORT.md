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

총 140개 지능 항목을 지도에 등록했다.

| kind | auto | advanced | pending | deprecated |
| --- | ---: | ---: | ---: | ---: |
| command | 15 | 27 | 0 | 0 |
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
