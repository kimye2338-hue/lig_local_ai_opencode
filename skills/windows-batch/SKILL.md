---
name: windows-batch
description: 이 repo에서 .bat 런처를 만들거나 수정할 때의 인코딩/구조 규칙. 한글 Windows에서 조용히 깨지는 함정 모음.
---

# windows-batch

한국어 Windows에서 BAT가 조용히 깨지는 지점을 막는 규칙.

## Workflow

1. 파일 형식: **UTF-8 no BOM + CRLF**. LF로 저장된 BAT는 한글 출력/라벨에서 깨질 수 있다.
2. 첫 줄부: `@echo off` → `chcp 65001 >nul` → `set PYTHONUTF8=1` →
   `set PYTHONIOENCODING=utf-8`. 한글 경로 참조는 반드시 chcp 이후 라인에.
3. Python 실행 전 guard 2단: `where py` 확인 → `py -3.11 --version` 확인,
   실패 시 한 줄 안내 + `exit /b 2` (조용한 실패 금지).
4. 스크립트 위치 기준 상대 경로는 `%~dp0` 사용 (더블클릭 시 CWD가 다르다).
5. 기존 `workspace-template/launch/*.bat` 하나를 열어 형태를 복제하는 것이 가장 안전.

## Rules

- `PowerShell -ExecutionPolicy Bypass` 금지 (보안 정책·백신 오탐).
- base64 임베드/자가압축해제 BAT 금지.
- 사용자 확인이 필요한 동작(schtasks 등록, 삭제)은 실행 전 명령을 출력하고 y 입력을 받는다.
