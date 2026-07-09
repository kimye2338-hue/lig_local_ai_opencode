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

