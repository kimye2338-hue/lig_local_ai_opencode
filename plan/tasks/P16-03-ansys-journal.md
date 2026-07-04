# P16-03 — simulation_automation (Fluent journal) + fluent_batch

| 항목 | 값 |
|------|-----|
| 단계 | P16 (MASTER_PLAN §4 P16 작업 항목 3) |
| 담당 | codex |
| 선행 | P16-01 |
| 환경 | ANY (ANSYS 불필요 — 생성+SKIP. 실측은 회사 P19) |

## 목표
ANSYS 2024R1 반복 작업의 scaffold: Fluent journal 생성 + 배치 실행 어댑터,
Mechanical/SpaceClaim 스크립트는 **생성만** (GUI 의존 — 정직하게 pending).

## 리뷰 반영 (r1→r2) — reviews/P16-03-r1.md 필수 수정 1건 (r2 단일 진실 소스)

1. **키워드에서 광범위어 제거**: bare `해석`(일상어: 데이터/회의/문서 해석)과 `journal`은
   ANSYS 무관 요청을 오라우팅해 fluent_journal/ansys_script를 스퓨리어스 생성한다. 도메인
   경계어만 사용: `앤시스, ansys, 플루언트, fluent, 시뮬레이션, 메카니컬, spaceclaim,
   icepak, cfd, fea`. bench negative check 추가: `이 데이터 해석해줘`·`journal 정리해줘`가
   simulation_automation/fluent_journal로 라우팅되지 않음. (아래 작업 항목 1의 키워드는
   이 정정본으로 교체됨.)

> 나머지(gen_fluent_journal/gen_ansys_script 골격·공학책임 경고 quality 강제·fluent_batch
> 부재안내·available=False·테스트 POSIX 이식성)는 r1에서 실측 확인됨 — 유지.

## 작업 항목
1. `capabilities.py`에 `simulation_automation` (§5 승인 목록): keywords 앤시스, ansys,
   플루언트, fluent, 시뮬레이션, 메카니컬, spaceclaim, icepak, cfd, fea
   (bare `해석`/`journal`은 오라우팅 제거 — 리뷰 반영 1 참조).
   artifact_kinds: ["fluent_journal", "ansys_script"].
2. `gen_fluent_journal(task, out_dir, ctx)` → `작업.jou`:
   - TUI 명령 골격: case 읽기(`/file/read-case`, 경로는 CASE_FILE 주석 상수) →
     반복/수렴 설정 확인 주석 → `/solve/iterate N` → 결과 export
     (`/file/export/ascii` 등) → `/exit yes`.
   - 헤더 주석: 요청/입력/실행 방법(`fluent 3ddp -g -i 작업.jou -t<코어수>`)/
     **경고: 해석 세팅·수렴 판단은 사용자 책임, 이 journal은 실행 절차만 자동화**/pending.
3. `gen_ansys_script(task, out_dir, ctx)` → `mechanical_script.py` (ACT/IronPython 골격,
   주석 중심) — "GUI 스크립팅 콘솔에서 실행, app validation pending" 명시.
4. `adapters/fluent_batch.py`: `execute(journal_path, options)` — fluent.exe 탐색
   (env `FLUENT_EXE` + ANSYS Inc 표준 경로), subprocess 배치, 트랜스크립트 수집,
   timeout(기본 1800s, 옵션). available=False.
5. quality 규칙: fluent_journal(read-case/iterate/export/exit 존재, 경고문, pending),
   ansys_script(실행 방법+pending). `_KIND_SUFFIXES` ".jou"/".py". bench 시나리오:
   "플루언트 해석 돌리는 journal 만들어줘" 라우팅/생성/품질.

## 검증 명령
```bat
py -3.11 tests\test_batch_adapters.py   (fluent 부분 추가)
py -3.11 tests\test_capability_bench.py
(회귀 9개 전부)
```

## DoD
- [ ] journal/script 생성+품질 bench 통과 (입력 반영 포함)
- [ ] "공학 판단은 사용자 책임" 경고가 산출물에 포함 (quality 규칙으로 강제)
- [ ] fluent_batch는 부재 시 안내 반환, available=False
- [ ] 기존 checks 무손상

## 금지
- 해석 결과의 공학적 판단/합격 판정을 자동화라 표기 금지.
- 수렴 기준/모델 세팅을 임의 기본값으로 확정 금지 — 확인 주석으로.
