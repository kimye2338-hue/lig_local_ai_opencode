# P14-03 — 아침 브리핑 + 리마인더 BAT

| 항목 | 값 |
|------|-----|
| 단계 | P14 (MASTER_PLAN §4 P14 작업 항목 3) |
| 담당 | codex |
| 선행 | P14-02 |
| 환경 | ANY (schtasks 등록은 안내만 — 자동 등록 금지) |

## 목표
하루의 시작: 오늘/이번 주 일정 + 마감 임박 + 미완료 액션아이템을 한 번에 보여주는 브리핑.

## 작업 항목
1. `agentops.py`에 `briefing` subcommand → `results/reports/briefing_<YYYYMMDD>.md` 생성+콘솔 출력:
   - 오늘 일정 / 이번 주 일정 / 마감 임박(3일 내, overdue 강조) — schedule_store 사용
   - 미완료 액션아이템: `results/artifacts/**/액션아이템.md`들을 스캔해 "대기" 행 수집
     (파일별 최대 5행, 출처 파일명 표기)
   - 어제 audit 요약(있으면): 실행 건수/실패 건수 (audit.py가 아직 없으면 이 항목은
     "audit 미도입" 표기 — P13-01 완료 후 자동 활성되는 optional import 패턴)
   - 빈 항목은 "없음" 명시 (조용한 생략 금지)
2. `launch/briefing.bat` (인코딩 규약 준수) — 더블클릭/스케줄러 양용.
3. `launch/install-reminder.bat`: `schtasks /Create /SC DAILY /ST 08:30 ...` 명령을
   **출력하고 사용자 확인(y) 후에만 실행**. `uninstall-reminder.bat`도 함께.
4. `tests/test_secretary.py` 신설: tmp 격리로 일정+액션아이템 fixture 만들고 briefing 실행 →
   md에 일정/임박/액션아이템/출처가 반영되는지, 빈 상태에서 "없음" 표기되는지.

## 검증 명령
```bat
py -3.11 tests\test_secretary.py
(회귀 9개 전부)
```

## DoD
- [ ] briefing md 생성 + 4개 섹션 (fixture 기반 검증)
- [ ] briefing.bat manual smoke 성공 (출력 첨부)
- [ ] reminder 등록은 확인 후에만 (자동 등록 없음 증명)
- [ ] 기존 checks 무손상

## 금지
- schtasks를 테스트에서 실제 실행 금지 (명령 문자열 생성까지만 검증).
- 액션아이템 스캔에서 results 밖 디렉터리 순회 금지.
