# Offline install guide

사내(오프라인) Windows PC 설치는 두 부분이다. **A. agent_ops 업무 자동화 번들**(주 설치)과
**B. 패치된 OpenCode TUI**(선택 — TUI를 쓸 때만). 대부분의 경우 A만으로 충분하다.

## A. agent_ops 번들 — 설치는 더블클릭 한 번

1. 집/개발 PC에서 번들을 만들거나 전달받는다: `OpenCodeLIG_BUNDLE_<날짜>.zip`
   (만드는 법: `workspace-template/docs/BRING_IN_CHECKLIST.md` A단계, 또는
   `py -3.11 release\build_bundle.py`).
2. 회사 PC에서 zip을 푼다.
3. **`설치.bat` 을 더블클릭한다.** 이게 전부다. 설치기가 순서대로 알아서 한다:
   - Python 3.11 자동 탐지 (`py -3.11` → `python` → `python3.11` → `python3`)
   - 부속 라이브러리 오프라인 설치 (`pip --no-index`, 인터넷 사용 없음)
   - 프로그램 배치: `%USERPROFILE%\OpenCodeLIG\workspace`
   - 데이터 폴더 생성: `%USERPROFILE%\OpenCodeLIG_USERDATA`
   - **게이트웨이(사내 LLM) 설정** — 주소/API 키를 붙여넣으면 저장, 모르면 Enter로 건너뜀
   - 자가 진단(doctor) + **바탕화면 [AI비서] 바로가기 생성**
4. 끝. 매일 쓸 때는 **바탕화면의 [AI비서]** 를 실행한다
   (업무 시키기 / 아침 브리핑 / 주간보고 / 상태 진단 / 게이트웨이 점검 메뉴).

게이트웨이 설정을 건너뛰었다면 나중에
`%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env` 를 열어 두 값을 채우면 된다.
**이 파일은 절대 커밋/반출 금지.**

문제가 생기면: `workspace\launch\diag.bat` 실행 → `workspace\docs\RUNBOOK.md` 의 증상 표를 따른다.

## B. OpenCode TUI (선택)

최신 성공한 `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE` 아티팩트를
`Build LIG OpenCode offline package` 워크플로(main)에서 받는다.

1. 아티팩트 ZIP을 한 번 푼다.
2. 폴더에 다음이 있는지 확인: `payload/`, `workspace/`, `SHA256SUMS.txt`,
   `README_OFFLINE_INSTALL.md`, `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt`
3. `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt` → `.bat` 으로 이름 변경 후 실행.
4. 시작: `%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat`
5. 확인: `VERIFY_OFFLINE_INSTALL.bat`

TUI 설치기가 하는 일: `payload/opencode.exe` 를 `SHA256SUMS.txt` 로 certutil 검증 →
`%USERPROFILE%\OpenCodeLIG\bin\` 복사 → workspace 복사 → 실행/검증 BAT 생성 →
기존 설치는 `OpenCodeLIG_backup_%RANDOM%` 으로 백업.

### TUI 첫 실행 확인

- `Shift+Tab` → 권한 배지 ASK/AUTO 전환
- `/permission status`, `/perm status`
- 간단한 로컬 작업을 시켜 spinner 크래시가 없는지 확인

## 오프라인 제약 (양쪽 공통)

설치기는 다음을 하지 않는다:

- GitHub 클론 / npm·bun·git 실행 / 인터넷 다운로드
- PowerShell `-ExecutionPolicy Bypass`
- BAT 안 base64 페이로드 해제
