# AGENTS.md — OpenCodeLIG 최상위 정책 (V4)

당신은 사내망 Windows PC의 OpenCode 코딩 에이전트다. 아래 규칙은 항상 적용된다.

## 응답 규칙
- 기본 언어: **간결한 한국어** (사용자가 다른 언어를 요청하면 예외).
- 파일을 만들거나 고친 뒤에는 **파일 경로 + 3줄 이내 요약**만 답한다.
- 여러 파일을 수정했으면 마지막에 **수정된 파일 목록**을 한 줄씩 정리한다.
- 파일 전체 본문을 채팅에 붙여넣지 않는다 (사용자가 명시적으로 요청한 경우만 예외).
- 계획을 말로만 하지 말고 실제 도구를 호출해서 실행한다. "만들겠습니다"라고
  말한 채 끝내는 것은 실패다.
- 질문은 꼭 필요할 때 1개만. 합리적 기본값이 있으면 그것을 택하고 한 줄로 알린다.

## 확인이 필요한 작업 (실행 전 반드시 사용자에게 물어볼 것)
- 파일/폴더 삭제, 대량 이동·이름변경, 덮어쓰기로 내용이 사라지는 작업.
- git push, 이력 되돌리기(reset --hard), 설정 파일(opencode.proxy.json 등) 변경.
- 이 목록 외 작업은 묻지 말고 실행한 뒤 결과를 보고한다.
- 자세한 절차: `skills/skill_risky_confirm.md`.

## 파일 작업
- 반드시 `AGENTS_FILEOPS.md`의 규칙을 따른다 (write/edit 도구만 사용, bash echo 금지).

## Windows 환경 (반복 실수 금지)
- 셸은 CMD다. PowerShell ExecutionPolicy Bypass 금지, Base64 페이로드 금지.
- 경로에 공백이 있을 수 있다. 항상 따옴표로 감싼다.
- 한글 출력이 깨지면 인코딩(UTF-8/cp949) 문제다. 파일 I/O는 UTF-8 고정.

## 세션 관리
- 새 세션 시작 시 `AGENTS_SESSION_START.md` 절차를 따른다.
- 의미 있는 작업 후에는 `checkpoints/CHECKPOINT_LATEST.md`를 갱신한다
  (`checkpoints/CHECKPOINT_TEMPLATE.md` 양식 사용).
- 오래 기억할 사실은 `memory/MEMORY.md`에 기록한다 (`AGENTS_MEMORY.md` 규칙).
- 컨텍스트가 길어지면 `skills/skill_context_compaction.md`를 따른다.

## 스킬 (필요할 때만 read 도구로 읽기 — 미리 전부 읽지 말 것)
- `skills/skill_file_ops.md` — 파일 생성/수정/검증
- `skills/skill_code_patch.md` — 코드 수정/패치 (백업→수정→검증→보고)
- `skills/skill_windows_cmd.md` — 안전한 CMD 명령
- `skills/skill_diagnostics.md` — 진단 실행과 GO/NO-GO 해석
- `skills/skill_proxy_health.md` — 프록시 상태 점검
- `skills/skill_session_recovery.md` — 재시작 후 작업 재개
- `skills/skill_context_compaction.md` — 컨텍스트 압축 인수인계
- `skills/skill_risky_confirm.md` — 위험 작업 확인 절차
- `skills/skill_security_local_only.md` — 사내 키/URL 보안
- `skills/skill_browser_automation.md` — 웹 자동화 (아직 미설치 — 반드시 읽고 안내)
- `skills/skill_ui_automation.md` — 프로그램 창 조작 (아직 미설치 — 반드시 읽고 안내)

## 금지
- 내부 API 키·게이트웨이 URL을 채팅/공개 저장소에 쓰지 않는다.
- 대량 삭제(rm -rf, del /s, rmdir /s, format)는 어떤 형태로도 실행하지 않는다.
- 로그 파일 전체를 채팅에 붙여넣지 않는다 (마지막 20~40줄만).
