# RUNBOOK — OpenCodeLIG 사용 설명서

## 한눈에 보기
- **매일은 이것만 실행**: `RUN_OPENCODE_LIG.bat`
- **문제 생기면 이것만 실행**: `DIAG_OPENCODE_LIG.bat`
- **GO 가 나오면**: 그냥 쓰면 됩니다.
- **NO-GO 가 나오면**: 화면의 [보내기] 블록만 복사해서 전달하세요.

모든 실행 파일은 `C:\Users\74358\OpenCodeLIG\` 바로 아래, 딱 4개입니다.

| 언제 | 실행할 파일 |
|---|---|
| **매일 사용** | `RUN_OPENCODE_LIG.bat` |
| 시작이 느릴 때 (수동 안전모드) | `RUN_OPENCODE_LIG_SAFE_PURE.bat` |
| 뭔가 이상할 때 (진단) | `DIAG_OPENCODE_LIG.bat` |
| 설정이 깨졌을 때 (복구) | `APPLY_OR_REPAIR_OPENCODE_LIG.bat` |

## 1. 최초 설치 (또는 업데이트)
1. 배포 폴더에서 `INSTALL_OPENCODELIG_V4.bat.txt` → 이름을 `.bat`으로 바꿔 더블클릭.
   (직접 이름을 바꾸는 파일은 이것 하나뿐입니다.)
2. 설치가 끝나면 화면의 **준비 상태 점검**에 [해야함] 항목이 나옵니다:
   - `opencode.exe` 복사 (오프라인 패키지 → `OpenCodeLIG\bin\`)
   - `SET_LIG_SECRET.bat` 1회 실행 (별도 전달 파일 — 실행 후 삭제 권장)
3. `DIAG_OPENCODE_LIG.bat` 실행 → **GO** 확인.
- 업데이트도 동일: 새 배포 폴더에서 INSTALL 재실행. 메모리/체크포인트는 보존되고,
  예전 실행 파일들은 자동으로 `backups\deprecated_*` 폴더로 치워집니다.

## 2. 매일 쓰는 법
1. `RUN_OPENCODE_LIG.bat` 더블클릭.
2. 상태판에 `프록시: 정상 / 설정: 정상 / 비밀키: 로드됨` 이 보이면 준비 완료.
3. 한국어로 그냥 지시하세요:
   - "메모.md 파일 만들어줘"
   - "이 코드 고쳐줘" / "수정한 파일만 요약해줘"
   - "**계속**" ← 지난번 하던 작업을 이어갑니다
   - "진단 돌리고 뭐가 문제인지 알려줘"
- 시작 모드(normal/안전모드)는 진단이 자동으로 정합니다. 안전모드(SAFE_PURE)여도
  기능 손실은 없습니다 — 신경 쓰지 않아도 됩니다.

## 3. 진단 결과 읽는 법
[RESULT] 아래 [설명] 섹션이 한국어로 원인과 **다음 할 일**을 알려줍니다. 요약:
- `CORE_OK=True` : 프록시/설정/도구호출 경로 정상.
- `FILE_CREATE_OK=True` : 파일이 **실제로** 만들어졌고 내용까지 검증됨.
- `STARTUP=mode:pure` : 안전모드 사용 중 — 정상이며 기능 손실 없음.
- `GO` : 사용 가능. / `NO-GO` : [보내기] 블록만 복사해 전달.

## 4. 자주 겪는 문제와 즉시 해결
| 증상 | 해결 |
|---|---|
| "비밀 파일이 없습니다" (코드 10) | `SET_LIG_SECRET.bat` 1회 실행 |
| "opencode.exe 가 없습니다" (코드 2) | 오프라인 패키지에서 `bin\`에 복사 |
| "예전 프록시가 포트 사용 중" (코드 4) | 떠 있는 프록시 콘솔 창 닫고 재실행 |
| "Python 을 찾지 못했습니다" | 화면 안내대로 `set LIG_PYTHON_EXE=...` 지정 |
| 시작이 느림 | `RUN_OPENCODE_LIG_SAFE_PURE.bat` 사용 (기능 동일) |
| 파일 생성 실패 (CORE는 정상) | DIAG 후 [보내기] 블록 + 리포트 마지막 섹션 전달 |

## 5. 버그 리포트 보내는 법
`DIAG_OPENCODE_LIG.bat` 실행 → 화면 맨 아래 **[보내기] 블록 하나만** 복사해서
전달하면 됩니다. 더 필요하면 리포트 파일
(`OpenCodeLIG_USERDATA\diagnostics\LIG_DIAG_날짜.txt`)의 **마지막 섹션만** 추가.
로그 전체는 보내지 마세요.

## 6. 앞으로 추가될 기능 (웹/화면 자동화)
"홈페이지에서 찾아줘", "이 창에서 버튼 눌러줘" 같은 기능은 **선택 모듈**로
준비 중입니다 (`docs\AUTOMATION_ROADMAP.md`). 지금 요청하면 에이전트가 솔직하게
"아직 준비 중"이라고 답하고 가능한 대안을 제시합니다. 모듈이 설치되어도
지금의 파일 작업 기능은 그대로 유지됩니다.

## 7. 폴더 구조 (참고 — 몰라도 사용에는 지장 없음)
```
OpenCodeLIG\            실행 파일 4개 + bin\ scripts\ proxy\ secrets\ workspace\ docs\ logs\
OpenCodeLIG_USERDATA\   자동 생성 설정/진단 리포트/백업/상태 (직접 수정 금지)
```
