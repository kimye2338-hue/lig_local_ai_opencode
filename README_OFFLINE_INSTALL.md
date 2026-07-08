# OpenCodeLIG 오프라인 설치 패키지

이 폴더는 사내 오프라인 Windows PC에 OpenCodeLIG를 설치하기 위한 배포본입니다.
Python 3.11, Windows Terminal, Obsidian은 사용자가 별도로 설치한다는 전제입니다.

## 설치

1. 이 폴더 전체를 회사 PC로 옮깁니다.
2. `INSTALL_OFFLINE_LIG_OPENCODE.bat`를 실행합니다.
3. 설치 후 아래 파일을 실행합니다.

```text
%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat
```

검증:

```text
%USERPROFILE%\OpenCodeLIG\workspace\VERIFY_OFFLINE_INSTALL.bat
```

전체 pending 점검:

```text
점검용_전체확인.bat
```

이 파일은 설치 전 패키지 루트에서도, 설치 후 `%USERPROFILE%\OpenCodeLIG\workspace`에서도 실행할 수 있습니다.
실행 결과는 아래 파일에 저장됩니다.

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\pending_checks\pending-check-last.md
```

사용법:

```text
%USERPROFILE%\OpenCodeLIG\workspace\docs\사용법\GUIDE.md
```

## 포함된 것

- `payload\opencode.exe`: 패치된 OpenCode 실행 파일
- `workspace\`: OpenCodeLIG 런타임, 런처, 사용자 문서
- `workspace\tools\wheelhouse\`: 오프라인 Python wheel 의존성
- `userdata_seed\`: 최초 설치 시 USERDATA로 복사되는 사내 게이트웨이 설정
- `점검용_전체확인.bat`: 사내 PC에서 pending 항목을 한 번에 확인하는 보고서 생성기

설치기는 `payload\opencode.exe`의 SHA256을 확인하고, 기존 `%USERPROFILE%\OpenCodeLIG`가 있으면
백업한 뒤 새 workspace를 복사합니다. `%USERPROFILE%\OpenCodeLIG_USERDATA`의 기존 기억, 일정,
위키, 설정은 덮어쓰지 않습니다.

## 승인 모드

`Shift+Tab`은 ASK → AUTO → FULL 순서로 승인 정책을 바꿉니다. 어떤 모드에서도 위험 명령 차단은
유지됩니다.

## 주의

이 패키지는 사내 전용입니다. 게이트웨이 설정 파일이 포함되어 있으므로 외부 공유 금지입니다.
설치기는 인터넷 다운로드, GitHub clone, npm/bun 설치를 하지 않습니다.
