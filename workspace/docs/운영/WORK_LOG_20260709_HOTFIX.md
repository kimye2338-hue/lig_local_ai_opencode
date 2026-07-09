# 2026-07-09 기존 설치본 보완 작업 이력

## 사용자 보고

- `RUN_OPENCODE_LIG.bat` 시작 시 `probe-gateway is not recognized...` 문구가 보임.
- OpenCode TUI 좌측 하단에 Obsidian의 `obsidian.md` 업데이트 실패 로그가 겹쳐 보임.
- `cd 작업폴더` 후 `ocd`로 실행해도 산출물과 조회 기준이 설치 workspace 쪽으로 쏠리는 것으로 보임.
- Obsidian은 자동 실행을 유지해야 함.

## 원인 판단

- `probe-gateway`는 기능 파일이 없는 것이 아니라 짧은 명령 이름을 받아줄 설치 루트 `bin` wrapper가 부족한 문제로 판단했다.
- Obsidian 오류는 폐쇄망에서 업데이트 서버 `obsidian.md`를 찾지 못해 나는 로그다. 핵심 문제는 업데이트 실패 자체가 아니라 그 로그가 OpenCode 콘솔에 섞이는 실행 방식이다.
- 기존 `ocd.py`는 현재 폴더 기준 프로필을 만들도록 설계되어 있었지만, 최종 런처가 다시 설치 workspace로 `cd` 하면서 작업 기준점이 흐려졌다.
- `agent_ops.core`는 `AGENTOPS_ROOT`를 결과 저장 기준으로 사용한다. 이를 작업폴더로 넘기되, 전역 기억은 `AGENTOPS_MEMORY_DIR=%USERPROFILE%\OpenCodeLIG_USERDATA\memory`로 고정해야 기억 누적 구조가 깨지지 않는다.

## 적용한 방향

- Obsidian은 계속 자동으로 띄운다.
- Obsidian 실행은 `launch\obsidian_detached.vbs`를 통해 분리해 OpenCode TUI에 Electron 로그가 섞이지 않게 했다.
- `RUN_OPENCODE_LIG.bat`는 사용자가 `cd`로 들어온 폴더를 `LIG_PROJECT_DIR`로 보존한다.
- 프로그램 파일은 설치 workspace에서 읽고, OpenCode 실행 직전에는 `LIG_PROJECT_DIR`로 돌아간다.
- 작업폴더에 `.opencode`가 없으면 설치본의 `.opencode`를 복사해 slash command를 쓸 수 있게 한다.
- 작업폴더의 `agent_ops\agentops.py`, `command_guard.py`, `safe_file_writer.py`는 실제 설치본 엔진으로 연결하는 작은 wrapper로 생성한다.
- 기존 `ocd.py`의 폴더별 `.opencodelig` 프로필 생성 흐름은 유지한다.
- 기존 설치본용 핫픽스는 `workspace\patches\existing_install_hotfix_20260709.py`와 `PATCH_EXISTING_INSTALL_LIG_OPENCODE_20260709.bat.txt`로 유지한다.

## 검증

- `py -3.11 -m pytest workspace\tests\test_existing_install_hotfix.py workspace\tests\test_work_command.py -q`
  - 결과: 7 passed
- `py -3.11 workspace\tests\test_launch_bats.py`
  - 결과: ALL 101 CHECKS PASSED
- `py -3.11 -m py_compile workspace\patches\existing_install_hotfix_20260709.py workspace\launch\project_agentops_wrapper.py`
  - 결과: 통과
- `ocd.py --no-launch` 임시 폴더 검증
  - `.opencodelig`와 `OpenCode_열기.bat` 생성 확인
- 작업폴더용 `agent_ops/agentops.py status` wrapper 검증
  - 설치본 엔진으로 연결되어 정상 JSON 출력 확인

## 남은 확인

- 실제 사내 PC에서 `cd 원하는작업폴더` 후 `ocd` 실행.
- OpenCode TUI에 Obsidian 업데이트 실패 로그가 더 이상 겹치지 않는지 확인.
- Obsidian 창은 계속 자동으로 뜨는지 확인.
- 작업 후 산출물이 `%USERPROFILE%\OpenCodeLIG\workspace`가 아니라 해당 작업폴더 또는 그 하위 결과 폴더에 쌓이는지 확인.

## 2026-07-09 추가 보강: 세션 자동저장

사용자 지적: 일반 대화 중 창을 닫으면 Obsidian에 내용이 쌓이지 않았다. 기존 구현은 `/remember`, `/auto`, `/work`, compaction 요약처럼 명령 완료 또는 요약 이벤트 중심이었다. “사용자는 그냥 사용하고, 시스템이 알아서 축적한다”는 원칙 기준으로는 부족했다.

조치:

- `.opencode/plugins/session-autosave.ts` 추가.
- OpenCode 세션 이벤트를 `%USERPROFILE%\OpenCodeLIG_USERDATA\memory\wiki\sessions\YYYY-MM-DD-opencode-session.md`에 즉시 append.
- 일정량 이상 쌓이면 `agentops.py log-activity`로 저우선순위 활동 기억에도 자동 승격.
- 잘못된 JS 정규식 문법 `(?i:...)` 제거.
- `RUN_OPENCODE_LIG.bat`가 기존 작업폴더 `.opencode`에도 `session-autosave.ts`를 보강 복사하도록 수정.
- `pending_check.py`에 `세션 자동저장 플러그인` 점검 항목 추가.

검증:

- `py -3.11 -m pytest workspace\tests\test_existing_install_hotfix.py workspace\tests\test_autocad_gui_fallback.py -q`
  - 결과: 8 passed
- `py -3.11 -m py_compile workspace\agent_ops\pending_check.py workspace\patches\existing_install_hotfix_20260709.py`
  - 결과: 통과

## 2026-07-09 추가 보강: 최종 단일 BAT 통합

사용자 지적: 여러 차례 패치가 나뉘면 사내 PC에서 무엇을 다시 실행해야 하는지 관리가 어려워진다. 최종 BAT 하나에 이전 보완과 현재 보완을 모두 누적해야 한다.

조치:

- `최종_패치파일.bat` 하나에 다음을 모두 포함:
  - `mss-10.2.0-py3-none-any.whl` 내장
  - Obsidian 분리 실행
  - `probe-gateway` wrapper
  - `ocd` 작업폴더 기준 실행
  - 세션 자동저장 플러그인
  - AutoCAD GUI 실행 경로 인식
  - 기존 설치본의 `agent_ops/adapters/autocad_batch.py` 실제 갱신
- 특히 AutoCAD는 점검만 PASS로 보이는 것이 아니라, 실제 어댑터가 `acad.exe <사본.dwg> /p LIGNEX1 /product ACADM /b <script.scr>` fallback을 수행하도록 기존 설치본 파일을 교체한다.
- 이미 같은 내용이면 덮어쓰지 않고 SKIP한다.

검증:

- `py -3.11 -m pytest workspace\tests\test_existing_install_hotfix.py workspace\tests\test_autocad_gui_fallback.py -q`
  - 결과: 8 passed
- `test_final_patch_bat_extracts_and_runs_against_min_install`로 최종 BAT 직접 실행 검증 포함.

## 2026-07-09 현재 패치본 위치와 이어작업 기준

현재 사용해야 하는 단일 패치본:

- 루트 파일: `최종_패치파일.bat`
- 실제 보강 로직 원본: `workspace/patches/existing_install_hotfix_20260709.py`
- 세션 자동저장 플러그인 원본: `workspace/.opencode/plugins/session-autosave.ts`
- AutoCAD 실행 어댑터 원본: `workspace/agent_ops/adapters/autocad_batch.py`

이전 보조 파일 `PATCH_EXISTING_INSTALL_LIG_OPENCODE_20260709.bat.txt`는 이력 확인용이다. 사내 PC에 적용할 때는 `최종_패치파일.bat` 하나만 실행하는 기준으로 유지한다.

현재 단일 패치본에 포함된 사항:

- `mss-10.2.0-py3-none-any.whl` 내장 및 이미 설치된 경우 건너뛰기.
- Obsidian 자동 실행 유지, 단 OpenCode TUI와 콘솔 출력이 섞이지 않도록 VBS 분리 실행.
- `probe-gateway`, `probe_gateway`, `gateway-smoke`, `ocd` wrapper 생성.
- `cd 작업폴더` 후 `ocd` 실행 시 그 폴더를 작업 기준점으로 보존.
- 작업폴더에 `.opencode`와 `agent_ops` wrapper가 없으면 자동 생성.
- 산출물 저장 기준은 작업폴더, 장기 기억과 위키 기준은 `%USERPROFILE%\OpenCodeLIG_USERDATA\memory`로 분리.
- 일반 대화/세션 이벤트를 Obsidian wiki `sessions` 폴더에 즉시 append하는 `session-autosave.ts` 설치.
- 일정량 이상 쌓인 세션 내용을 `agentops.py log-activity`로 활동 기억에도 자동 승격.
- AutoCAD 회사 실행 방식 `"C:\AutoCAD 2019\acad.exe" /p LIGNEX1 /product ACADM` 인식.
- `accoreconsole.exe`가 없을 때 `acad.exe <사본.dwg> /p LIGNEX1 /product ACADM /b <script.scr>` 방식으로 fallback.
- `pending_check.py`가 위 항목들을 PASS/WARN/PENDING으로 더 정확히 판정하도록 보강.

철학 기준으로 식별된 추가 점검 사항:

- 사용자는 수동 저장을 하지 않아도 기억이 쌓여야 한다. 따라서 OpenCode 재시작 후 `pending_check`의 `세션 자동저장 플러그인` 항목이 PASS여야 한다.
- OpenCode 창을 닫는 순간까지 모든 대화가 완벽히 보존된다고 단정하지 않는다. 플러그인은 이벤트 수신 즉시 append하므로 대부분의 손실을 줄이지만, 실제 OpenCode 이벤트 형태는 실사용으로 확인해야 한다.
- 작업 산출물은 설치 workspace로 쏠리면 안 된다. `cd 임의폴더 && ocd` 후 파일 생성 명령을 실행했을 때 해당 임의폴더 아래에 결과가 생기는지 확인한다.
- Obsidian은 자동으로 떠야 하지만, 폐쇄망 업데이트 실패 로그가 OpenCode 화면에 겹치면 안 된다.
- AutoCAD는 실행파일 탐색 PASS만으로 충분하지 않다. 실제 `.dwg` 사본과 `.scr` 파일 기준으로 GUI fallback 명령이 구성되는지 계속 확인한다.
- `최종_패치파일.bat`는 계속 단일 진입점이어야 한다. 이후 보강도 새 파일을 늘리지 말고 이 BAT와 `existing_install_hotfix_20260709.py`에 누적한다.

다음 작업자가 먼저 확인할 명령:

```cmd
py -3.11 -m pytest workspace\tests\test_existing_install_hotfix.py workspace\tests\test_autocad_gui_fallback.py -q
py -3.11 -m py_compile workspace\agent_ops\adapters\autocad_batch.py workspace\agent_ops\pending_check.py workspace\patches\existing_install_hotfix_20260709.py
```

## 2026-07-09 추가 보강: OpenCode 플러그인 런타임/햄스터/자동기억

사용자 지적: 햄스터가 OpenCode 작업 상태를 제대로 못 잡고, 세션 중 창을 닫으면 Obsidian에 자동으로 쌓이지 않는 것으로 보였다. 이전 점검은 플러그인 파일 존재를 봤지만, OpenCode가 실제로 플러그인을 로드하는지와 최신 이벤트명을 해석하는지까지 확인하지 못했다.

원인:

- `RUN_OPENCODE_LIG.bat`에 `OPENCODE_PURE=1`이 남아 있으면 OpenCode 외부 플러그인이 로드되지 않는다.
- `hamster-status.ts`가 최신 이벤트인 `session.status`, `session.next.text.delta`, `session.next.tool.*`, `session.next.step.*`를 충분히 처리하지 못했다.
- `session-autosave.ts`가 OpenCode 이벤트 본문이 들어오는 `event.properties` 내부를 충분히 재귀 추출하지 못했다.
- 기존 설치본 핫픽스는 런처에 마커가 있으면 건너뛰어, 잘못된 줄이 남은 PC를 다시 고치지 못할 수 있었다.
- `pending_check.py`가 파일 존재만 확인하고 플러그인 런타임이 실제로 살아 있는지는 판정하지 못했다.

조치:

- `RUN_OPENCODE_LIG.bat`에서 `OPENCODE_PURE=1` 제거.
- 프로젝트 폴더 `.opencode\plugins`에 설치본의 모든 필수 플러그인 `*.ts`를 매번 최신본으로 동기화.
- `hamster-status.ts`가 최신 OpenCode 이벤트를 읽어 `current_status.json`에 `working/done/error/idle`을 반영하도록 보강.
- 햄스터 상태파일 쓰기를 임시파일 후 rename 방식으로 바꿔 깨진 JSON을 줄였다.
- `session-autosave.ts`가 `properties`, `delta`, `input`, `output`, `error` 내부까지 재귀 추출하도록 보강.
- `memory-inject.ts`, `compaction-handoff.ts`는 `LIG_AGENTOPS_HOME`을 우선해 `cd 작업폴더 && ocd`에서도 설치본 엔진을 기준으로 동작하게 했다.
- `pending_check.py`에 `OpenCode 플러그인 런타임` 섹션을 추가해 `OPENCODE_PURE`, CRLF, 플러그인 동기화, 햄스터 이벤트 브리지, 자동저장 추출을 확인하게 했다.
- `workspace/patches/existing_install_hotfix_20260709.py`와 `최종_패치파일.bat`에도 같은 내용을 누적했다.

검증 기준:

```cmd
py -3.11 -m pytest workspace\tests\test_opencode_lig_plugin_runtime.py -q
py -3.11 -m pytest workspace\tests\test_existing_install_hotfix.py -q
```

주의:

- 이 패치 이후에도 실사용 중 Obsidian 자동저장은 OpenCode 이벤트가 발생한 만큼 즉시 append하는 구조다. “창 닫기 직전 아직 이벤트가 전달되지 않은 토큰”까지 보장하는 것은 아니지만, 현재 구조에서 자동 축적이 실제로 동작할 수 있게 플러그인 로딩과 이벤트 해석 경로를 복구했다.
- 이후 누군가 이어받으면 `pending-check-last.md`에서 `OpenCode 플러그인 런타임` 섹션을 먼저 확인한다.

## 2026-07-09 추가 보강: LiteLLM 원격 cost map 경고 차단

사용자 지적:

```text
litellm:warning:get_model_cost_map.py:264 - LiteLLM:Failed to fetch remote model cost map from https://raw.githubusercontent.com/berriai/litellm/main/model_prices_and_context_window.json:[errno 11002]getaddrinfo failed. Falling back to local backup.
```

원인:

- 폐쇄망에서 LiteLLM이 import 시 GitHub의 모델 가격/컨텍스트 표를 받으려다 DNS 실패를 낸다.
- LiteLLM은 로컬 백업으로 fallback하므로 일반 LLM 호출 자체가 막히는 오류는 아니다.
- 다만 사용자 화면에 warning이 계속 뜨면 실제 장애처럼 보이므로, 폐쇄망 제품 기준으로는 원격 조회를 처음부터 끄는 것이 맞다.

조치:

- `RUN_OPENCODE_LIG.bat`, `launch\_py.bat`, `launch\_pyw.bat`, `최종_패치파일.bat`에 아래 값을 설정.

```bat
set "LITELLM_LOCAL_MODEL_COST_MAP=True"
set "LITELLM_LOCAL_POLICY_TEMPLATES=True"
set "LITELLM_LOCAL_BLOG_POSTS=True"
```

- `agent_ops\agentops.py`에서도 Python 직접 실행 경로를 위해 같은 값을 `os.environ.setdefault(...)`로 설정.
- `existing_install_hotfix_20260709.py`가 기존 설치본의 런처와 `agentops.py`에도 같은 보강을 주입하도록 수정.

검증:

```cmd
py -3.11 -m pytest workspace\tests\test_opencode_lig_plugin_runtime.py -q
py -3.11 -m py_compile workspace\agent_ops\agentops.py workspace\patches\existing_install_hotfix_20260709.py
```

## 2026-07-09 추가 보강: OpenCode 빠른 시작/햄스터/ocd 최종 런처

사용자 최종 확인:

- `RUN_OPENCODE_LIG.bat` 직접 실행 시 OpenCode가 빠르게 뜨고 햄스터가 표시되어야 한다.
- `cd 작업폴더` 후 `ocd`로 실행해도 OpenCode가 빠르게 뜨고 햄스터가 표시되어야 한다.
- `.opencode\plugins`는 유지해야 하며 `OPENCODE_PURE=1`로 플러그인을 끄면 안 된다.
- 원본 `opencode.json`은 유지해야 한다.
- `ocd`로 연 폴더가 작업/산출물 폴더가 되어야 한다.

최종 원인 판단:

- 지연의 직접 조합은 기존 OpenCode runtime config/data/cache 경로, 회사망 외부 fetch/update/npm/bun/proxy 대기, 플러그인 로딩 활성 상태였다.
- 플러그인 파일 자체나 Chrome CDP가 직접 원인은 아니었다.
- 햄스터 파일 위치는 `agent_ops\ui\hamster_overlay.py`인데, 런처가 VBS 또는 잘못된 경로에 의존하면 `ocd` 실행에서 누락될 수 있었다.

조치:

- `RUN_OPENCODE_LIG.bat`에서 OpenCode 실행 직전에만 `%USERPROFILE%\OpenCodeLIG_USERDATA\opencode_fast_runtime\config\data\cache` 계열로 격리한다.
- `OPENCODE_DISABLE_MODELS_FETCH`, `OPENCODE_DISABLE_AUTOUPDATE`, `OPENCODE_DISABLE_LSP_DOWNLOAD`, npm/bun registry timeout, proxy 비움 값을 OpenCode 실행 직전에 설정한다.
- `OPENCODE_PURE=1`은 금지하고 `set "OPENCODE_PURE="`만 둔다.
- `.opencode\plugins` 동기화는 유지한다.
- 햄스터는 `hamster_hidden.vbs`에 의존하지 않고 `%USERPROFILE%\OpenCodeLIG\workspace\agent_ops\ui\hamster_overlay.py`를 우선 직접 실행한다.
- `LIG_PROJECT_DIR`는 caller/ocd가 지정하면 유지하고, 없으면 `%CD%`를 쓰며, `%USERPROFILE%`, `System32`, `SysWOW64`에서 시작한 경우만 workspace로 fallback한다.
- `workspace\launch\ocd.bat`와 hotfix 생성 `ocd.bat`는 인자 없이 실행될 때 현재 폴더를 `LIG_PROJECT_DIR`로 넘긴다.
- `pending_check.py`의 `OpenCode 플러그인 런타임` 섹션에 `OpenCode fast runtime isolation`, `direct hamster launcher` 판정을 추가했다.
- `최종_패치파일.bat`를 최신 `existing_install_hotfix_20260709.py`와 기존 내장 `mss-10.2.0` wheel로 다시 생성했다.

검증:

```cmd
py -3.11 -m pytest workspace\tests\test_existing_install_hotfix.py workspace\tests\test_opencode_lig_plugin_runtime.py -q
py -3.11 -m py_compile workspace\patches\existing_install_hotfix_20260709.py workspace\agent_ops\pending_check.py workspace\agent_ops\ocd.py workspace\agent_ops\ui\hamster_overlay.py workspace\agent_ops\agentops.py
py -3.11 workspace\tests\test_launch_bats.py
```

이어받는 기준:

- 사내 PC에는 `최종_패치파일.bat` 하나만 실행한다.
- 적용 후 `RUN_OPENCODE_LIG.bat`가 느리면 `pending-check-last.md`의 `OpenCode fast runtime isolation`과 `direct hamster launcher`를 먼저 본다.
- `OPENCODE_PURE=1`, plugins 폴더 rename/삭제, `browser_cdp.py` 비활성화, `opencode.json` 최소화는 재발 원인이므로 하지 않는다.

## 2026-07-09 추가 보강: 실수 재발 방지 품질 게이트

사용자 지적:

- 이전 작업에서 파일 존재를 실제 동작 검증으로 착각했다.
- 개발본 기준으로만 판단하고 기존 설치본 변형을 충분히 재현하지 못했다.
- 위키/Obsidian/햄스터/자동저장처럼 “사용자는 그냥 쓰면 된다”는 철학이 테스트와 점검 기준에 충분히 들어가지 않았다.

조치:

- `agent_ops\quality_gate.py` 추가.
- `agentops.py quality-gate` 명령 추가.
- `tests\test_quality_gate.py` 추가.
- `existing_install_hotfix_20260709.py`가 기존 설치본에 `quality_gate.py`와 `agentops.py quality-gate` 명령을 복구하도록 보강.
- `최종_패치파일.bat`에 최신 hotfix payload를 다시 내장.

품질 게이트가 확인하는 계약:

- `RUN_OPENCODE_LIG.bat`가 fast runtime/offline timeout 방지 환경변수를 OpenCode 실행 직전에 설정한다.
- `OPENCODE_PURE=1`이 없다.
- 햄스터는 `agent_ops\ui\hamster_overlay.py`를 직접 실행한다.
- `ocd` 작업폴더가 `LIG_PROJECT_DIR`로 보존된다.
- 필수 플러그인이 존재하고 작업폴더로 동기화된다.
- `session-autosave.ts`가 Obsidian `wiki\sessions`에 append하며 `event.properties` 내부까지 추출한다.
- `memory-inject.ts`가 TUI 시작을 막지 않는 fallback + background refresh 구조다.
- Obsidian은 `obsidian_detached.vbs`로 분리 실행되어 TUI에 Electron 로그가 섞이지 않는다.
- 격리 임시 메모리에서 `remember → wiki consolidate` smoke가 성공한다.
- 최종 패치 BAT가 최신 hotfix payload와 `mss` wheel을 자체 포함한다.
- 기존 설치본에 `quality_gate.py`와 `agentops.py quality-gate` 명령이 없어도 hotfix가 복구한다.

수동 실행 명령:

```cmd
py -3.11 workspace\agent_ops\quality_gate.py --no-commands
py -3.11 workspace\agent_ops\agentops.py quality-gate --no-commands
```

출시 전 전체 게이트:

```cmd
py -3.11 workspace\agent_ops\quality_gate.py
```

검증:

```cmd
py -3.11 -m pytest workspace\tests\test_quality_gate.py -q
```

결과: 5 passed.

## 2026-07-09 추가 보강: 햄스터 멀티에이전트 표시 + 자동 자가개선 루프

사용자 지적:

- OpenCode native subagent/Task에 일을 맡기면 현재 멈춘 것인지 처리 중인지 구분하기 어렵다.
- 모델이 초반에 같은 실수를 반복하고, 한 세션 안에서는 나아져도 새 세션에서 다시 같은 시행착오를 겪는다.
- 사용자가 별도 명령을 고르지 않아도 상태 표시, 실수 기록, 해결법 승격, 다음 세션 반영이 자동으로 작동해야 한다.
- 필요하면 파일럿 자가개선 기능을 끌 수 있어야 한다.

조치:

- `hamster-status.ts`가 `task.start`, `task.end`, subagent/agent_name 계열 이벤트를 넓게 감지해 `current_status.json`에 `working/done`을 쓴다.
- 이벤트 타입만 `%LIG_DIAG_DIR%\opencode-event-types.log`에 남겨, OpenCode 이벤트명이 바뀌어도 원인 추적이 가능하게 했다. 본문/비밀값은 저장하지 않는다.
- `agent_ops\self_improvement.py` 추가.
- 기본값은 자동 ON이며, 실패/성공/도구오류/agent loop 종료를 요약형 `self_error`, `self_fix`, `self_lesson`으로 기록한다.
- `agentops.py self-improve status/on/off/report/inject` 명령을 추가했다. 명령은 제어/진단용이고, 일반 사용자는 직접 고르지 않아도 된다.
- `recall --pinned` 경로가 자가개선 지침을 최대 3개만 추가 출력하므로 다음 세션 주입이 기존 `memory-inject.ts` 흐름을 그대로 탄다.
- Obsidian 보기용 요약은 `%USERPROFILE%\OpenCodeLIG_USERDATA\memory\wiki\self-improvement\0-자가개선-대시보드.md`에 생성된다.
- `quality_gate.py`에 `hamster_subagent_status_bridge`, `self_improvement_auto_loop` 검사를 추가했다.
- 기존 설치본용 hotfix와 `최종_패치파일.bat`에도 같은 내용을 누적한다.

검증 기준:

```cmd
py -3.11 -m pytest workspace\tests\test_self_improvement.py -q
py -3.11 -m pytest workspace\tests\test_opencode_lig_plugin_runtime.py workspace\tests\test_quality_gate.py -q
py -3.11 -m py_compile workspace\agent_ops\self_improvement.py workspace\agent_ops\agentops.py workspace\agent_ops\tool_dispatch.py workspace\agent_ops\orchestrator.py workspace\agent_ops\quality_gate.py
```

운영 기준:

- 파일럿 기간에는 자가개선 ON이 기본이다.
- OFF는 새 기록/주입만 멈추며 기존 기록과 위키 요약은 삭제하지 않는다.
- 주입은 최대 3개, 각 항목은 짧은 행동지침만 포함한다.
- command_guard, approval, USERDATA 보호는 변경하지 않는다.
