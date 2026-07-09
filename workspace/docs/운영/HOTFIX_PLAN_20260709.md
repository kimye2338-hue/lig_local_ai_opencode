# Existing Install Hotfix 20260709 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 이미 설치된 OpenCodeLIG를 삭제하지 않고, Obsidian 자동 실행 오류 표시, `probe-gateway` 경로 누락, `mss` 오프라인 설치, 점검 BAT 위치 문제, `cd 작업폴더` 후 `ocd` 실행 시 산출물이 설치 폴더에 쌓이는 문제를 한 번에 보완한다.

**Architecture:** 패치는 기존 설치본 위에 덧씌우는 방식으로 동작한다. 사용자 데이터, 기억, 위키, API 키는 건드리지 않고, 런처와 진단 도구에 필요한 보완만 추가한다.

**Tech Stack:** Windows BAT, Python 3.11, OpenCodeLIG `agent_ops`, Obsidian, offline wheelhouse.

## Global Constraints

- 기존 `%USERPROFILE%\OpenCodeLIG_USERDATA`는 삭제하거나 초기화하지 않는다.
- 사용자가 `cd`로 들어간 폴더에서 `ocd`를 실행하면 그 폴더가 작업 기준점이어야 한다.
- 작업 기준 폴더에 초기 설정이 없으면 자동으로 만든다.
- 사용자가 요청해 만든 산출물은 설치 폴더가 아니라 작업 기준 폴더 아래에 정리한다.
- Obsidian은 OpenCode 시작 시 자동으로 떠야 한다.
- Obsidian의 인터넷 업데이트 실패 로그는 OpenCode TUI에 겹쳐 보이면 안 된다.
- 오프라인 환경을 전제로 하며, `mss`는 wheel 파일이 있을 때만 설치한다.
- `.bat`와 `.bat.txt`는 CRLF와 `chcp 65001`을 유지한다.
- 게이트웨이 URL, API 키, 라우트, 모델명은 수정하지 않는다.

---

### Task 1: Obsidian 자동 실행 분리

**Files:**
- Modify: `workspace/patches/existing_install_hotfix_20260709.py`
- Modify by generated patch target: `%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat`
- Create by generated patch target: `%USERPROFILE%\OpenCodeLIG\workspace\launch\obsidian_detached.vbs`

**Interfaces:**
- Consumes: installed workspace path `%USERPROFILE%\OpenCodeLIG\workspace`
- Produces: `obsidian_detached.vbs` and patched launcher block

- [ ] Add a test that copies `workspace/RUN_OPENCODE_LIG.bat` into a temporary install tree, runs the hotfix, and asserts the launcher calls `wscript ...obsidian_detached.vbs`.
- [ ] Verify the test fails before implementation because the launcher still uses direct `start "" "%OBSEXE%"`.
- [ ] Implement `patch_run_launcher()` in the hotfix script.
- [ ] The patched launcher must still seed the wiki vault every start.
- [ ] The patched launcher must auto-open Obsidian unless `LIG_AUTO_WIKI=0`.
- [ ] The patched launcher must open Obsidian through a detached VBS helper so Electron logs do not write into the OpenCode console.

### Task 2: `probe-gateway` command wrapper

**Files:**
- Modify: `workspace/patches/existing_install_hotfix_20260709.py`
- Create by generated patch target: `%USERPROFILE%\OpenCodeLIG\bin\probe-gateway.bat`
- Create by generated patch target: `%USERPROFILE%\OpenCodeLIG\bin\probe_gateway.bat`
- Create by generated patch target: `%USERPROFILE%\OpenCodeLIG\bin\gateway-smoke.bat`

**Interfaces:**
- Consumes: installed `workspace\launch\probe-gateway.bat` and `workspace\launch\gateway-smoke.bat`
- Produces: wrapper BAT files under installed `bin`

- [ ] Add a test that runs the hotfix on a temporary install tree and checks all three wrapper BATs exist.
- [ ] Verify the test fails before implementation only if wrappers are missing or invalid.
- [ ] Keep wrappers ASCII-only on command/path lines.
- [ ] Use `chcp 65001` and call the exact installed launcher path.

### Task 3: User working-folder launch mode

**Files:**
- Modify: `workspace/patches/existing_install_hotfix_20260709.py`
- Modify by generated patch target: `%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat`
- Create by generated patch target: `%USERPROFILE%\OpenCodeLIG\bin\ocd.bat`

**Interfaces:**
- Consumes: caller's current directory as `%CD%`
- Produces: workspace-local `.opencode`, `.agent-memory`, `agent_ops\results`, and run metadata in the caller's current directory

- [ ] Add a test that runs the hotfix against a temporary install tree and checks that `RUN_OPENCODE_LIG.bat` preserves the caller directory in `LIG_PROJECT_DIR`.
- [ ] Verify the test fails before implementation because the launcher currently executes `cd /d "%AGENTOPS_HOME%"`.
- [ ] Patch the launcher so program files are read from `%AGENTOPS_HOME%` but OpenCode is launched from `%LIG_PROJECT_DIR%`.
- [ ] If the current directory is the install workspace, use it as before.
- [ ] If the current directory is any other folder, create minimal local folders for project settings and outputs.
- [ ] Add or refresh `%USERPROFILE%\OpenCodeLIG\bin\ocd.bat` so typing `ocd` from any folder calls the installed launcher without changing the user's current directory first.

### Task 4: Offline `mss` install and diagnostic wording

**Files:**
- Modify: `workspace/patches/existing_install_hotfix_20260709.py`
- Modify by generated patch target: `%USERPROFILE%\OpenCodeLIG\workspace\agent_ops\pending_check.py`
- Modify by generated patch target: `%USERPROFILE%\OpenCodeLIG\workspace\agent_ops\adapters\__init__.py`

**Interfaces:**
- Consumes: optional `patch_wheels\mss-*.whl` or installed `workspace\tools\wheelhouse\mss-*.whl`
- Produces: best-effort `mss` install and clearer pending-check report

- [ ] Add a syntax test for `existing_install_hotfix_20260709.py`.
- [ ] Verify the test catches the nested string problem in the pending-check injection block.
- [ ] Fix the injection block so it compiles.
- [ ] Keep behavior: if `mss` wheel exists, install it offline; if not, keep Pillow/PowerShell fallback and report that clearly.

### Task 5: Root check BAT copy and local verification report

**Files:**
- Modify: `workspace/patches/existing_install_hotfix_20260709.py`
- Modify: `PATCH_EXISTING_INSTALL_LIG_OPENCODE_20260709.bat.txt`
- Create/update by generated patch target: `%USERPROFILE%\OpenCodeLIG\점검용_전체확인.bat`
- Create/update by generated patch target: `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\pending_checks\pending-check-last.md`

**Interfaces:**
- Consumes: installed `workspace\점검용_전체확인.bat`
- Produces: root-level check BAT and one final report path

- [ ] Add a test that root check BAT is copied.
- [ ] Normalize the patch BAT to CRLF.
- [ ] Run a temporary-install hotfix smoke.
- [ ] Run `py -3.11 -m py_compile workspace\patches\existing_install_hotfix_20260709.py`.
- [ ] Record results in `workspace/docs/작업이력` or existing operation notes.
