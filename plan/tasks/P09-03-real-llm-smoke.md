# P09-03 — real-LLM 스모크 테스트 + doctor + 실측

| 항목 | 값 |
|------|-----|
| 단계 | P9 (MASTER_PLAN §4 P9 작업 항목 4~7) |
| 담당 | codex |
| 선행 | P09-02 |
| 환경 | LOCAL-LLM(옵션 — 없으면 SKIP 경로만 검증하고 그 사실을 보고) |
| 산출 규모 | 신규 테스트 파일 1개 + doctor 확장 + 문서 |

## 목표
로컬 OpenAI 호환 서버(Ollama 등)로 agent loop을 real로 실측하는 스모크 테스트와
운영 진단(doctor llm_endpoints)을 만든다. 서버가 없으면 **정직하게 SKIP**.

## 먼저 읽기
- MASTER_PLAN §4 P9 작업 항목 4~7, §1.2(집 PC 사양: 8GB VRAM → 7b 무거우면 3b)
- `workspace-template/agent_ops/doctor.py` (기존 섹션 패턴)
- `workspace-template/tests/test_agent_cli.py` (subprocess 테스트 패턴)

## 작업 항목
1. `tests/test_real_llm_smoke.py` 신설:
   - 시작 시 `LIG_LOCAL_BASE_URL`(기본 11434)에 2초 타임아웃 연결 시도.
     실패 → `SKIP  local llm not running — skipped, not failed` 출력 후 exit 0.
   - 성공 시 3 시나리오를 subprocess(run-agent 경로)로 실행:
     ① 파일 읽고 요약 저장 ② 새 파일 생성 ③ 존재하지 않는 도구를 유도하는 태스크에서
     복구/정상 종료. 각각 결과 파일 존재/exit code 검증. 워크스페이스는 tmp로 격리
     (AGENTOPS_ROOT env — test_capability_bench.py의 CLI 섹션 참고).
   - tool-call 원문 로그를 tmp에 저장하고, 파싱 실패 사례가 있으면 보고서에 첨부용으로 남김.
2. `doctor.py`에 `llm_endpoints` 섹션: profile, 라우트별 설정 여부(presence flag),
   local base_url 도달성(ok/fail만 — **URL 원문 출력 금지**, 로컬 127.0.0.1은 예외적으로 표기 가능).
3. `launch/README.md`에 "§5 로컬 LLM으로 real 모드 검증" 절 추가 (Ollama pull → env 설정 →
   run-agent 명령, MASTER_PLAN P9 작업 항목 4의 명령 그대로).
4. **실측**: 실행 환경에 Ollama가 있으면 시나리오 3종을 실제 수행하고 출력/산출물을
   보고서에 증거로 첨부. 없으면 "환경 부재로 실측 미수행 (SKIP 경로만 검증)"을 명시.
5. 실측 중 tool-call 파싱 실패가 나오면: `toolcall_parser.py`에 **실측 사례 기반** 복구 규칙
   추가 + `test_toolcall_parser.py`에 해당 사례 테스트 추가. (실측 없으면 이 항목 생략)

## 검증 명령
```bat
py -3.11 tests\test_real_llm_smoke.py      (서버 없는 상태 → SKIP + exit 0 확인)
py -3.11 tests\test_real_llm_smoke.py      (서버 있으면 실측)
py -3.11 -c "import json,sys; sys.path.insert(0,'.'); from agent_ops.doctor import run_doctor; print(json.dumps(run_doctor()['llm_endpoints'], ensure_ascii=False))"
(회귀 9개 전부)
```

## DoD
- [ ] 서버 부재 시 SKIP+exit 0 (테스트 출력 원문 증빙)
- [ ] doctor llm_endpoints 동작 (gateway host 문자열 미출력)
- [ ] launch/README §5 추가
- [ ] 실측 수행 여부와 결과를 보고서에 정직 기록 (수행 시: E2E 성공 증빙 / 미수행 시: 사유)
- [ ] 기존 checks 무손상

## 금지 / 가드레일
- Ollama 자동 설치 시도 금지 (사람의 환경 결정 — 안내만).
- 실측 실패를 성공으로 기록 금지. 로컬 성공을 "gateway/company 검증"이라 표기 금지.
- CI에서 이 테스트가 SKIP으로 통과하는지 확인 (외부 자원 없는 환경 전제).
