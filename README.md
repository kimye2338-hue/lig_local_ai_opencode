# OpenCodeLIG — 사내 오프라인 AI 업무비서

사내 망분리 윈도우 PC용 한국어 AI 업무비서. 자세한 사용법은
**`workspace/docs/사용법/GUIDE.md` 하나면 됩니다.** 새 세션(AI)으로 이어작업할 땐 `CLAUDE.md`.

## 회사에 반입할 파일 (3개)

| zip | 내용 | 필수 |
|---|---|---|
| **LIG_OPENCODE_설치_최종.zip** | 프로그램 본체(opencode.exe·설정·전 기능). 압축 풀고 `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt`를 `.bat`으로 개명 후 실행 | 필수 |
| **반입파일_따로받는것.zip** | 선택 기능 wheel(PDF/워드 읽기·Office 생성·앱조작) 오프라인 설치본 + 링크 안내 | 선택 |
| **WindowsTerminal_오프라인설치.zip** | Windows Terminal 최신본(한글 입력 매끄럽게) + 의존성 + 설치 스크립트 | 선택 |

## 설치 순서 (2번만 열면 끝)

1. `LIG_OPENCODE_설치_최종.zip` 풀기 → `INSTALL_...bat` **한 번 실행** → 설치 자동 완료:
   게이트웨이 무설정 연결 + **오프라인 의존성(wheel) 자동 설치**(PDF 읽기·진짜 Office 파일·화면 OCR).
2. `%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat` **실행** → 바로 사용.

- 확인(선택): `python agent_ops\agentops.py deps` (뭐가 준비됐는지 한눈에)
- 옵시디언·Windows Terminal은 사내 기설치 가정(없으면 GUIDE 참고). Terminal을 기본으로 지정하면 한글 입력이 매끄럽다.
- wheel 자동설치가 일부 실패해도 설치 자체는 성공하며, `launch\install-tools.bat`로 재시도할 수 있다.

## 폴더 한눈에

- `payload/opencode.exe` — 프로그램 본체
- `workspace/` — 런타임·문서·런처 (설치되면 `%USERPROFILE%\OpenCodeLIG\workspace`)
- `workspace/docs/사용법/GUIDE.md` — **사용자 매뉴얼(이거 하나)**
- `CLAUDE.md` — 새 AI 세션이 전체를 파악하는 진입 문서

## 라이선스 / 불변 규칙

- 포함/반입 소프트웨어는 전부 무료(오픈소스/무료 상용). 유료 없음.
- LLM 설정(게이트웨이/키/라우트/모델)과 USERDATA 기억은 사용자 권한 — 함부로 변경 금지.
