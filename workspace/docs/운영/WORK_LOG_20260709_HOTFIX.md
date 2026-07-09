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
