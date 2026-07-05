# P00-03 — 회사 real-mode 실측 팩 (function calling 판정 + agent 실동작 + 기동 시간)

| 항목 | 값 |
|------|-----|
| 단계 | P0 (실측 — gateway 개통 후 최고 가치 방문) |
| 담당 | **human (사용자)** — 실행/반출. 결과 분석·후속 task화는 fable |
| 선행 | 없음 (gateway 3라우트 200 확인됨 — probe/results/ r3) |
| 환경 | COMPANY |

## 목표
gateway가 열렸으므로, 다음 방문 한 번으로 남은 3대 미지수를 실측한다:
① OpenAI function calling 지원 여부(런타임 경로 결정), ② EXAONE의 agent loop
실동작/tool-call 원문(파서 보강 입력), ③ 강화 런처의 기동 시간 개선 판정.

## 절차
`plan/NEXT_ONSITE.md`의 목록을 그대로 수행하고 결과물을 반출한다.

## 결과가 결정하는 것
- openai_tools 지원 → P11-01/P11-02는 native tools 경로를 1차로 측정
  (미지원 → 현행 텍스트 파싱 경로 유지)
- real agent 스모크 성공 → P19 파일럿의 리스크 대폭 감소 / 실패 →
  diagnostics가 P11-02의 실측 입력
- 기동 시간 개선 확인 → "느린 창" 종결 / 미개선 → 구버전 잔재·기타 원인 추적 task 신설

## DoD
- [ ] probe_results 반출 (openai_tools/text_toolcall/기동 시간 포함)
- [ ] real 스모크·work E2E 결과(성공이든 실패든) + runtime-last.json 반출
- [ ] Fable이 결과를 probe/results/에 sanitize 기록 + 후속 task 갱신
