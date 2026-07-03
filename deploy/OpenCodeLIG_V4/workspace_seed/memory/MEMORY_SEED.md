# MEMORY.md — OpenCodeLIG 지속 메모리

(규칙: AGENTS_MEMORY.md. 짧은 불릿 + 날짜. 비밀 금지, 로그 원문 금지.)

## 검증된 환경 사실
- [2026-07] 프로젝트 루트: `C:\Users\74358\OpenCodeLIG`, 작업 폴더: `...\workspace`.
- [2026-07] OpenCode는 로컬 프록시 `http://127.0.0.1:8765/v1` 를 통해서만 동작한다
  (직접 게이트웨이 연결 시 tool_calls 미지원 → 파일이 실제로 안 만들어짐).
- [2026-07] 이 빌드의 headless 문법: `opencode.exe run --pure --auto -m lig-proxy/ai_infra_llm_api "프롬프트"`.
  `-q` 옵션은 **없다** (쓰면 help + returncode 1).

## 반복 실패와 원인 (다시 하지 말 것)
- [2026-07] `cmd /k python "경로"` 로 내부 실행 → 따옴표 깨짐. 반드시
  `[sys.executable, str(path)]` 리스트 형태 사용.
- [2026-07] subprocess 출력 기본 cp949 디코드 → UnicodeDecodeError. 항상
  `encoding="utf-8", errors="replace"`.
- [2026-07] 진단에서 "파일이 존재함"만으로 성공 판정 → 기존 파일 때문에 거짓 통과.
  반드시 고유 파일명 + 마커 내용으로 판정.
- [2026-07] 로컬 플러그인이 하나라도 있으면 시작이 ~45초 지연
  (분류: any_local_plugin_or_plugin_runtime_slow). 기본 모드는 --pure.

## 사용자 선호
- 간결한 한국어 답변. 파일 경로 + 요약만. 전체 본문 출력 금지.
