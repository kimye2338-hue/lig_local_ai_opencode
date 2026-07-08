# OpenCodeLIG — 사내 오프라인 AI 업무비서

사내 망분리 윈도우 PC용 한국어 AI 업무비서. 자세한 사용법은
**`workspace/docs/사용법/GUIDE.md` 하나면 됩니다.** 새 세션(AI)으로 이어작업할 땐 `CLAUDE.md`.

## 회사에 반입할 파일

프로그램 본체는 **이 배포 패키지 1개**면 끝입니다(라이브러리·wheel 모두 포함). 나머지 3개는
사용자가 별도로 반입/설치하는 사전 준비물입니다.

| 파일 | 내용 | 구분 |
|---|---|---|
| **LIG_OPENCODE 배포 패키지** | 프로그램 본체(opencode.exe·설정·런타임·wheelhouse 전부 포함). 폴더 안 `INSTALL_OFFLINE_LIG_OPENCODE.bat` 한 번 실행 | 이 패키지(필수) |
| **Python 3.11.3** | 런타임 실행 및 wheel 설치용 | 사용자가 별도 설치 |
| **Obsidian** | 기억 위키를 그래프/백링크로 보기 | 사용자가 별도 설치 |
| **Windows Terminal** | 한글 입력을 매끄럽게 쓰기 위한 터미널(권장) | 사용자가 별도 설치 |

## 설치 순서 (2번만 열면 끝)

1. `LIG_OPENCODE_배포패키지` 풀기 → `INSTALL_...bat` **한 번 실행** → 설치 자동 완료:
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
