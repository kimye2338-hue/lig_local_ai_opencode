# P14-01 — schedule store + 결정적 날짜 파서

| 항목 | 값 |
|------|-----|
| 단계 | P14 (MASTER_PLAN §4 P14 작업 항목 1) |
| 담당 | codex |
| 선행 | 없음 |
| 환경 | ANY |
| 산출 규모 | 모듈 ~200줄 + 테스트 ~25 checks |

## 목표
일정 데이터 저장소와 자연어 날짜 파서. **날짜 해석은 LLM 금지** — 일정 오등록은 치명적이므로
결정적 파서만, 모호하면 되묻는다.

## 작업 항목
1. `agent_ops/schedule_store.py` (stdlib only):
   - 저장: `%USERPROFILE%\OpenCodeLIG_USERDATA\schedule\schedule.json`
     (env `LIG_SCHEDULE_DIR` 오버라이드 — 테스트 격리). 쓰기 전 `.bak` 1세대 유지,
     원자적 쓰기는 core의 atomic_write_json 재사용.
   - 항목 스키마: {id(순번), title, due("YYYY-MM-DD" 또는 "YYYY-MM-DD HH:MM"),
     category("회의"|"보고"|"시험"|"개인"|"기타"), status("open"|"done"),
     source("manual"|"mail"|"meeting"), created}.
   - API: `add(title, due_text, category=None, source="manual", now=None)`,
     `list_items(when="all|today|week|overdue", now=None)`, `mark_done(id)`, `remove(id)`,
     `parse_due(text, now=None)`. `now` 주입은 테스트 결정성용 (datetime 직접 호출 금지).
2. `parse_due(text, now)` 지원 케이스 (전부 테스트로 고정):
   - "오늘", "내일", "모레", "글피"
   - 요일: "금요일", "이번주 금요일", "다음주 화요일" (당일이 그 요일이면 오늘, 지났으면 다음 주)
   - 상대: "3일 후", "1주일 후", "2주 후"
   - 절대: "7월 15일", "2026-07-15", "12/25" (연도 없으면 미래 방향으로 보정)
   - 시각 결합: "금요일 14시", "내일 오후 3시", "7월 15일 09:30"
   - **파싱 불가/모호** → `{"ok": False, "question": "날짜를 다시 말씀해 주세요 (예: ...)"}` 반환.
     추측 금지. ("다음에", "언젠가", 빈 문자열 등)
3. category 자동 추정: title 키워드 테이블(회의/보고/시험/제출/미팅 등) — 못 찾으면 "기타".
4. `tests/test_schedule_store.py`: 위 파서 케이스 전부(각 1 check 이상, now 고정),
   CRUD/기간 조회/overdue/원자성(.bak)/done 전이/모호 입력 되묻기/저장 파일 스키마.

## 검증 명령
```bat
py -3.11 tests\test_schedule_store.py
(회귀 9개 전부)
```

## DoD
- [ ] 파서 케이스 표 전부 테스트로 고정 (now 주입, 결정적)
- [ ] 모호 입력 → 되묻기 반환 (추측 금지 증명 테스트)
- [ ] .bak 백업 + 원자적 쓰기
- [ ] LLM/외부 패키지 사용 없음
- [ ] 기존 checks 무손상

## 금지
- dateutil 등 외부 패키지 금지. LLM 호출 금지.
- 로케일 의존 API(strftime %A 한글 기대 등) 금지 — 요일은 weekday() 정수로 계산.
