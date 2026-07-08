# OpenCodeLIG 장애 대응표

먼저 아래 명령으로 현재 상태를 확인합니다.

```bat
cd %USERPROFILE%\OpenCodeLIG\workspace
python agent_ops\agentops.py doctor
```

진단 파일 위치:

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics
```

## 빠른 대응

| 증상 | 확인할 것 | 대응 |
|---|---|---|
| LLM 응답 없음 | `diagnostics\runtime-last.json`, `lig-api.env` | 주소/API 키 확인 → `doctor` 재실행 → 필요 시 `launch\probe-gateway.bat` |
| OpenCode가 안 뜸 | 설치 파일, payload 해시 | `python agent_ops\agentops.py verify` 실행. 설치본에 `VERIFY_OFFLINE_INSTALL.bat`가 있으면 함께 확인 |
| 한글이 깨짐/밀림 | 실행 경로, 터미널 | `RUN_OPENCODE_LIG.bat` 또는 `launch\*.bat`로 실행. Windows Terminal 권장 |
| 문서 읽기/Office 생성 기능이 안 됨 | 선택 wheel 반입 상태 | `python agent_ops\agentops.py deps` 확인 후 필요한 wheel 반입 |
| Obsidian이 안 열림 | `tools\Obsidian\Obsidian.exe` | 없으면 탐색기로 위키 폴더만 열리는 것이 정상. 포터블 Obsidian을 해당 위치에 배치 |
| 작업이 멈춘 듯함 | `watch`, audit, results | `python agent_ops\agentops.py watch` → 멈춤이면 `doctor` → 더 작은 요청으로 재시도 |
| 일정이 이상함 | schedule 저장 폴더와 `.bak` | `python agent_ops\agentops.py schedule list --when all` 후 백업 복구 |
| 앱 프로세스가 남음 | Excel/HWP/CAD 프로세스 | 작업관리자에서 잔류 프로세스 종료. 원본 대신 사본/산출물 사용 여부 확인 |
| 디스크가 부족함 | `agent_ops\results` 크기 | 오래된 `results\artifacts\<run_id>` 정리. USERDATA 기억/일정은 삭제 금지 |

## 주요 위치

| 항목 | 위치 |
|---|---|
| 채팅 실행 | `%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat` |
| 번호 메뉴 | `%USERPROFILE%\OpenCodeLIG\workspace\launch\menu.bat` |
| 설정 | `%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env` |
| 기억/위키 | `%USERPROFILE%\OpenCodeLIG_USERDATA\memory` |
| 진단 | `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics` |
| 감사 로그 | `%USERPROFILE%\OpenCodeLIG_USERDATA\audit` |
| 산출물 | `%USERPROFILE%\OpenCodeLIG\workspace\agent_ops\results` |

## 기본 원칙

- USERDATA 폴더는 삭제하지 않습니다.
- `lig-api.env` 값은 화면 공유, 메일, 커밋에 노출하지 않습니다.
- 원본 업무 파일은 가능하면 직접 수정하지 말고 사본이나 새 산출물로 작업합니다.
- 같은 문제가 반복되면 해결 방법을 `기억해: ...`로 남겨 다음 작업에 반영합니다.
