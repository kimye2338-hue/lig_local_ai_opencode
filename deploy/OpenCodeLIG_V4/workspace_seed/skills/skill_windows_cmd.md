# skill_windows_cmd — 안전한 Windows CMD 명령

## 언제
bash 도구로 명령을 실행해야 할 때 (이 PC의 셸은 CMD).

## 규칙
- 경로는 항상 큰따옴표: `dir "C:\Users\74358\OpenCodeLIG\workspace"`.
- 존재 확인: `if exist "경로" echo YES` / 목록: `dir /b "폴더"`.
- 파일 내용 확인은 bash 대신 **read 도구** 사용 (인코딩 안전).
- 인코딩: 한글 깨짐 발생 시 `chcp 65001` 후 재시도.
- Python 실행: `python "스크립트경로"` (인자도 각각 따옴표).

## 금지
- PowerShell `-ExecutionPolicy Bypass`, `-EncodedCommand`, Invoke-Expression.
- `rm -rf`, `del /s /q`, `rmdir /s`, `format` 등 대량 삭제.
- `cmd /k python "경로"` 패턴 (따옴표 깨짐 이력 있음).
- 리눅스 전용 문법 가정 (grep/sed 대신 도구 사용).
