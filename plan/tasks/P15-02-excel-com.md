# P15-02 — excel_com 어댑터 (사본 정책)

| 항목 | 값 |
|------|-----|
| 단계 | P15 (MASTER_PLAN §4 P15 작업 항목 2) |
| 담당 | codex |
| 선행 | P15-01, P13-01 |
| 환경 | ANY (코드+SKIP 테스트. Excel 실측은 P15-04) |

## 목표
Excel COM 실행 어댑터 — 원본 불가침(항상 사본), 실패 시 프로세스 정리, VBProject 차단 시
정직한 강등.

> **probe 실측 (2026-07-03, 회사 PC)**: Excel AccessVBOM=1 + VBAWarnings=1 + 정책 잠금
> 없음 (probe/results/probe_env_company_20260703.md) → `run_macro_file`의 VBProject
> 자동 주입을 **1차 경로**로 구현하라. manual_import 강등 경로는 다른 PC 대비용으로 유지.
> pywin32는 회사 PC에 이미 설치됨.

## 작업 항목
1. `agent_ops/adapters/excel_com.py`:
   - pywin32는 **optional import**: 없으면 모든 호출이
     {"ok": False, "error": "pywin32 미설치 — dependencies.json 'pywin32' 참조"} 반환 (crash 금지).
   - `execute(action, options)`: `open_copy`(원본→`사본_<이름>` 복사 후 열기),
     `read_range(sheet, range)`, `write_range(sheet, range, values)`, `save`, `close`,
     `run_macro_file(bas_path)` — VBProject 접근 실패(Trust Center) 시
     {"ok": False, "fallback": "manual_import", "guide": "Alt+F11 …"} 로 강등 (예외 전파 금지).
   - Excel 기동: DisplayAlerts=False, Visible 옵션(기본 False). **finally에서 Quit** +
     COM 해제. 원본 경로 직접 열기 시도는 코드 수준에서 차단 (open_copy만 존재).
   - 모든 실행은 audit.record 경유 (P13-01), risk=dangerous → 호출측 승인 전제.
2. `adapters/__init__.py` office 항목에 execute 연결, available=False 유지.
3. `tests/test_office_adapters.py` 신설: pywin32/Excel 부재 → SKIP+exit 0.
   부재 환경에서도 검증: optional import 경로, open_copy 외 원본 접근 부재(API 표면 검사),
   action 라우팅/미지 action 거부. (실측 checks는 P15-04에서 활성)

## 검증 명령
```bat
py -3.11 tests\test_office_adapters.py
(회귀 9개 전부)
```

## DoD
- [ ] pywin32 부재에서 전 API가 안내 반환 (crash 0)
- [ ] 사본 강제 (원본 열기 API 자체가 없음)
- [ ] VBProject 차단 → manual_import 강등 경로 존재 (모의 테스트)
- [ ] available=False 유지, 기존 checks 무손상

## 금지
- pywin32를 이 시점에 pip install 금지 (P17-02 반입 절차로만).
- SaveAs로 원본 덮어쓰기 가능한 경로 금지.
