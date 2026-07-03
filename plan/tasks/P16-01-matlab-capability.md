# P16-01 — matlab_automation capability + .m 생성기

| 항목 | 값 |
|------|-----|
| 단계 | P16 (MASTER_PLAN §4 P16 작업 항목 1) |
| 담당 | codex |
| 선행 | P15-01 |
| 환경 | ANY (MATLAB 불필요 — 생성만) |

## 목표
시험 데이터 후처리용 MATLAB 스크립트 scaffold — 기계연구원의 실제 반복 업무
(데이터 로드→필터→통계→플롯→저장)를 구조로 제공.

## 작업 항목
1. `capabilities.py`에 `matlab_automation` (§5 승인 목록): keywords 매트랩, matlab,
   후처리, 플롯, 그래프 그려, .m. artifact_kinds: ["matlab_script"].
   pending: ["app validation pending: MATLAB 2024a에서 -batch 실행 검증"].
2. `artifact_generators.py`에 `gen_matlab_script(task, out_dir, ctx)` → `작업.m`:
   - 헤더 주석: 요청/입력 자료/실행 방법(`matlab -batch "run('작업.m')"`)/상태(pending)
   - 구조: 설정 상수(INPUT_FILE — ctx 입력 CSV 있으면 실제 파일명 반영) →
     readtable/readmatrix 로드 → 필터/이상값(입력 notable 반영 주석) → 기본 통계 →
     figure+saveas(png) → writetable 저장 → try/catch로 전체 감싸 오류 시 메시지+exit(1)
   - MATLAB 2024a 문법 기준 (사용자 확정 버전), input-grounded 규칙 준수.
3. `artifact_quality.py` matlab_script 규칙: 실행 방법 명시, try/catch, INPUT_FILE 상수,
   pending 표기, 공통 규칙 상속. `_KIND_SUFFIXES`에 ".m".
4. ARTIFACT_KIND_INFO + bench: "시험 데이터 후처리 매트랩 스크립트 만들어줘" 라우팅/생성/
   품질/입력 반영(CSV fixture) checks.

## 검증 명령
```bat
py -3.11 tests\test_capability_bench.py
(회귀 9개 전부)
```

## DoD
- [ ] 라우팅→생성→품질→입력 반영 bench 통과
- [ ] .m이 -batch 실행 전제 구조 (try/catch+exit)
- [ ] 기존 checks 무손상

## 금지
- MATLAB 툴박스 의존 함수(기본 배포 외) 사용 금지 — base MATLAB 함수만.
