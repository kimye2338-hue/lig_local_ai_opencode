# OpenCodeLIG 마스터플랜 — "구두 지시 → 오프라인 PC 업무 자동화"

- 작성: 2026-07-03, 기준 HEAD `9363b9c` (8차 세션까지 완료, 총 260 checks locally validated)
- 목적: 이 문서 하나만 보고 **어떤 세션(하위 모델 포함)이든** 다음 작업을 이어갈 수 있게 한다.
- 읽는 규칙: 각 단계의 [작업 항목] → [검증 명령] → [완료 기준(DoD)] → [금지/가드레일] 순서로 그대로 수행한다.
  판단이 필요하면 "왜 이 순서인가"를 먼저 읽는다.

---

## 0. 최종 목표 (제품 정의)

> 사내 오프라인 내부망 PC에서, 로컬 LLM(EXAONE/Qwen 등)을 이용해,
> 사용자가 **구두로 지시**하면 컴퓨터 업무(문서/표/PPT/매크로/메일/브라우저/CAD)를
> **알아서 수행하고 증거와 함께 보고**하는 프로그램.

측정 가능한 성공 기준 (전 단계 완료 시):

| # | 기준 | 측정 방법 |
|---|------|----------|
| 1 | 대표 업무 10종 중 8종 이상 "지시→결과물" E2E 완료 (사람 개입은 승인 1회 이내) | 16단계 파일럿 체크리스트 |
| 2 | 7B급 weak model에서 tool-call 성공률 ≥ 95% | 10단계 capability-floor 벤치 |
| 3 | 모든 실행이 audit log에 남고, 모든 산출물이 quality validator 통과 | 12단계 orchestrator 검사 |
| 4 | 완전 오프라인 설치 가능 (인터넷 0회) | 14단계 반입 패키지 + setup 검증 |
| 5 | 음성 지시 → 텍스트 변환 정확도가 실사용 가능 수준 (한국어 업무 문장) | 13단계 STT 스모크 10문장 |

상태 어휘 (전 세션 공통, 절대 혼용 금지):
`implemented / locally validated / locally validated with mock / input-grounded /
artifact generated / static reviewed / app validation pending / company validation pending /
security cleanup pending`

---

## 1. 현재 위치 (v8) — 있는 것 / 없는 것

### 이미 있고 검증된 것 (재사용하라. 새로 만들지 마라)

| 계층 | 모듈 | 상태 |
|------|------|------|
| LLM 호출 | `lig_runtime.py` (재시도/fallback 호출 루프), `lig_providers.py` (secret-free 설정), `toolcall_parser.py` (깨진 tool-call 복구) | locally validated with mock |
| 실행 | `tool_dispatch.py` + `local_tools.py` (workspace 격리 파일 도구 7종, path-traversal 차단), `run_agent_loop` 멀티턴 | locally validated |
| 계획 | `capabilities.py` (keyword 라우팅+근거/confidence, 복합 분해, semantic planner hook) | locally validated |
| 입력 | `input_ingest.py` (CSV/LOG/코드/메일JSON 요약, secret 마스킹, unsupported 기록) | locally validated |
| 산출 | `artifact_generators.py` (5종 generator, 공유 context, 입력 근거 반영, enrich hook) | locally validated / input-grounded |
| 품질 | `artifact_quality.py` (kind별 규칙 + required_terms 가짜 성공 차단) | locally validated |
| 앱 연동 | `adapters/__init__.py` (4종 skeleton, 전부 available=false) | scaffold — app validation pending |
| 운영 | `doctor.py`, `launch/*.bat`, checkpoint/resume, 진단 파일 | locally validated |
| 테스트 | 9개 파일 260 checks | 전부 통과 유지 필수 |

### 아직 없는 것 = 이 문서의 나머지 전부

1. **real LLM 실측 0회** — mock으로만 검증됨. (최대 리스크)
2. **음성 입력 없음** — STT/마이크 캡처 미구현.
3. **앱 어댑터 실행 없음** — 매크로를 만들지만 실행은 못 함.
4. **한 명령 오케스트레이션 없음** — plan/agent/artifact가 분리된 명령.
5. **승인 게이트/audit log 없음** — 파괴적 작업 통제 장치 미비.
6. **오프라인 반입물 미확정** — dependencies.json에 PENDING_PREFETCH 잔존, 모델 파일 미정.
7. **git 히스토리에 내부 hostname 잔존** — 커밋 67e0028/be9f981 (security cleanup pending).

---

## 2. 목표 아키텍처 (최종 상태)

```text
[구두 지시] ──voice.bat──> whisper.cpp(STT, 오프라인) ──텍스트──┐
[텍스트 지시] ────────────────────────────────────────────────┤
                                                              v
                    agentops.py work  (12단계에서 신설)
                                                              v
   input_ingest(입력 자료) ─> plan_task(분해/근거) ─> WorkContext(공유)
                                                              v
        agent loop (lig_runtime + tool_dispatch + local_tools)
             ^ LLM 우선순위: ① 사내 gateway EXAONE/Qwen (company)
             |               ② PC-로컬 GGUF 서버 (llama.cpp/Ollama)
             |               ③ mock (파이프라인 검증용)
                                                              v
     artifact_generators + artifact_quality (+ LLM enrich, 검증 통과 시만)
                                                              v
     [승인 게이트] ─> adapters 실행 (browser CDP / Excel / HWP / SolidWorks)
                                                              v
        결과 보고(.md) + audit log(jsonl) + diagnostics(secret-free)
```

원칙 (모든 단계 공통):
- 코어는 stdlib-only 유지. 외부 패키지는 어댑터/음성 계층에만, 반드시 `release/dependencies.json`에 먼저 기록.
- 모든 새 기능은 mock으로 먼저 검증 → real은 별도 표기.
- 검증 못 한 것을 됐다고 말하지 않는다 (상태 어휘 준수).

---

## 3. 왜 이 순서인가 (의존성과 리스크 기준)

```text
9. 로컬 LLM real 실측(집)  ──> 10. weak-model floor ──> 12. work 오케스트레이터
                                     │                        │
11a. 브라우저 CDP 어댑터(집) ────────┘                        │
13. 음성 입력(집) ────────────────────────────────────────────┤
14. 오프라인 반입 패키지  <── 11b~d. Excel/HWP/SW 어댑터(회사) │
15. 보안/감사/운영 준비 ──────────────────────────────────────┤
16. 회사 파일럿 (전 단계 수렴) <──────────────────────────────┘
```

- **9단계가 무조건 먼저**: 지금까지 real mode는 한 번도 실행된 적 없다. 집 PC는 인터넷이
  되므로 Ollama+Qwen(소형)을 받아 **회사 가기 전에** "LLM이 실제로 도구를 부리는" 경로의
  리스크를 전부 태워야 한다. 이게 되면 회사에서는 base_url만 바꾸면 된다.
- 11a(브라우저 CDP)와 13(음성)은 **추가 의존성 없이/집에서** 검증 가능하므로 병렬 진행 가능.
- 11b~d(Office/HWP/SolidWorks)는 회사 PC(앱 존재)가 필요 → 14(반입) 이후 회사에서 마무리.
- 16(파일럿)은 모든 것의 수렴점.

예상 규모: 단계당 1~2 세션, 총 10~14 세션.

---

## 4. 단계별 상세 계획

> 공통 시작 의식(모든 세션, 생략 금지):
> ```bat
> cd /d "%USERPROFILE%\OpenCodeLIG_HOME_LAB\repo"
> git status -sb          (사용자 untracked 5개 외에 이상 없어야 함)
> git log --oneline -5    (HEAD 기록해 둘 것)
> cd workspace-template
> py -3.11 tests\test_capability_bench.py   (빠른 스모크; 시간 되면 9개 전부)
> ```
> 공통 종료 의식: 9개 테스트 전부 실행 → 전부 통과 시에만 commit/push → 메모리 갱신 → 보고.

---

### 9단계 — Real LLM 이중화 + 집에서 첫 실측 ★최우선★

**목적**: mock 검증을 real 검증으로 바꾼다. 회사 gateway 없이도 로컬 GGUF 서버로
agent loop 전체를 실측하고, 모델별 tool-call 형식 차이를 파서에 흡수한다.

**선행 조건**: 없음 (지금 바로 가능). 집 PC 인터넷 필요 (Ollama/모델 다운로드).

**작업 항목**:
1. `agent_ops/lig_providers.py`에 프로필 개념 추가 (기존 키 유지, 하위 호환):
   - `LIG_PROVIDER_PROFILE` env: `company_gateway`(기본) / `local_openai`(범용 OpenAI 호환).
   - `local_openai`는 secret 불필요: `LIG_LOCAL_BASE_URL`(기본 `http://127.0.0.1:11434/v1`),
     `LIG_LOCAL_MODEL`(기본 `qwen2.5:7b-instruct`)만 읽는다. validate_config가 프로필별로
     "무엇이 빠졌는지"를 정확히 말해야 한다.
2. `lig_runtime.py`: 프로필에 따라 요청 payload/헤더 구성 분기. **transport 주입 구조는
   그대로 유지** (기존 mock 테스트 14개가 깨지면 안 됨).
3. 집 PC 실측 절차 (문서화 포함, `launch/README.md`에 §5로 추가):
   ```bat
   ollama pull qwen2.5:7b-instruct   (또는 3b — 램 부족 시)
   set LIG_PROVIDER_PROFILE=local_openai
   run-agent.bat --mode real --task "메모.txt 파일을 읽고 요약해서 요약.md로 저장해줘"
   ```
4. 실측에서 나온 Qwen의 tool-call 원문을 `results/`에 저장하고, 깨진 형식이 있으면
   `toolcall_parser.py`에 복구 규칙 추가 (+ `test_toolcall_parser.py`에 실제 사례 기반 테스트).
5. `tests/test_real_llm_smoke.py` 신설: 서버가 안 떠 있으면 **전 항목 SKIP을 명시 출력**
   ("local llm not running — skipped, not failed")하고 exit 0. 떠 있으면 시나리오 3종
   (파일 요약 / 파일 생성 / 잘못된 도구명 복구) 실측.
6. doctor에 `llm_endpoints` 섹션: 프로필, base_url 도달성(연결만, secret 없음), 모델명.

**검증 명령**:
```bat
py -3.11 tests\test_lig_providers.py
py -3.11 tests\test_lig_runtime.py
py -3.11 tests\test_real_llm_smoke.py     (Ollama 켠 상태/끈 상태 각 1회)
run-agent.bat --mode real --task "..."     (위 3번)
```

**DoD**:
- [ ] 로컬 Qwen으로 "파일 읽고 요약 저장" E2E 최소 1회 성공, 산출물과 진단 파일 증빙
- [ ] Ollama 꺼진 상태에서 run-agent가 exit 2 + 원인 안내 (crash 금지)
- [ ] 기존 260 checks 무손상
- [ ] 보고 표기: "locally validated with local Qwen; EXAONE/사내 gateway는 company validation pending"

**금지/가드레일**:
- 로컬 실측 성공을 "회사 검증 완료"라고 절대 말하지 마라.
- Ollama 설치 실패 시 mock 코드 경로를 고치려 들지 마라 — 실패 사실과 원인만 보고.
- lig-api.env에 어떤 실제 값도 커밋하지 마라 (example 파일만).

---

### 10단계 — Weak-model capability floor (하위 모델 안정화)

**목적**: 7B급(가능하면 3B급) 모델에서도 tool-call이 안정적으로 돌게 만든다.
회사에서 쓸 모델 성능을 통제할 수 없으므로, 바닥 성능을 벤치로 고정한다.

**선행 조건**: 9단계 완료.

**작업 항목**:
1. `tests/test_capability_floor.py` 신설 (로컬 LLM 필요, 없으면 SKIP):
   시나리오 10종 × 반복 3회 → 성공률/실패 유형 집계를 `results/reports/capability_floor.md`로 저장.
   시나리오는 8차까지의 대표 업무를 재사용 (새 시나리오 발명 금지).
2. 실패 유형별 대응 (우선순위 순):
   - tool-call JSON 깨짐 → `toolcall_parser.py` 규칙 추가 (실측 사례 기반만)
   - 없는 도구 호출 → tool_dispatch의 오류 메시지에 "사용 가능 도구 목록" 자동 포함
   - 무한 사과/반복 → repeated-failure cutoff 파라미터 튜닝 (기존 구조 재사용)
   - 도구 안 쓰고 말로 때움 → 시스템 프롬프트에 "파일 작업은 반드시 도구 사용" 강조 1줄
3. 시스템 프롬프트/스키마는 **줄이는 방향**으로만 수정 (현재 ~2.3KB 초과 금지).
4. 3B/7B 모델별 성공률을 같은 리포트에 비교 기록.

**DoD**:
- [ ] 7B에서 tool-call 성공률 ≥ 95%, 3B 수치 기록 (달성 못 하면 수치 그대로 보고 — 조작 금지)
- [ ] capability_floor.md 리포트 생성, doctor에서 경로 노출
- [ ] 기존 테스트 무손상

**금지**: 성공률을 올리려고 시나리오를 쉽게 바꾸지 마라. 파서에 "모델이 안 낸 형식"을
추측으로 추가하지 마라 (실측 로그에 있는 형식만).

---

### 11a단계 — 브라우저 CDP 어댑터 (집에서 가능, 의존성 0)

**목적**: 첫 번째 **실행형** 어댑터. Chrome DevTools Protocol은 추가 설치가 필요 없어
"생성한 스크립트를 실제로 실행"하는 최초 사례로 최적.

**선행 조건**: 없음 (9단계와 병렬 가능). Chrome 존재 (doctor의 chrome_9222 체크 재사용).

**작업 항목**:
1. `agent_ops/adapters/browser_cdp.py`:
   - stdlib-only WebSocket 클라이언트 최소 구현 (RFC6455 클라이언트, 텍스트 프레임만, ~200줄)
     — 외부 패키지 금지. `http://127.0.0.1:9222/json`으로 탭 목록/생성은 urllib 사용.
   - `execute(action, options)` 지원 action: `open_url`, `get_title`, `extract_text`
     (Runtime.evaluate로 document.body.innerText), `screenshot`(Page.captureScreenshot →
     results/에 png 저장).
   - 로그인/입력 자동화는 이번 단계 범위 아님 (company validation pending 유지).
2. `adapters/__init__.py`의 browser 항목: execute 연결, **실제 Chrome으로 3개 action 성공 후에만**
   `available: True`로 변경 + `"validated": "local Chrome, <날짜>"` 기록.
3. `launch/chrome-debug.bat`: `--remote-debugging-port=9222 --user-data-dir=%TEMP%\opencodelig_chrome`
   로 기존 프로필과 분리해 기동.
4. `tests/test_browser_adapter.py`: 9222 안 떠 있으면 SKIP 명시. 떠 있으면 example.com
   open→title→extract 검증.

**DoD**:
- [ ] chrome-debug.bat → example.com 열고 텍스트 추출 실측 성공 (증빙: 결과 파일)
- [ ] browser adapter available=True (근거 문자열 포함), 나머지 3개 어댑터는 false 유지
- [ ] 사내 시스템 로그인은 여전히 company validation pending으로 표기

**금지**: 사용자 기본 Chrome 프로필로 디버그 포트를 열지 마라 (반드시 별도 user-data-dir).
selenium/playwright를 이 단계에서 도입하지 마라.

---### 11b~d단계 — Excel COM → HWP → SolidWorks 어댑터 (회사 PC 중심)

**목적**: 생성한 VBA/문서를 실제 앱에서 실행/변환한다.

**선행 조건**: 14단계에서 pywin32 wheel 반입 (Excel/HWP/SW 공통). 앱이 있는 PC.
집 PC에 Excel이 있으면 11b는 집에서 선검증 가능 (있는지 먼저 확인하고 시작).

**작업 항목** (어댑터당 동일 패턴, 한 세션에 하나씩):
1. `adapters/excel_com.py`: `execute(macro_path, workbook_path, options)`:
   - **원본은 절대 직접 수정 금지**: 항상 `사본_<원본명>`으로 복사 후 작업.
   - win32com으로 Excel 기동(Visible 옵션) → VBProject import는 보안 설정 이슈가 있으므로
     1차 구현은 "매크로 실행"이 아니라 **openpyxl 없는 순수 COM 데이터 작업**(셀 읽기/쓰기/
     저장)과 "사용자에게 Alt+F11 import 안내"의 이중 경로로 시작. VBProject 접근은
     Trust Center 설정 확인 후 2차.
   - 실패 시 Excel 프로세스 잔류 방지 (finally에서 Quit + 프로세스 확인).
2. `adapters/hwp_com.py`: HwpFrame COM으로 문서.md → hwp 변환 (텍스트 유입 수준부터).
3. `adapters/solidworks_com.py`: SldWorks.Application 접속 → 열린 문서 확인 → 생성된
   매크로의 RunMacro 실행. **반드시 사본 문서에서만** (문서 자동 저장 금지, 사용자 확인 후 저장).
4. 각 어댑터: 실제 앱에서 시나리오 3종 성공 로그를 `validation/` 아닌
   `workspace-template/agent_ops/results/adapter_validation/`에 남긴 뒤에만 available=True.
5. `tests/test_office_adapters.py`: 앱 없으면 SKIP 명시 (CI에서도 SKIP으로 통과해야 함).

**DoD** (어댑터별):
- [ ] 사본 기반 실행 1회 이상 성공 + 로그 증빙 → 그때만 available=True
- [ ] 앱 없는 PC에서 테스트가 SKIP으로 정직하게 통과
- [ ] 실패해도 앱 프로세스/파일 잔류 없음

**금지**: 앱이 없는 PC에서 available=True로 바꾸지 마라. 원본 파일을 직접 조작하지 마라.
"COM 코드를 작성했다"를 "앱 검증 완료"라고 보고하지 마라 (static reviewed로 표기).

---

### 12단계 — `work` 오케스트레이터 + 승인 게이트 + audit log

**목적**: "한 명령이면 끝"을 만든다. 음성(13단계)이 최종적으로 꽂히는 자리.

**선행 조건**: 9단계. (어댑터는 있으면 실행, 없으면 pending 안내 — 의존 아님)

**작업 항목**:
1. `agentops.py`에 `work` subcommand:
   ```bat
   py -3.11 agent_ops\agentops.py work --task "..." [--input 경로]... [--mode mock|real] [--execute] [--yes]
   ```
   흐름: ingest → plan(+출력) → **승인 게이트** → agent loop(파일 작업이 필요한 경우) →
   artifact 생성+품질 검증 → (--execute && adapter available 시) 어댑터 실행 →
   최종 보고 `results/reports/work_<run_id>.md` 생성.
2. 승인 게이트 (`agent_ops/approval.py`):
   - 위험 분류: `safe`(파일 생성/읽기, workspace 내) / `caution`(기존 파일 수정) /
     `dangerous`(workspace 밖 쓰기, 앱 실행, 삭제).
   - dangerous는 콘솔 y/n 확인 (구체적으로 "무엇을 하려는지" 목록 제시). `--yes`로 일괄 승인
     가능하되 audit에 "auto-approved" 기록.
3. `agent_ops/audit.py`: append-only `%USERPROFILE%\OpenCodeLIG_USERDATA\audit\audit.jsonl`
   — {ts, run_id, task 앞 80자, tool/adapter, target, verdict}. **secret/파일 내용은 기록 금지**.
   tool_dispatch와 adapter 실행 경로 양쪽에 훅.
4. 최종 보고 md: 요청/입력 요약/계획/수행 내역/산출물 목록+품질 결과/pending/다음 명령.
5. `tests/test_work_command.py`: mock 모드 E2E (승인 게이트는 --yes 경로 + 거부 경로 모두).

**DoD**:
- [ ] `work --task "시험 결과 파일 읽고 보고서 만들어줘" --input ... --mode mock` 한 줄로
      보고서+품질검증+최종 보고 md까지 생성
- [ ] dangerous 작업이 승인 없이 실행되지 않음 (거부 테스트 통과)
- [ ] audit.jsonl에 전 과정 기록, secret 없음
- [ ] 기존 테스트 무손상

**금지**: 승인 게이트를 우회하는 기본값(--yes 기본 on) 금지. audit 실패가 작업을 죽이면 안 됨
(try/except, 단 실패 사실은 stderr 경고).

---

### 13단계 — 음성 입력 (구두 지시) — 집에서 검증 가능

**목적**: "구두로 지시"를 실현한다. 완전 오프라인 STT.

**기술 선택 (근거)**:
- STT: **whisper.cpp** (exe + GGML 모델 파일만 반입, pip 의존성 0) — faster-whisper보다
  오프라인 반입이 압도적으로 단순. 한국어는 `ggml-small`(465MB)부터 시작, 부족하면 medium.
- 녹음: whisper.cpp 공식 배포의 `whisper-cli`는 wav 입력이므로, 녹음은
  **ffmpeg.exe 단일 실행파일** (`ffmpeg -f dshow -i audio=...`) 또는 whisper.cpp의
  `whisper-stream.exe`(SDL2 동봉 빌드, 마이크 직접) 중 실측 후 선택.
- 피드백(TTS, 옵션): Windows 내장 SAPI (`PowerShell Add-Type System.Speech`) — 설치 0.
  한국어 보이스(Heami) 존재 여부는 회사 PC에서 확인.

**작업 항목**:
1. `release/dependencies.json`에 whisper.cpp exe/모델/ffmpeg 항목 추가 (URL+SHA256, 14단계에서 prefetch).
2. `agent_ops/voice_input.py` (stdlib): 녹음 subprocess → whisper-cli subprocess → 텍스트
   후처리(앞뒤 공백/타임스탬프 제거) → 반환. 실패 시 "텍스트로 입력하세요" 안내.
3. `launch/voice.bat`: 누르면 N초 녹음(기본 8초, 인자로 조정) → STT → 인식 문장 표시 →
   `y` 확인 후 `work` 명령으로 전달. **인식 오류로 잘못된 작업이 실행되는 것을 확인 단계로 방지.**
4. `tests/test_voice_input.py`: exe/모델 없으면 SKIP. 있으면 동봉 샘플 wav(직접 녹음해 커밋,
   1~2초 "보고서 만들어줘")로 STT 텍스트에 "보고서" 포함 확인.
5. doctor에 `voice` 섹션: whisper exe/모델/ffmpeg 존재 여부, 샘플 STT 스모크 결과.

**DoD**:
- [ ] 집 PC에서 마이크 → "시험 결과 정리해서 보고서 만들어줘" → work 실행까지 E2E 1회 성공
- [ ] 한국어 10문장 스모크 결과 기록 (오인식은 오인식대로 기록)
- [ ] 음성 없이도 모든 기능이 동작 (음성은 부가 계층임을 코드 구조로 보장)

**금지**: 인식 텍스트를 확인 없이 바로 실행하는 기본값 금지. 녹음 파일을 repo에 커밋하지
마라 (테스트용 1개 샘플 wav 제외, 1MB 미만).

---

### 14단계 — 오프라인 반입 패키지 완성

**목적**: 인터넷 0회로 회사 PC에 전체 시스템을 설치 가능하게 한다.

**선행 조건**: 9/11a/13단계에서 무엇이 실제로 필요한지 확정된 후. (미리 하면 두 번 일함)

**작업 항목**:
1. `release/dependencies.json`의 모든 PENDING_PREFETCH 해소: 집 PC에서 실제 다운로드 →
   SHA256 계산 → manifest에 기록. 대상(확정분): pywin32, openpyxl, python-pptx,
   whisper.cpp(exe+ggml-small ko 검증본), ffmpeg, (선택) chromedriver.
2. LLM 모델 반입 계획 확정 — **사용자 확인 필요 항목** (§6 참조): 회사 반입 정책상
   GGUF 파일(수 GB) 반입이 가능한가? 가능하면 Qwen GGUF + llama.cpp server exe 포함,
   불가면 gateway-only로 확정하고 로컬 서빙 항목은 계획에서 제거.
3. `release/build_bundle.py` (stdlib): repo + wheels + exe + 모델 → 단일 zip + 매니페스트
   (전 파일 SHA256). GitHub Actions "Build offline package"와 정합 유지.
4. `release/setup.bat`: 회사 PC에서 zip 풀고 실행 → py 확인 → pip 오프라인 설치
   (`pip install --no-index --find-links wheels\ ...`) → doctor 실행 → 결과 요약.
5. `docs/BRING_IN_CHECKLIST.md`: 반입 매체 준비물 / 순서 / 설치 후 확인 명령 목록.

**DoD**:
- [ ] 집 PC에서 "인터넷 차단 상태(네트워크 어댑터 비활성)"로 setup.bat 전체 리허설 성공
- [ ] 매니페스트의 모든 항목에 SHA256 존재, PENDING_PREFETCH 0건
- [ ] doctor가 설치 직후 전 섹션 정상 보고

**금지**: 검증 안 된 URL을 manifest에 넣지 마라. 모델 파일을 git에 커밋하지 마라
(zip 번들에만 포함, .gitignore 확인).

---

### 15단계 — 보안/감사/운영 준비

**작업 항목**:
1. **git 히스토리 purge** (사용자 승인 필수 — 승인 없이 절대 실행 금지):
   ```bat
   pip download git-filter-repo (집에서) →
   git filter-repo --replace-text replacements.txt   (내부 hostname → placeholder)
   git push --force origin rebuild/fable5-open-architecture
   ```
   실행 전 로컬 전체 백업 clone 필수. PR/이슈 텍스트도 점검.
2. secret 스캔 pre-commit: `tools\` 말고 `workspace-template/scripts/precommit_scan.py`
   (stdlib, 패턴: api_key/token/password/내부 도메인 패턴) + 설치 안내.
3. 운영 runbook `docs/RUNBOOK.md`: 증상별 대응 (LLM 무응답/도구 실패 반복/인코딩 깨짐/
   어댑터 행) — 전부 기존 diagnostics 파일 경로와 연결.
4. audit log 순환(크기 제한) 정책.

**DoD**: 히스토리에서 내부 hostname 검색 0건 (`git log -S` 확인) / 스캔 훅 동작 / runbook 존재.

---

### 16단계 — 회사 PC 파일럿 (최종 수렴)

**첫 출근일 체크리스트 (순서대로)**:
1. 반입 zip → setup.bat → doctor 전 섹션 확인.
2. `lig-api.env` 작성 (gateway URL/키 — 파일은 repo 밖 USERDATA, 절대 커밋 금지).
3. gateway 스모크: `run-agent.bat --mode real --task "간단한 파일 요약"` — EXAONE/Qwen 각각.
4. tool-call 형식 실측 → 필요 시 파서 보강 (10단계 절차 재사용).
5. 대표 업무 10종 실행 (아래 표), 각각 성공/실패/소요시간 기록:

| # | 업무 | 사용 경로 |
|---|------|----------|
| 1 | 시험 CSV → 이상값 보고서+PPT | work --input |
| 2 | 메일 목록 분류+액션아이템 | work --input |
| 3 | 로그 원인 분석 문서 | work --input |
| 4 | Excel 데이터 정리 (COM 실행) | work --execute |
| 5 | 기존 매크로 검토 문서 | work --input |
| 6 | 사내 페이지 텍스트 추출 | browser adapter |
| 7 | 회의자료 초안 (문서+PPT) | work |
| 8 | HWP 변환 | hwp adapter |
| 9 | SolidWorks 매크로 실행 | sw adapter (사본) |
| 10 | 음성 지시로 1~3 중 하나 재실행 | voice.bat |

6. 실패 항목 → `docs/PILOT_BACKLOG.md`에 원인/재현/우선순위 기록 → 다음 세션들의 입력.

**DoD**: 10종 결과표 작성 (성공률 조작 금지), backlog 생성, company validation pending
항목들의 실제 해소 여부를 상태 어휘로 갱신.

---

## 5. 하위 모델 세션 실행 프로토콜 (실수 방지 규약 — 전 세션 필수)

### 5.1 불변 규칙 (위반 = 세션 실패)

1. **기존 테스트가 깨지면**: 원인 파악 → 못 고치면 변경 revert → 사실대로 보고. 테스트를
   약화시켜 통과시키는 것 금지.
2. **성공 어휘 통제**: §0의 상태 어휘만 사용. mock 검증을 real이라, scaffold를 완성이라,
   로컬을 회사 검증이라 말하지 않는다. 전체 제품 성공 선언 금지.
3. **secret/내부 hostname**: 코드/커밋/보고 어디에도 출력 금지. lig-api.env 실값 커밋 금지.
4. **repo 루트의 사용자 untracked 5개** (.gitignore, docs/home-lab-status.md, logs/, tools/,
   validation/) 건드리지 않기. 커밋은 항상 **개별 파일 git add** (git add -A 금지).
5. **파괴적 git 작업** (force push, filter-repo, reset --hard) 은 사용자 승인 텍스트가 이번
   세션에 명시돼 있을 때만.
6. **새 외부 의존성**: dependencies.json에 먼저 기록 + 사유. 코어(agent_ops 비어댑터부)는
   stdlib-only 유지.
7. **테스트 작성 규칙**: pytest 금지, 기존 check(label, cond) 스타일. 외부 자원(LLM/앱/포트)
   필요 테스트는 없을 때 SKIP을 exit 0으로 명시 출력.
8. **막혔을 때**: 같은 접근 2회 실패 시 접근을 바꾼다. 3회 실패 시 그 항목을 pending으로
   보고하고 다음 항목 진행 (세션 전체를 태우지 않는다).

### 5.2 세션 프롬프트 템플릿 (복붙용)

```text
이전 결과를 이어서 OpenCodeLIG 작업을 계속해라. 이번 세션은 MASTER_PLAN.md의 <N>단계다.
1) workspace-template/docs/MASTER_PLAN.md 의 <N>단계 섹션을 읽어라.
2) 공통 시작 의식을 수행해라 (git 상태 + 테스트 스모크).
3) [작업 항목]을 순서대로 구현해라. 판단이 필요하면 "왜 이 순서인가"와 5.1 불변 규칙을 따르라.
4) [검증 명령]을 실행하고, [DoD] 각 항목을 체크해라. 못 채운 항목은 pending으로 남겨라.
5) 9개 기존 테스트 + 신규 테스트 전부 통과 시에만 commit/push 해라.
6) 최종 보고는 기존 형식(Outcome/Files changed/.../Next exact command)으로, 상태 어휘를 지켜라.
```

### 5.3 보고 형식 (전 세션 동일)

```text
Outcome: / Files changed: / (단계별 핵심 섹션): / Local validation: /
App/company validation pending: / Dependency impact: / Maintainability notes: /
Security cleanup status: / New HEAD commit: / Next exact command:
```

---

## 6. 사용자 확인 필요 항목 (진행 중 결정 필요 — 세션이 임의 결정 금지)

| # | 질문 | 영향 단계 | 미확인 시 기본값 |
|---|------|----------|----------------|
| 1 | 회사 PC 사양 (RAM/GPU/디스크 여유) | 9, 14 | gateway-only 가정 |
| 2 | 사내 gateway 스펙 (엔드포인트 형식, 모델명, 인증 방식) | 9, 16 | OpenAI 호환 가정, lig-api.env로 흡수 |
| 3 | 반입 매체 정책 (USB 허용? 용량? 수 GB 모델 파일 가능?) | 14 | wheel/exe만(수백 MB) 가정 |
| 4 | 집 PC에 Excel 있는지 | 11b | 없다고 가정 (회사에서 검증) |
| 5 | git 히스토리 purge 승인 (force push 동반) | 15 | 보류 (pending 유지) |
| 6 | 회사 PC 마이크 존재/사용 정책 | 13 | 있다고 가정, 없으면 텍스트-only |
| 7 | SolidWorks/HWP 버전 | 11c,d | COM late-binding으로 흡수 |

---

## 7. 리스크 레지스터 (대비책 내장)

| 리스크 | 가능성 | 대비 (계획 반영 위치) |
|--------|--------|----------------------|
| gateway 형식이 OpenAI 비호환 | 중 | lig_runtime payload 분기 + 16단계 1일차 스모크로 조기 발견 |
| weak model이 tool-call 자체를 못 함 | 중 | 10단계 floor 벤치 + 파서 복구 + 최악 시 "명령 선택형" UI로 강등 (별도 백로그) |
| 모델 파일 반입 불가 | 중 | gateway-only 경로가 독립 동작 (9단계 프로필 분리가 보험) |
| VBProject COM 보안 차단 | 높음 | 11b 이중 경로 (COM 데이터 작업 + 수동 import 안내) |
| STT 한국어 인식률 부족 | 중 | 13단계 확인 게이트 + medium 모델 업그레이드 여지 |
| Chrome 버전 이슈 | 낮음 | CDP는 드라이버 불필요 (11a 선택 근거) |
| 인코딩(cp949) 사고 재발 | 낮음 | 기존 BAT 규약(PYTHONUTF8=1) 전 신규 BAT에 복제 |

---

## 8. 다음 세션이 시작해야 할 정확한 지점

> **9단계.** 시작 명령:
> ```bat
> cd /d "%USERPROFILE%\OpenCodeLIG_HOME_LAB\repo\workspace-template"
> py -3.11 tests\test_capability_bench.py
> ```
> 이후 §4의 9단계 [작업 항목] 1번(lig_providers 프로필)부터.
