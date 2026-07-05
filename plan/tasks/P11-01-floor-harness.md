# P11-01 — weak-model capability-floor 하네스

| 항목 | 값 |
|------|-----|
| 단계 | P11 (MASTER_PLAN §4 P11) |
| 담당 | codex |
| 선행 | P09-03, P11-A (둘 다 APPROVED — 2026-07-03) |
| 환경 | ANY (하네스 자체는 LLM 불필요 — mock으로 검증. 실측은 P11-02) |
| 산출 규모 | 테스트 파일 1개 + doctor 필드 1개 |

## 목표
로컬 LLM으로 시나리오 10종×N회를 자동 실행해 tool-call 성공률/실패 유형을 집계하는
하네스를 만든다 (실측 자체는 P11-02 범위 — 이 작업은 하네스+mock 자가검증까지).

> **실측 확정 (2026-07-03)**: gateway는 OpenAI native function calling 완전 지원,
> P11-A로 id 자체발급 + `tool_call_mode`(native|text_fallback|none) 진단이 이미
> 구현·APPROVED됨. 하네스는 **runtime-last.json의 tool_call_mode를 그대로 집계**하면
> 된다 — 새 파싱 로직 작성 금지.

## 먼저 읽기 (이미 구현된 것 — 재구현 금지)
- `tests/test_real_llm_smoke.py` — `local_llm_is_running()`, `make_env()`, `run_agent()`,
  `copy_diag()` 패턴을 **그대로 복사해 재사용**. 서버 부재 SKIP 문구도 동일 형식.
- `agent_ops/tool_dispatch.py` — `run_agent_loop` outcome 어휘:
  `completed | tool_loop_cutoff | llm_failed | max_turns_exceeded`,
  dispatch history의 `root_cause_category`:
  `unknown_tool | invalid_argument | missing_argument | io_error | path_escape`.
- `agent_ops/lig_runtime.py` — result/`runtime-last.json`의 `tool_call_mode`.
- `agent_ops/mock_transport.py` — mock 자가검증 1회 실행에 사용 (`MOCK_ENV`).

## 시나리오 10종 (고정 — 발명·변경 금지)
판정 = ①subprocess exit 0 ②기대 파일 존재 ③필수 단어 포함. 태스크 문자열에
출력 파일명을 명시해 약모델도 판정 가능하게 한다 (P09-03 r3 방식).

| # | 태스크 문자열 (그대로 사용) | 기대 파일 | 필수 단어 |
|---|---------------------------|----------|----------|
| 1 | `input/memo.txt 파일을 읽고 floor_요약.md로 요약해서 저장해줘. 반드시 브라켓 단어를 포함해줘` | `floor_요약.md` | `브라켓` |
| 2 | `floor_노트.md 파일을 만들고 'floor smoke ok'라고 적어줘` | `floor_노트.md` | `floor smoke ok` |
| 3 | `현재 폴더의 파일 목록을 확인하고 floor_목록.md에 저장해줘` | `floor_목록.md` | `memo` |
| 4 | `input/데이터.csv 파일을 읽고 행 수를 floor_행수.md에 적어줘` | `floor_행수.md` | `3` |
| 5 | `input/memo.txt를 읽고 액션아이템을 floor_액션.md로 정리해줘. 반드시 금요일 단어를 포함해줘` | `floor_액션.md` | `금요일` |
| 6 | `floor_보고.md 파일을 만들고 제목과 결론 섹션을 포함한 보고서 틀을 적어줘` | `floor_보고.md` | `결론` |
| 7 | `input/memo.txt 내용을 floor_사본.md로 복사해줘` | `floor_사본.md` | `케이블` |
| 8 | `input/데이터.csv를 읽고 헤더 컬럼 이름들을 floor_컬럼.md에 나열해줘` | `floor_컬럼.md` | `이름` |
| 9 | `floor_점검.md를 만들어 오늘 점검 항목 3개를 번호 목록으로 적어줘` | `floor_점검.md` | `1` |
| 10 | `input/memo.txt를 읽고 한 줄 요약을 floor_한줄.md에 적어줘. 반드시 도면 단어를 포함해줘` | `floor_한줄.md` | `도면` |

입력 fixture (하네스가 매 회 새 임시 작업공간에 생성):
- `input/memo.txt` = `회의 메모: 배터리 브라켓 도면 검토, 케이블 간섭 확인, 금요일까지 요약 필요`
- `input/데이터.csv` = 헤더 `이름,값` + 데이터 3행 (`A,1` / `B,2` / `C,3`)

## 작업 항목
1. `tests/test_capability_floor.py`:
   - 서버 부재 → mock 자가검증 checks 수행 후 `SKIP  local llm not running — skipped, not failed` + exit 0.
   - 서버 존재 → 시나리오 10종 × N회(기본 3, env `FLOOR_REPEAT`) 실행.
   - 회차마다 diag(`runtime-last.json`, `agent-loop-last.json`)에서 `tool_call_mode`와
     loop `outcome`을 수집.
   - 실패 유형 분류(새 로직 금지 — 기존 필드 매핑만):
     `parse_fail`(tool_call_mode=="none"인데 도구 필요 태스크) / `loop_cutoff`(outcome
     tool_loop_cutoff) / `max_turns`(outcome max_turns_exceeded) / `llm_failed` /
     `wrong_output`(exit 0이지만 기대 파일·단어 불충족) / `other`.
   - 집계 리포트 `agent_ops/results/reports/capability_floor.md` 저장:

     ```markdown
     # capability floor 리포트
     - 실행: <UTC ISO> / 모델: <LIG_LOCAL_MODEL> / 반복: N
     - 총 성공률: X/Y (Z%)  / native 비율: n/Y

     | # | 시나리오 | 성공 | tool_call_mode 분포 | 실패 유형 |
     |---|----------|------|--------------------|-----------|
     ```

     실패 사례는 시나리오당 최근 1건 요약 3줄 이내 (대화 원문 전체 저장 금지).
   - **mock 자가검증 checks (LLM 불필요, 항상 실행)**: mock 모드 1회로
     ①집계 함수가 성공/실패/유형을 올바르게 세는지(가짜 결과 주입) ②리포트 md가
     생성되고 표 헤더·성공률 라인이 존재하는지 ③시나리오 테이블이 정확히 10개인지.
2. `doctor.py` artifact_pipeline 섹션에 `"capability_floor_report"`: 리포트 경로 존재
   시 path/timestamp, 없으면 `"not generated"`.

## 검증 명령
```bat
cd workspace-template
py -3.11 tests\test_capability_floor.py    (서버 없음 → mock 자가검증 + SKIP, exit 0)
py -3.11 tests\test_capability_floor.py    (Ollama 구동 시 → 실측 1회 이상 — 이 PC는 qwen2.5:7b-instruct 설치됨)
(회귀: tests\test_*.py 전부 exit 0)
```

## DoD
- [ ] 서버 없이 하네스 자가검증 checks 통과 + 실측부 SKIP + exit 0
- [ ] 리포트 md 형식: 위 골격(성공률 라인+시나리오 표+실패 유형) 준수, 예시 출력 보고서에 첨부
- [ ] tool_call_mode/outcome은 기존 diag 필드에서 읽음 (새 파서 없음)
- [ ] 기존 checks 무손상 (전체 테스트 파일 exit 0)

## 금지
- 시나리오 문자열·판정 기준 변경/완화 금지 (필수 단어 완화 금지).
- 대화 원문 전체를 리포트에 저장 금지 (실패 요약 3줄 이내).
- toolcall_parser/tool_dispatch/lig_runtime 제품 코드 수정 금지 — 이 작업은 테스트+doctor 필드만.
