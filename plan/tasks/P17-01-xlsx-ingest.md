# P17-01 — xlsx 입력 ingest (openpyxl optional)

| 항목 | 값 |
|------|-----|
| 단계 | P17 (MASTER_PLAN §4 P17 작업 항목 2) |
| 담당 | codex |
| 선행 | 없음 |
| 환경 | ANY |

## 목표
시험 데이터의 실제 형식인 .xlsx를 입력으로 읽는다. openpyxl은 **optional import** —
없으면 기존대로 unsupported로 정직 표기 (동작 저하 없음).

## 먼저 읽기
- `agent_ops/input_ingest.py` (CSV 처리 `_csv_facts` — 동일 규칙 적용 대상)
- `tests/test_capability_bench.py` input-grounded 섹션

## 작업 항목
1. `input_ingest.py`:
   - 모듈 상단 `try: import openpyxl / except ImportError: openpyxl = None`.
   - SUPPORTED_SUFFIXES에 ".xlsx" 추가하되, openpyxl=None이면 xlsx는 unsupported로
     기록 + reason에 "openpyxl 미설치 (dependencies.json 'office-doc-wheels')".
   - `_xlsx_facts(path)`: 첫 시트(+시트 수) — 헤더/행·열 수/이상 행(마커 규칙은
     `_ABNORMAL_MARKERS` 재사용, 셀 str 변환 후), 시트 다수면 시트명 목록 fact.
     read_only=True + data_only=True (수식 대신 값).
   - 대용량: max_rows(기본 2000) 초과 시 앞부분만 + fact에 명시.
2. bench 확장 (openpyxl 유무 양쪽 커버):
   - openpyxl 있으면: xlsx fixture 생성(테스트 내에서 openpyxl로 작성) → facts/notable/
     input-grounded 문서 반영 checks.
   - 없으면: unsupported 경로 + 문서 limitations 표기 checks (SKIP 아님 — 이 경로도 정상 동작).
   - 어느 경로였는지 테스트 출력에 명시.
3. `release/dependencies.json`의 openpyxl 항목 상태 확인 (office-doc-wheels) — 이 작업에서는
   설치하지 않음 (개발 PC에 이미 있으면 활용 가능).

## 검증 명령
```bat
py -3.11 tests\test_capability_bench.py
(회귀 9개 전부)
```

## DoD
- [ ] openpyxl 유무 양쪽 경로가 각각 정직하게 동작 (테스트 증명)
- [ ] xlsx facts가 CSV와 동일 규칙 (행·열/이상 행/파일명 반영)
- [ ] 코어 stdlib-only 원칙 유지 (optional import — 부재 시 기능 저하 없이 unsupported)
- [ ] 기존 checks 무손상

## 금지
- openpyxl을 하드 의존으로 만들기 금지 (import 실패 = crash 금지).
- .xls(구형)/암호화 파일 지원 시도 금지 — unsupported 사유만 정확히.
