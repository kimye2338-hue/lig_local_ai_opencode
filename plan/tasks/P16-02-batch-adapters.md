# P16-02 — matlab -batch / AutoCAD accoreconsole 어댑터

| 항목 | 값 |
|------|-----|
| 단계 | P16 (MASTER_PLAN §4 P16 작업 항목 1~2) |
| 담당 | codex |
| 선행 | P16-01 |
| 환경 | ANY (앱 부재 시 SKIP — 실측은 회사 P19) |

## 목표
CLI 배치형 어댑터 2종 — COM보다 안정적인 경로. subprocess 기반이라 stdlib만으로 가능.

> **probe 실측 + 사용자 확인 (2026-07-03, 회사 PC)**: MATLAB R2024a 경로 확인
> (`C:\Program Files\MATLAB\R2024a\bin\matlab.exe`). AutoCAD는 **Mechanical 2019,
> 비표준 경로 `C:\AutoCAD 2019\`** — 사용자는 `acad.exe /p LIGNEX1 /product ACADM`
> 바로가기로 실행. 구현 지침: exe 탐색에 `C:\AutoCAD*\accoreconsole.exe` 포함(probe_env
> 반영됨), accoreconsole 호출 시 `/product ACADM` 컨텍스트가 필요한지 회사 실측으로 확인,
> 프로필/제품 인자는 env(`ACAD_PROFILE`, `ACAD_PRODUCT`)로 받되 기본값을 위 실측값으로.

## 작업 항목
1. `agent_ops/adapters/matlab_batch.py`:
   - `find_matlab() -> str`: PATH + 표준 설치 경로(`C:\Program Files\MATLAB\R2024a\bin\matlab.exe`)
     탐색, env `MATLAB_EXE` 오버라이드. 없으면 "" (안내 반환용).
   - `execute(script_path, options)` → `matlab -batch "run('<script>')"` subprocess,
     timeout(기본 300s), stdout/stderr 수집, exit code로 ok 판정. 실행 전 approval 전제
     (risk=dangerous), audit 기록. 작업 디렉터리는 script 폴더 (원본 데이터는 읽기만 —
     스크립트가 쓰는 출력은 script 폴더 내로 유도, P16-01 생성기 구조가 보장).
2. `agent_ops/adapters/autocad_batch.py`:
   - AutoCAD .scr 생성기 추가: `gen_autocad_script(task, out_dir, ctx)` → `작업.scr`
     (도면 사본 열기→명령 나열→QSAVE 금지, SAVEAS 사본만 — 템플릿 주석으로 명시),
     기존 office_cad_automation capability의 artifact_kinds에 "autocad_script" 추가.
   - `execute(dwg_path, scr_path)`: 원본 dwg를 사본 복사 후
     `accoreconsole.exe /i <사본.dwg> /s <script.scr>` subprocess (AutoCAD 2019 경로 탐색
     + env `ACCORECONSOLE_EXE`). 로그 수집, timeout.
3. `adapters/__init__.py`에 matlab/autocad 항목 등록 (available=False, requires/pending 정직 기입).
4. quality: autocad_script 규칙(사본 정책 문구, QSAVE 부재, pending) + `_KIND_SUFFIXES` ".scr".
5. `tests/test_batch_adapters.py`: 앱 부재 SKIP + 부재 안내 반환, exe 탐색 로직(가짜 env로),
   사본 정책(원본 미변경 — 가짜 exe 스크립트로 subprocess 경로 검증 가능하면 수행),
   scr 생성/품질 bench 연동.

## 검증 명령
```bat
py -3.11 tests\test_batch_adapters.py
py -3.11 tests\test_capability_bench.py
(회귀 9개 전부)
```

## DoD
- [ ] 두 어댑터 모두 앱 부재에서 crash 없이 안내 반환
- [ ] 원본 dwg 불가침 (사본 실행) — 코드 경로로 보장
- [ ] .scr 생성기 + 품질 규칙 bench 통과
- [ ] available=False + "app validation pending: 회사 MATLAB 2024a / AutoCAD 2019" 표기

## 금지
- MATLAB Engine API(파이썬 패키지) 도입 금지 — subprocess -batch만.
- QSAVE(원본 저장) 명령을 scr 템플릿에 포함 금지.
