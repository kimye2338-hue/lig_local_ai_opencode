# P15-01 — Office 2016 호환 quality 규칙

| 항목 | 값 |
|------|-----|
| 단계 | P15 (MASTER_PLAN §4 P15 작업 항목 1, §6.2) |
| 담당 | codex |
| 선행 | 없음 |
| 환경 | ANY |

## 목표
회사 Office는 2016 — 하위 모델/LLM이 최신 함수를 쓴 매크로를 만들면 품질 검사가
**자동으로 FAIL**하게 만든다.

## 작업 항목
1. `artifact_quality.py`:
   - 상수 `_OFFICE2016_BANNED` = MASTER_PLAN §6.2 금지 목록 전체 (XLOOKUP, XMATCH, FILTER,
     SORT, SORTBY, UNIQUE, SEQUENCE, RANDARRAY, LET, LAMBDA, TEXTSPLIT, TEXTBEFORE,
     TEXTAFTER, VSTACK, HSTACK, TEXTJOIN, CONCAT, IFS, SWITCH, MAXIFS, MINIFS).
   - vba_macro 규칙 추가 `office2016_compat`: 텍스트에 금지 함수가 **함수 호출 형태**
     (`이름(` 또는 `WorksheetFunction.이름`)로 등장하면 위반. 주석/문자열 내 단순 언급은
     오탐 가능 — 단어 경계+`(` 패턴으로 최소화하고, 한계를 규칙 why에 명시.
     FILTER/SORT 같은 짧은 이름의 오탐 사례를 테스트로 확인해 필요 시
     `WorksheetFunction.` 접두 형태만 검사하는 식으로 조정하되, 조정 근거를 보고서에 기록.
2. `artifact_generators.py` `_VBA_HOST_NOTES`/헤더에 "대상: Office 2016 호환" 문구 추가
   (excel/word/powerpoint), 대체 가이드 한 줄 (VLOOKUP/INDEX+MATCH/중첩 IF).
3. `test_capability_bench.py`: negative — XLOOKUP 포함 매크로 텍스트 → office2016_compat
   위반 검출 / positive — 기존 scaffold 전부 통과 유지.

## 검증 명령
```bat
py -3.11 tests\test_capability_bench.py
(회귀 9개 전부)
```

## DoD
- [ ] 금지 목록 21종 상수화 + 검출 테스트 (최소 XLOOKUP/TEXTJOIN/LET 3종 negative)
- [ ] 기존 scaffold 오탐 0 (전체 bench 통과)
- [ ] 매크로 헤더에 2016 대상 명시
- [ ] 기존 checks 무손상

## 금지
- 오탐 줄이려고 검사 자체를 무력화 금지 — 한계는 명시하되 핵심(XLOOKUP 등 긴 이름)은 반드시 검출.
