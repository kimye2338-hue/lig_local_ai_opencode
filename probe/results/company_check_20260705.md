# company_check 종합 계측 — 회사 PC (2026-07-05 10:46, 사용자 제공, sanitized)

CHECK_FULL 패키지(런타임 동봉)로 실행. **현재 빌드가 회사 PC에서 실제로 돈다는 것이 처음으로 실측 확인됨.**

## 0. 현재 빌드(agent_ops) 런타임 — ★ 핵심

| 항목 | 결과 |
|------|------|
| doctor 종료코드 | **0** (정상 로드 — capabilities/adapters/artifact/LLM 인벤토리 출력) |
| mock work E2E | **0** (파이프라인 정상 — 회의록.md 생성, quality 10 rules OK) |
| **real agent E2E** | **0** — 실제 게이트웨이로 tool-use 루프 성공 (턴 2, 도구 실행 1회, read 후 요약) |

**결론: real 파이프라인(실 게이트웨이 → tool call → 응답)이 회사 환경에서 실제로 작동.**

## 1. Gateway — 전부 성공

- coding/chat/fallback: 200 / 96·93·138ms
- function calling: accepted=True, tool_calls_present=True, finish_reason=tool_calls
- streaming True / think_on True / /models 200 (EXAONE-4.5-33B-vibe_coding_think_off)
- 512토큰 지연 7181ms (지난 3717ms보다 느림 — 부하 시간대 추정, 실사용 허용)

## 2. 앱/COM 실동작 — 전부 성공

Excel 16.0 실왕복+VBProject(매크로 주입 OK) / Outlook 16.0.0.5507 / HWP 10.0.0.14727 /
SolidWorks COM 접속 / Chrome CDP 148 / MATLAB -batch 50.6s.

## 6. 업무 시나리오 (실제 1회 끝까지) — 5/6 성공

| # | 시나리오 | 결과 |
|---|----------|------|
| ① | LLM native tool 왕복(파일 읽고 답변) | ✅ 파일 내용 반영("항목B 13.9 불합격" 정확 식별) |
| ② | Excel 매크로 주입+실행 | ✅ A1=42 |
| ③ | MATLAB -batch 계산 | ✅ mean=12.50 max=13.90 (44s) |
| ④ | HWP 문서 생성+저장 | ✅ |
| ⑤ | Outlook 받은편지함/일정 read | ✅ |
| ⑥ | **AutoCAD accoreconsole .scr** | ❌ exit 53 — **테스트 스크립트 버그**(아래) |

## ⑥ AutoCAD exit 53 — 원인 확정 (제품 결함 아님)

- **제품 어댑터 `autocad_batch.py`는 정상**: `[exe, "/i", copy_dwg, "/s", scr]` — 입력 도면을
  `/i`로 넘기고, exit 53을 "도면을 열지 못함 — /i 경로 확인"으로 이미 처리함(line 83).
- **계측기의 시나리오 `scn_autocad_script`가 `/i`를 누락**하고 `[exe, "/s", scr]`만 실행 →
  accoreconsole가 열 도면이 없어 exit 53. **즉 계측기 버그이지 제품 경로가 틀린 게 아님.**
- 조치: 시나리오를 템플릿(.dwt)을 `/i` 시드로 넘기도록 수정(제품과 동일 패턴). 실제 검증은
  재실행 또는 파일럿에서 사용자 dwg로.

## 3~5. 기타

OpenCode exe cold/warm 1.0s(빠름), 구버전 잔재 없음, autoupdate:false 표식.
Excel AccessVBOM=1/VBAWarnings=1/정책잠금 없음. 앱 경로 전부 확인(MATLAB R2024a, AutoCAD 2019,
Fluent v241, Chrome). RAM 128GB / 디스크 260GB 여유 / py3.11.3 / pywin32 True.

## 이 결과로 확정되는 것

- **어댑터 app validation 달성** → office(Excel)/outlook/matlab/hwp를 `available: True`로 전환
  (Fable 승인, 2026-07-05). solidworks는 connect만 확인(매크로 실행은 파일럿), autocad는 계측기
  버그로 미검증, fluent 미검증 → 계속 pending.
- **파일럿(P19-02)의 핵심 전제(실 파이프라인·앱 실행)가 실측으로 섰다** → 남은 건 12종 UX 실주행.
