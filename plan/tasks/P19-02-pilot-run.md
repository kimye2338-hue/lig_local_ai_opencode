# P19-02 — 회사 파일럿 12종 실측

| 항목 | 값 |
|------|-----|
| 단계 | P19 (MASTER_PLAN §4 P19) |
| 담당 | human+fable (회사 PC에서 사용자가 실행, Fable 세션이 보조/기록) |
| 선행 | P19-01, P17-04 |
| 환경 | COMPANY+HUMAN |

## 절차
1. `docs/PILOT_DAY1.md` 순서대로 1일차 수행 → gateway 3라우트 스모크 결과 기록.
2. EXAONE/Qwen tool-call 원문 수집 → 파싱 실패 시 그 자리에서 파서 보강 태스크 생성
   (P11-02 절차 재사용).
3. `docs/PILOT_RECORD.md` 12종 실측 — **성공률 조작 금지**, 실패는 원인과 함께.
4. 결과에 따라: 성공 어댑터 available=True 전환(검증 날짜 기입),
   company validation pending 항목 일괄 갱신, 실패 항목은 `docs/PILOT_BACKLOG.md` →
   Fable이 후속 task로 변환.

## DoD
- [ ] 12종 결과표 완성 (최종 성공 기준: 10/12)
- [ ] gateway 실측으로 company validation pending 갱신
- [ ] BACKLOG → 후속 task 생성
