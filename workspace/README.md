# OpenCodeLIG workspace (프로그램 본체)

이 폴더가 프로그램 본체다. 오프라인 패키지에서 아래로 설치된다:

```
%USERPROFILE%\OpenCodeLIG\workspace
```

## 폴더 구성

- `agent_ops/` — 파이썬 런타임(비서의 두뇌·도구·기억·어댑터). 진입점 `agent_ops/agentops.py`.
  - `knowledge/` — 공식 API·디자인·도메인 근거 코퍼스(생성 시 자동 주입)
- `.opencode/` — OpenCode용 로컬 커맨드·에이전트·플러그인
- `launch/` — `.bat` 런처(항상 이걸로 실행 — 한글/UTF-8·경로 보장)
- `docs/` — 문서. **사용법은 `docs/사용법/GUIDE.md` 하나면 된다.**
- `tests/` — 테스트
- `tools/` — 오프라인 반입 바이너리(Obsidian·OCR 엔진 등)
- `RUN_AGENTOPS_*.bat.txt` — 보조 런처(쓰려면 `.bat`으로 이름 변경)

## 처음이라면

- 사용법: `docs/사용법/GUIDE.md` (설치·사용·기능·문제해결 전부)
- 운영/장애: `docs/사용법/RUNBOOK.md`
- 개발 인계: `docs/운영/AI_HANDOFF.md`

## 규칙

- 런타임 파일은 여기, 맥락/설명은 `docs/`에. 옛 리뷰 프롬프트 묶음이나 실험 설치기는 넣지 않는다.
- LLM 설정(게이트웨이/키/라우트/모델)은 사용자 권한 — `USERDATA\secrets\lig-api.env` 하나로 관리.
