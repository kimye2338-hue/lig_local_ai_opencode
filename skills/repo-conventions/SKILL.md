---
name: repo-conventions
description: 이 repo에서 코드/테스트를 작성할 때의 비자명한 규칙. agent_ops 관련 모든 구현 작업에서 사용.
---

# repo-conventions

stdlib-only Windows 한국어 환경의 오피스 자동화 런타임. 아래는 이 repo에서만 통하는
비자명한 규칙이다 — 일반 상식은 생략되어 있다.

## Workflow

1. 실행은 항상 `py -3.11` (시스템 기본은 3.14 — 맨몸 `python` 금지).
2. 테스트는 pytest 금지. 패턴: `check(label, cond, detail="")` + 실패 시 `sys.exit(1)`,
   마지막에 `ALL n CHECKS PASSED` 출력. 기존 tests/ 아무 파일이나 골라 형태를 복제.
3. 외부 자원(LLM 서버/앱/포트/인터넷) 필요 테스트: 자원 없으면
   `SKIP ... — skipped, not failed` 출력 후 **exit 0**. CI는 자원이 없는 환경이다.
4. 테스트 격리는 env 오버라이드로: `AGENTOPS_ROOT`(워크스페이스), `LIG_DIAG_DIR`(진단),
   `LIG_AUDIT_DIR`, `LIG_SCHEDULE_DIR`, `LIG_API_ENV_FILE`. 사용자 홈을 오염시키는 테스트 금지.
5. 커밋: 개별 파일 `git add`만 (`-A`/`.` 금지). 메시지는 `<TASK-ID>: 요약`.
   push 전 회귀 전체(tests/test_*.py 전부) 통과가 조건.

## Rules

- 코어(agent_ops 비어댑터부)에 외부 패키지 import 금지. 어댑터/ingest 확장은
  optional import 패턴 (`try: import X / except ImportError: X = None` + 부재 시 안내 반환).
- secret/내부 hostname을 코드·테스트·보고 어디에도 쓰지 않는다. 진단 출력은 presence flag만.
- 상태 어휘 고정: implemented / locally validated / locally validated with mock /
  input-grounded / artifact generated / static reviewed / app validation pending /
  company validation pending. mock을 real이라, 집 검증을 회사 검증이라 부르지 않는다.
- 기존 테스트가 깨지면 본인 변경을 revert하고 사실대로 보고 — 테스트 약화/삭제 금지.
- repo 루트 untracked 5개(.gitignore, docs/home-lab-status.md, logs/, tools/, validation/)
  불가침. Office 대상 코드는 2016 API 범위(MASTER_PLAN §6.2 금지 함수 목록).
- Python 파일 첫 줄 `# -*- coding: utf-8 -*-`, 한국어 사용자 문구는 완성형으로 정확하게.
