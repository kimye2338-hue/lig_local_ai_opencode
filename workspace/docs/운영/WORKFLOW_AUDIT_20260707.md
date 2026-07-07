# 전수 워크플로우 감사 (2026-07-07, Fable 직접 검토)

목적: 지금까지 추가·보유한 모든 기능이 **실사용 워크플로우(입력→도구탐색→호출→
생각→확인→행동)에서 원활·효율적으로 작동하는지**, 그리고 **활동/대화가 자동으로
Obsidian 위키에 가독성 좋게 정리되고, 기억이 쌓여도 모델 효율이 저하되지 않는지**
점검하고, 부족분을 구조로 반영.

## 1. 실행 계층 (두 층으로 명확)

- **주 에이전트(OpenCode TUI, `.opencode/agents/agent.md`)** — bash + `agentops.py *` 허용.
  사용자 요청을 받아 아래 CLI로 오케스트레이션. (build/plan/agent 3모드, AUTO=Shift+Tab)
- **run_agent_loop(`agentops work|agent --mode real`)** — 게이트웨이 LLM + 20개 툴
  (파일 read/write/replace/search, 브라우저 CDP snapshot/click/…, project_info, remember).
  실제 내용 생성·파일·브라우저 작업 수행. 약한 모델 보호로 툴 20개/스키마 7.8KB 상한.
- **어댑터 10종** — office/hwp/solidworks/autocad/matlab/fluent/outlook/browser/
  ocr_screen/desktop_ui. 산출물 실행/앱 제어 경로.

## 2. 대표 워크플로우 점검

### A. "이 CSV로 보고서·PPT·엑셀 만들어줘" — ✅ 원활
입력 인제스트(CP949 폴백) → plan → **기억+공식API+디자인+한국비즈니스 주입** →
LLM이 내용 생성(품질검사) → `.md` 산출 → 주 에이전트가 `report-xlsx`/`office-doc`/
`report-html`로 진짜 .xlsx/.pptx/HTML 생성 → 보고 → **작업 자동 기억화**.
- 근거 주입으로 환각 대신 실제 API/서식, 디자인 원칙 적용. 완료 시 자동 정리.

### B. "사내 포털 이번 주 공지 요약" — ✅ (OCR 갭 보완됨)
chrome-debug → `agent` 루프가 CDP(snapshot/read_web_page/spa_map/click)로 읽고 요약.
DOM으로 안 되면 → **`agentops ocr`(신규 CLI)로 화면을 읽어** 판단. (이번에 CLI 노출로
"막힐 때 화면 보기" 흐름을 실제 호출 가능하게 보완.)

### C. 반복 업무 자동화 — ✅
성공 직후 `routine save "<이름>"` → 다음부터 `routine run`으로 LLM 없이 검증된
도구 호출 재생(command_guard 통과). 결정적 작업에 효율적.

### D. 데스크톱 앱 — ✅ 커버
Excel/HWP/Outlook/SolidWorks=COM, AutoCAD/MATLAB/Fluent=배치, COM 없는 앱=desktop_ui
(Windows-Use, 반입 후). 문서는 Office 없이도 office_writer로 생성 가능.

## 3. 기억·위키 자동정리 & 효율 (핵심)

### 자동 정리 파이프라인 (이번에 완성)
작업 완료 → **`add_activity`(자동 적재, 이번 추가)** → `add_memory_event` →
**`consolidate_quietly()`(매 기록마다 위키 갱신)** → 위키 주제 페이지(.md = Obsidian vault).
- 명시 교훈은 `remember`, 실패는 `log-failure`, 아침 `memorycheck`가 consolidate+lint+
  지식책 재생성. 즉 **사용자 개입 없이 활동·교훈이 Obsidian 위키로 정리**된다.
- 위키는 `[[백링크]]`·별칭·모순후보·반복확인 신호로 가독성 있게 정리(복습/회상용).
- Obsidian 의미검색은 Smart Connections(선택 반입)로 강화 가능.

### 기억이 쌓여도 효율 저하 없는 구조 (검증)
- **주입은 유계(bounded)**: 회상 주입 = 고정 규칙(pinned ≤5) + recall(≤8, 각 500자) +
  **증류된 위키 1페이지 발췌** + 프로필 + (관련 시) API/디자인/도메인(각 캡). 기억이
  수천 건이어도 주입 총량은 사실상 고정 → 모델 컨텍스트/정확도 유지.
- **증류(compounding)**: 개별 사건이 아니라 40개 주제 페이지로 압축돼 회상됨(Karpathy 위키).
- **규칙 보호 캡(이번 추가)**: active 500 초과 시 **가치 낮은 활동부터** 아카이브 —
  사용자 규칙/선호(source=user)·high는 활동 홍수에도 생존(`_protect_rank`). 검증:
  활동 600건 부어도 규칙 active 유지.
- **회상 우선순위**: recall 은 사용자(+3)·high(+2)·규칙/교훈(+1) 가점, activity 가점 0 →
  규칙이 항상 상위. 검증: 활동 추가 후에도 recall 최상위 = 사용자 규칙.

## 4. 이번 검토로 반영한 구조 개선

1. **작업 자동 기억화**(`memory_manager.add_activity` + `cmd_work` 연결) — 활동이 자동으로
   위키에 정리(사용자 요구 #1). 간결·같은날 중복 방지.
2. **우선순위 인식 캡**(`_protect_rank`) — 자동 적재가 사용자 규칙을 밀어내지 않게 보호.
3. **화면 OCR CLI 노출**(`agentops ocr`) — "막힐 때 화면 보기"를 실제 워크플로우에서 호출 가능.
- 회귀: 기억/위키/디스패치/작업 테스트 green + 신규 test_memory_activity 7 green.

## 5. 남은 설계 판단(의도적)

- **전체 대화 원문**은 자동 저장하지 않는다 — 작업 outcome + 명시 교훈이 올바른 단위
  (원문 통째 저장은 위키를 오염시키고 회상 효율을 떨어뜨림). 필요한 통찰은 remember 로.
- **run_agent_loop 20툴 예산 유지** — office/report/ocr 등은 CLI(주 에이전트 bash)로 노출해
  약한 모델의 툴 호출 정확도를 지킨다(툴 스키마 비대화 방지). CLI 경로로 충분히 도달 가능.

## 결론

핵심 워크플로우는 입력→근거주입→도구→생성→검증→보고→**자동 정리**까지 원활히 돈다.
기억은 자동으로 Obsidian 위키에 정리되고, 유계 주입+증류+규칙보호로 **많이 쌓여도 효율
저하가 구조적으로 방지**된다. 이번에 자동 적재·규칙보호·OCR 노출 3가지 갭을 메웠다.
