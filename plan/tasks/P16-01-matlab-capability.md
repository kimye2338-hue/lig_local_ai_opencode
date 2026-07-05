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
   - 기존 generator들(gen_document 등)과 같은 시그니처/반환/ctx 사용 패턴을 따른다.
   - MATLAB 2024a 문법 기준 (사용자 확정 버전), input-grounded 규칙 준수.
   - 골격 (이 구조 그대로 — 섹션 순서·try/catch·exit(1) 필수. `-batch` 실계산은
     2026-07-03 회사에서 실증됨, ~21s 기동 포함):
   ```matlab
   %% 시험 데이터 후처리 스크립트 (자동 생성 scaffold)
   % 요청: <task 문자열>
   % 입력: <ctx 입력 파일명 목록 또는 "지정된 입력 없음">
   % 실행: matlab -batch "run('작업.m')"   (작업 폴더에서)
   % 상태: app validation pending — MATLAB 2024a에서 -batch 실행 검증 전
   try
       %% 1. 설정
       INPUT_FILE = '<입력 CSV 있으면 실제 파일명, 없으면 data.csv>';
       OUT_PREFIX = '결과_후처리';
       %% 2. 로드
       T = readtable(INPUT_FILE);
       %% 3. 필터/이상값 (입력 요약의 notable 반영 주석)
       % TODO(사용자 확인): 이상값 기준을 업무 규격에 맞게 조정
       %% 4. 기본 통계
       S = varfun(@mean, T, 'InputVariables', @isnumeric);
       disp(S)
       %% 5. 플롯 저장
       fig = figure('Visible', 'off');
       % plot(...)  % 입력 열 구조에 맞는 기본 플롯
       saveas(fig, [OUT_PREFIX '_plot.png']);
       %% 6. 결과 저장
       writetable(S, [OUT_PREFIX '_통계.csv']);
       fprintf('완료: %s\n', OUT_PREFIX);
   catch err
       fprintf(2, '오류: %s\n', err.message);
       exit(1);
   end
   ```
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
