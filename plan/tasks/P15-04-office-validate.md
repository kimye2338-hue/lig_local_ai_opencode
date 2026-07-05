# P15-04 — word/ppt 변환 action + 집 Excel 실측

| 항목 | 값 |
|------|-----|
| 단계 | P15 (MASTER_PLAN §4 P15 작업 항목 4~5) |
| 담당 | codex |
| 선행 | P15-02 |
| 환경 | **EXCEL 필수** (집 PC 최신 Excel — 실측 가능 환경에서만 착수) |

## 목표
집 Excel로 excel_com 사본 왕복을 실측하고, Word/PowerPoint 변환 action을 추가한다.
**집 성공 = 스모크일 뿐** — 2016 검증은 회사(P19)에서.

## 작업 항목
1. pywin32 로컬 설치(개발 PC 한정 — dependencies.json에 이미 기록된 항목) 후
   `tests/test_office_adapters.py` 실측 활성: open_copy→write→read→save 왕복,
   원본 해시 불변 확인, 강제 예외 후 Excel 프로세스 잔류 없음.
2. `adapters/office_convert.py` (또는 excel_com 확장): `md_to_docx(문서.md)` —
   Word COM으로 제목/본문 스타일 유입, `spec_to_pptx(slide_spec.json)` — 슬라이드
   골격+제목+points 텍스트. 둘 다 optional import + 사본/신규 파일 생성만.
3. 실측 로그를 `results/adapter_validation/office_<날짜>.md`로 기록.
4. adapters office 항목: **available는 여전히 False**,
   `"home_smoke": "passed <날짜> (Excel 최신) — Office 2016 검증은 app validation pending"` 필드 추가.

## DoD
- [ ] 사본 왕복 실측 + 원본 불변 + 프로세스 정리 증빙
- [ ] md→docx / spec→pptx 생성 실측 (파일 열림 확인)
- [ ] available=False 유지 + home_smoke 기록 (집≠2016 원칙)
- [ ] Excel 없는 환경이면 착수하지 말고 STATUS 코멘트 후 다음 READY로

## 금지
- 집 실측 성공을 app validation 완료로 표기 금지.
- 문서 원본 위치에 변환 결과 덮어쓰기 금지 (신규 파일만).
