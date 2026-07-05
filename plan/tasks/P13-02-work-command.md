# P13-02 — `work` 오케스트레이터 subcommand E2E

| 항목 | 값 |
|------|-----|
| 단계 | P13 (MASTER_PLAN §4 P13 작업 항목 1, 4) |
| 담당 | codex |
| 선행 | P13-01 |
| 환경 | ANY (mock으로 E2E) |
| 산출 규모 | agentops work (~150줄) + 테스트 파일 1개 |

## 목표
"한 명령이면 끝": ingest → plan → 승인 → (파일 작업 필요 시) agent loop → artifact+품질 →
(--execute && available 어댑터) 실행 → 최종 보고 md.

## 먼저 읽기
- `agentops.py`의 `cmd_plan`/`cmd_agent` (재사용할 조립 블록)
- `tests/test_capability_bench.py`의 CLI 섹션 (subprocess+격리 패턴)
- MASTER_PLAN §4 P13

## 작업 항목
1. `agentops.py`에 `work` subcommand:
   `--task`(필수) `--input`(반복) `--task-file`(음성 대비: 파일에서 task 읽기)
   `--mode mock|real`(기본 mock) `--execute` `--yes`.
   흐름: ingest 요약 출력 → plan 출력 → 위험 항목 목록화 → `request_approval`
   (--yes면 auto) → 거부 시 exit 3 + "승인 거부로 중단" → artifact 생성(품질 포함) →
   --execute 시 available 어댑터만 실행(아니면 "adapter pending" 안내) →
   `results/reports/work_<run_id>.md` 최종 보고 생성(요청/입력/계획/수행/산출물+품질/
   audit 요약/pending/다음 명령).
2. run_id는 artifact context의 run_id 재사용 — 보고서/audit/산출물이 같은 id로 연결.
3. 전 과정 audit.record (task 80자, 단계별 verdict).
4. `tests/test_work_command.py`: subprocess E2E (AGENTOPS_ROOT/LIG_AUDIT_DIR/LIG_DIAG_DIR
   전부 tmp 격리): ① --yes mock 성공 → 보고서 md 존재+필수 섹션 ② 승인 거부(input "n")
   → exit 3 + 산출물 없음 ③ --input 경로 → input-grounded 검증 ④ audit에 run_id 일관.

## 검증 명령
```bat
py -3.11 tests\test_work_command.py
(회귀 9개 전부)
```

## DoD
- [ ] work 한 줄로 입력→산출물→최종 보고 md (mock, 증빙 첨부)
- [ ] 거부 시 아무 산출물/실행 없음
- [ ] --task-file 동작 (음성 연동 대비)
- [ ] 최종 보고 md에 품질 결과/pending/audit 요약 포함
- [ ] 기존 checks 무손상

## 금지
- cmd_plan/cmd_agent 로직 복사-붙여넣기 금지 — 함수로 재사용 (한 곳 수정 원칙).
- --yes 기본 on 금지. real 모드 기본값 금지 (mock 기본).
