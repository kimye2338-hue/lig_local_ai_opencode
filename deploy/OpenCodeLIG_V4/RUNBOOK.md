# RUNBOOK — OpenCodeLIG V4 사용 설명서

모든 실행 파일은 `C:\Users\74358\OpenCodeLIG\` 바로 아래에 있습니다.
외울 것은 파일 4개뿐입니다.

| 언제 | 실행할 파일 |
|---|---|
| **매일 사용** | `RUN_OPENCODE_LIG.bat` |
| 시작이 느릴 때 (수동 안전모드) | `RUN_OPENCODE_LIG_SAFE_PURE.bat` |
| 뭔가 이상할 때 (진단) | `DIAG_OPENCODE_LIG.bat` |
| 설정이 깨졌을 때 (복구) | `APPLY_OR_REPAIR_OPENCODE_LIG.bat` |

## 1. 최초 설치 (또는 업데이트)
1. 배포 폴더(`OpenCodeLIG_V4`)에서 `INSTALL_OPENCODELIG_V4.bat.txt`의
   이름을 `INSTALL_OPENCODELIG_V4.bat`으로 바꾸고 더블클릭.
   (수동 이름 변경은 이 파일 하나뿐 — 나머지는 자동)
2. `opencode.exe`를 `C:\Users\74358\OpenCodeLIG\bin\`에 복사 (오프라인 패키지에서).
3. **별도로 전달받은** `SET_LIG_SECRET.bat`을 한 번 실행
   (사내 API 키/주소를 로컬 비밀 파일에 기록 — git에는 절대 없음).
4. `DIAG_OPENCODE_LIG.bat` 실행 → `GO` 확인.
- 업데이트도 같은 방법: 새 배포 폴더에서 INSTALL을 다시 실행하면 됩니다.
  (메모리/체크포인트는 덮어쓰지 않고, 기존 AGENTS 파일은 자동 백업됩니다.)

## 2. 매일 쓰는 법
1. `RUN_OPENCODE_LIG.bat` 더블클릭.
2. 화면에 `[OK] proxy identity : LIG generic-toolcall-rescue-v2` 가 보이면 정상.
3. OpenCode 창에서 한국어로 지시:
   `C:\...\workspace\예시.md 파일을 실제로 생성해줘. 설명 말고 파일을 만들고 경로와 요약만 답해줘.`
- 시작 모드(normal/pure)는 진단이 자동으로 정해 저장합니다. 신경 쓸 필요 없음.

## 3. 진단 결과 읽는 법 (GO/NO-GO)
`DIAG_OPENCODE_LIG.bat` 실행 후 마지막 [RESULT] 블록:

- `CORE_OK = True` : 프록시·설정·tool_calls 정상
- `FILE_CREATE_OK = True` : 파일이 **실제로** 생성됨 (고유 마커로 검증, 거짓 통과 불가)
- `STARTUP = mode:pure` : 다음 실행부터 안전모드(--pure)로 자동 시작 (정상 동작임)
- `GO` : 모두 정상 → 그냥 쓰면 됨
- `NO-GO` : 아래 5번 방법으로 리포트 전달

에러코드: 런처가 `code=10`으로 끝나면 SET_LIG_SECRET.bat을 아직 안 돌린 것입니다.

## 4. 새 세션 / 재시작 후 이어가기
- OpenCode 안에서 **"계속"** 또는 **"이어서 해줘"** 라고 입력하면
  에이전트가 `checkpoints\CHECKPOINT_LATEST.md`를 읽고 이어서 작업합니다.
- 긴 작업을 시켰다면 중간중간 "체크포인트 저장해줘"라고 말해두면 안전합니다.

## 5. 버그 리포트 보내는 법 (짧게!)
문제가 생기면 아래 3가지만 보내면 됩니다. 로그 전체는 보내지 마세요.
1. `DIAG_OPENCODE_LIG.bat` 실행 후 화면의 **[RESULT] 블록** (복사/붙여넣기)
2. 리포트 파일 경로 표시줄에 나온 파일
   (`...\OpenCodeLIG_USERDATA\diagnostics\LIG_DIAG_날짜.txt`)의 **마지막 섹션만**
3. 무엇을 하다가 문제가 생겼는지 1~2문장

## 6. 폴더 구조 (참고)
```
C:\Users\74358\OpenCodeLIG\
  RUN_OPENCODE_LIG.bat 외 실행파일 4개   <- 여기만 보면 됨
  bin\opencode.exe                       실행 바이너리
  scripts\lig_*.py                       내부 로직 (수정 금지)
  proxy\lig_toolcall_proxy.py            로컬 프록시
  secrets\lig_local.env                  사내 키 (로컬 전용, 공유 금지)
  workspace\                             작업 폴더 + AGENTS/skills/memory/checkpoints
  docs\  logs\
C:\Users\74358\OpenCodeLIG_USERDATA\
  opencode_config\opencode.proxy.json    자동 생성 설정 (직접 수정 금지)
  diagnostics\  backups\  state\         진단 리포트 / 자동 백업 / 시작모드
```
