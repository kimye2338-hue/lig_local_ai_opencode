# P19-01 — 회사 파일럿 체크리스트/기록 양식 준비

| 항목 | 값 |
|------|-----|
| 단계 | P19 (MASTER_PLAN §4 P19) |
| 담당 | codex |
| 선행 | P14-03, P15-02, P16-02 |
| 환경 | ANY |

## 작업 항목
1. `docs/PILOT_DAY1.md`: 1일차 순서(반입→setup→doctor→lig-api.env→gateway 스모크
   3라우트→파서 실측) — 각 단계에 정확한 명령/기대 출력/실패 시 RUNBOOK 링크.
2. `docs/PILOT_RECORD.md`: MASTER_PLAN §4 P19의 12종 업무 표를 기록 양식으로
   (업무|명령|성공/실패|소요|개입 횟수|비고). 성공 기준을 업무별로 한 줄씩 명시
   (예: #1 브리핑 = "md 생성+일정/액션 반영").
3. gateway 스모크 스크립트 `launch/gateway-smoke.bat`: 3라우트 각각 짧은 real 호출
   (lig-api.env 없으면 무엇이 빠졌는지 출력 후 exit 2 — 기존 validate 재사용).
4. 12종 업무 각각의 정확한 실행 명령을 PILOT_RECORD에 미리 기입 (회사에서 복붙만).

## DoD
- [ ] 두 문서 + 스모크 BAT (mock 환경에서 BAT 경로/인코딩 smoke)
- [ ] 12종 전부 실행 명령 사전 기입
- [ ] 기존 checks 무손상
