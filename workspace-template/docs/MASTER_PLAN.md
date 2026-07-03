# OpenCodeLIG 마스터플랜 v2 — "구두 지시 → 오프라인 PC 업무 자동화"

- 작성: 2026-07-03 (v2 — 사용자 환경/업무 확정 답변 반영, v1 대체), 기준 HEAD `d68b2c0`
- 목적: 이 문서는 **전략**(왜/무엇을/어떤 순서로)을 담는다.
- **실행 추적은 repo 루트 `plan/`에서 한다**: 작업 보드 `plan/STATUS.md`, 세분화된
  지시서 `plan/tasks/`(P단계를 1커밋 단위로 분해), 보고서/리뷰 루프. 구현 워커는
  이 문서가 아니라 `plan/README.md` → `plan/STATUS.md` → 본인 task 순서로 진입한다.
- 읽는 규칙: 담당 단계 섹션의 [작업 항목] → [검증 명령] → [완료 기준(DoD)] → [금지/가드레일]을
  순서대로 그대로 수행한다. 판단이 필요하면 §3(순서 근거)과 §7(불변 규칙)을 따른다.

---

## 0. 최종 목표 (제품 정의)

> 사내 오프라인 내부망 PC에서, H100 서버의 로컬 LLM API(EXAONE-4.5-33B / Qwen3.6-27B)를 이용해,
> 사용자가 지시하면(텍스트 우선, 음성은 확장 예약) **비서 업무·일정 관리·주요 소프트웨어 매크로
> 작업**을 알아서 수행하고 증거와 함께 보고하는 프로그램.

사용자가 확정한 3대 핵심 업무 (모든 우선순위 판단의 기준):
1. **비서 역할** — 브리핑, 메일 분류/액션아이템, 회의록 정리, 보고서 초안
2. **일정 관리** — 일정 등록/조회/리마인드, 마감 추적
3. **주요 소프트웨어 매크로 작업** — Excel/HWP/SolidWorks/ANSYS/MATLAB/AutoCAD 자동화

측정 가능한 최종 성공 기준:

| # | 기준 | 측정 |
|---|------|------|
| 1 | 파일럿 업무 12종(§P19) 중 10종 이상 "지시→결과물" E2E (사람 개입은 승인 1회 이내) | P19 결과표 |
| 2 | gateway(EXAONE/Qwen) tool-call 성공률 ≥ 95% | P11 floor 벤치 |
| 3 | 모든 실행 audit log 기록 + 모든 산출물 quality validator 통과 | P13 검사 |
| 4 | 인터넷 0회로 회사 PC 전체 설치 (반입 zip 1개) | P17 리허설 |
| 5 | 생성된 Office 매크로가 **Office 2016**에서 실행됨 | P15 실측 |

상태 어휘 (혼용 금지): `implemented / locally validated / locally validated with mock /
input-grounded / artifact generated / static reviewed / app validation pending /
company validation pending / security cleanup pending`

---

## 1. 확정 환경 (2026-07-03 사용자 답변 — 변경 시 이 표부터 갱신)

### 1.1 LLM (변경 불가 — 사용자 권한 밖)

| 항목 | 값 |
|------|-----|
| 서빙 | 사내 H100 서버, **API로만 접근** (자원 넉넉 → 긴 컨텍스트/enrich 적극 활용 가능) |
| 모델 | **EXAONE-4.5-33B** (coding/chat 라우트, think_off 변형), **Qwen3.6-27B** (fallback 라우트) |
| API 형식 | OpenAI 호환. 라우트가 URL 경로에 인코딩됨 — 이미 `agent_ops/lig_providers.py`의 `_ROUTE_DEFAULTS`에 반영: `lig-coding`(/EXAONE-4.5-33B-vibe_coding_think_off/v1), `lig-chat`(/EXAONE-4.5-33B-default_think_off/v1), `lig-fallback`(/Qwen3.6-27B-vibe_coding_think_off/v1) |
| secret | `%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env` (LIG_GATEWAY_BASE_URL, LIG_API_KEY). **절대 커밋/출력 금지** |
| 변경 대응 | 라우트/모델/타임아웃은 lig-api.env의 env 키로 오버라이드 (P9에서 완전 오버라이드로 확장) |

### 1.2 하드웨어

| PC | 사양 | 역할 |
|----|------|------|
| 사내 업무 PC | i7-14700K / **RAM 128GB(실측)** / RTX 2000 Ada 16GB / SSD 1TB + HDD 2TB / **Windows 10 19044·21H2(실측 — 사용자 답변과 다름, probe 우선)** / Python 3.11.3 + pywin32 설치됨(실측) | 운영. gateway API 사용. (16GB VRAM+128GB RAM → 비상용 로컬 GGUF 서빙 여유 큼) |
| 집 개발 PC | Ryzen 3500X / RAM 16GB / RTX 2060 Super 8GB / SSD 1TB / **Windows 10** | 개발/선검증. 로컬 실측 모델: **Qwen2.5-7B-Instruct Q4** (8GB VRAM 상한 기준) |

### 1.3 사내 소프트웨어 (버전 고정 — 호환성 기준)

| SW | 버전 | 자동화 경로 (확정) |
|----|------|-------------------|
| MS Office | **2016** (전 제품 2016 기준으로 맞출 것) | COM (win32com) + VBA. **2016에 없는 함수 금지 (§6.2)** |
| 한글(HWP) | 2019 | HwpFrame COM |
| SolidWorks | 2022 한글판 | SldWorks COM (late binding, 기존 VBA scaffold와 정합) |
| ANSYS | 2024R1 — Mechanical, SpaceClaim, Classic Icepak, Fluent | Fluent: journal(.jou) + `fluent -g -i` 배치 / Mechanical: ACT(Python) 스크립트 / SpaceClaim: 스크립트(IronPython) — 생성 우선, 실행은 앱 검증 |
| MATLAB | 2024a | `.m` 생성 + `matlab -batch` CLI 실행 (COM 불필요, 가장 안정적) |
| AutoCAD | 2019 | `.scr` 스크립트/AutoLISP 생성 + `accoreconsole.exe` 배치 실행 |
| 브라우저 | Chrome | CDP (드라이버/설치 불필요) |

### 1.4 기타 확정 사항

- 반입 용량 제한 **없음** → GGUF 모델/whisper 모델 반입 가능.
- 집 Excel은 최신 버전 → **"집에서 됨" ≠ "2016 호환"**. §6.2 금지 목록 + 회사 실측이 최종.
- git 히스토리 purge **사용자 승인 확보됨 (2026-07-03)** → P10에서 실행.
- 마이크: 존재하나 당장 미사용 → 음성은 **인터페이스만 설계**(P13), 구현은 P20으로 예약.

---

## 2. 목표 아키텍처

```text
[텍스트 지시 / (예약) 음성] ──> agentops.py work (P13 신설)
        v
input_ingest(xlsx 포함, P14 확장) ─> plan_task(분해/근거) ─> WorkContext(공유)
        v
agent loop (lig_runtime + tool_dispatch + local_tools)
   ^ LLM 라우팅(P9): lig-coding(EXAONE, 도구/매크로/코드)
   |                lig-chat(EXAONE, 문서/요약/한국어)
   |                lig-fallback(Qwen3.6, EXAONE 실패 시 자동)
   |                local_openai(집 Qwen 7B — 개발 전용)  |  mock(파이프라인 검증)
        v
artifact_generators + artifact_quality (+ enrich: H100이라 적극 사용, 검증 통과 시만 대체)
        v
[승인 게이트(P13)] ─> adapters 실행
   browser CDP(P12) | Office 2016 COM(P15) | HWP/SW/MATLAB/AutoCAD/ANSYS(P16)
        v
결과 보고(.md) + audit log(jsonl) + 비서/일정 모듈(P14: briefing/schedule/reminder)
```

확장 원칙 (사용자 요구 "추후 변경에도 맞출 수 있는 구조"의 구현 방식):
- **모든 확장점은 registry**: capability = `CAPABILITIES` 항목, 산출물 = `GENERATORS` 함수,
  실행 = `adapters/` 모듈, LLM = provider 라우트(env 오버라이드). if/else 특수 처리 금지.
- gateway 스펙 변경은 **코드 수정 없이 lig-api.env 키 변경만으로** 흡수돼야 한다 (P9 DoD).
- 코어(agent_ops 비어댑터부)는 stdlib-only 유지. 외부 패키지는 어댑터/ingest 확장에만,
  반드시 `release/dependencies.json` 선기록.

---

## 3. 단계 구성과 순서 근거

| 단계 | 내용 | 장소 | 선행 |
|------|------|------|------|
| **P9** | Real LLM 연결 완성 (gateway 정합 + env 완전 오버라이드 + 집 Qwen 실측) | 집 | — |
| **P10** | git 히스토리 purge (승인 확보됨 — 짧은 전용 세션) | 집 | — |
| **P11** | weak-model capability floor (집 Qwen 7B 기준 벤치) | 집 | P9 |
| **P12** | 어댑터 1차: 브라우저 CDP (의존성 0, 첫 실행형) | 집 | — |
| **P13** | `work` 오케스트레이터 + 승인 게이트 + audit log | 집 | P9 |
| **P14** | 비서/일정 관리 모듈 (schedule/briefing/reminder/회의록) + xlsx ingest | 집 | P13 |
| **P15** | Office 2016 어댑터 (Excel COM 우선, Outlook/Word/PPT) + 2016 호환 규칙 | 집(선검증)→회사 | P17 일부(pywin32) |
| **P16** | 엔지니어링 어댑터 (HWP/SolidWorks/MATLAB/AutoCAD/ANSYS) | 회사 중심 | P15 패턴 |
| **P17** | 오프라인 반입 패키지 (전 의존성+모델, 인터넷 차단 리허설) | 집 | P9~P15 확정분 |
| **P18** | 운영/보안 마무리 (secret 스캔 훅, runbook, audit 순환) | 집 | — |
| **P19** | 회사 파일럿 (업무 12종 실측) | **회사** | 전부 |
| **P20** | 음성 입력 구현 (whisper.cpp — 예약, 파일럿 후) | 집→회사 | P13 |

순서 근거:
- **P9 최우선**: real mode 실측 0회가 최대 리스크. 집 Qwen으로 태운다. gateway는 코드상
  이미 정합(lig_providers)이므로 회사에서는 lig-api.env만 채우면 된다.
- **P10을 앞으로**: 승인이 확보됐고, 공개 repo에 내부 hostname이 남아있는 것은 지금도
  진행 중인 리스크. 독립 작업이라 언제든 가능 → 즉시 처리.
- **P14(비서/일정)를 어댑터보다 앞에**: 사용자 3대 업무 중 2개(비서, 일정)가 앱 없이도
  완성 가능(stdlib + 기존 파이프라인). 가치가 가장 빨리 나온다.
- P15/P16은 pywin32 반입(P17 일부 선행)과 회사 앱이 필요 → 뒤에.
- 예상 규모: 단계당 1~2 세션, 총 12~16 세션.

---

## 4. 단계별 상세 계획

> **공통 시작 의식** (모든 세션, 생략 금지):
> ```bat
> cd /d "%USERPROFILE%\OpenCodeLIG_HOME_LAB\repo"
> git status -sb    (사용자 untracked 5개 외 이상 없어야 함)
> git log --oneline -5
> cd workspace-template
> py -3.11 tests\test_capability_bench.py
> ```
> **공통 종료 의식**: 9개 기존 테스트 + 신규 테스트 전부 실행 → 전부 통과 시에만
> 개별 `git add` → commit/push → 메모리 갱신 → §7.3 형식 보고.

---

### P9 — Real LLM 연결 완성 + 집 실측 ★다음 세션★

**목적**: gateway 클라이언트를 "스펙 변경에도 코드 수정 없이 대응"하는 형태로 완성하고,
집 Qwen 7B로 agent loop 전체를 처음으로 실측한다.

**작업 항목**:
1. `lig_providers.py` 확장 (기존 키/함수 시그니처 유지 — 15개 테스트 무손상):
   - env 완전 오버라이드: `LIG_MODEL_CODING/CHAT/FALLBACK`(모델명), 기존 `LIG_ROUTE_*`(경로),
     `LIG_API_TIMEOUT_SEC` — **라우트 추가/모델 교체가 env 편집만으로 가능**해야 한다.
   - 프로필: `LIG_PROVIDER_PROFILE=company_gateway`(기본) / `local_openai`.
     local_openai는 secret 불필요: `LIG_LOCAL_BASE_URL`(기본 http://127.0.0.1:11434/v1),
     `LIG_LOCAL_MODEL`(기본 qwen2.5:7b-instruct).
   - `config/lig-api.env.example`에 신규 키 전부 주석과 함께 반영.
2. `lig_runtime.py`: 프로필 분기. transport 주입 구조 유지 (mock 테스트 14개 보존).
3. **작업 유형→라우트 자동 선택**: plan의 capability로 결정 — 매크로/코드/파일 작업은
   lig-coding, 문서/요약/메일 분류는 lig-chat, 호출 실패·비정상 응답 시 lig-fallback
   (기존 fallback 정책 재사용). 선택 결과를 진단에 기록.
4. 집 실측 (Ollama):
   ```bat
   ollama pull qwen2.5:7b-instruct
   set LIG_PROVIDER_PROFILE=local_openai
   run-agent.bat --mode real --task "메모.txt 파일을 읽고 요약해서 요약.md로 저장해줘"
   ```
   (16GB RAM/8GB VRAM 주의: 7b가 무거우면 `qwen2.5:3b-instruct`로 낮추고 그 사실 기록)
5. 실측 tool-call 원문을 results/에 수집 → 깨진 형식은 `toolcall_parser.py`에 규칙 추가
   (+실사례 기반 테스트 추가).
6. `tests/test_real_llm_smoke.py`: 서버 없으면 "local llm not running — skipped, not failed"
   출력 후 exit 0. 있으면 3 시나리오(요약/생성/오류 복구).
7. doctor `llm_endpoints` 섹션: 프로필, 라우트별 설정 여부(presence만), base_url 도달성
   (**host 문자열 출력 금지** — ok/fail만).

**검증 명령**: `test_lig_providers.py`, `test_lig_runtime.py`, `test_real_llm_smoke.py`
(서버 on/off 각 1회), 4번 실측.

**DoD**:
- [ ] 집 Qwen으로 "파일 읽고 요약 저장" E2E ≥1회 성공 (산출물+진단 증빙)
- [ ] 라우트/모델 변경이 lig-api.env 편집만으로 반영됨을 테스트로 증명
- [ ] Ollama 꺼진 상태에서 exit 2 + 원인 안내 (crash 금지)
- [ ] 기존 260 checks 무손상
- [ ] 보고: "locally validated with local Qwen; EXAONE-4.5-33B/Qwen3.6-27B gateway는 company validation pending"

**금지**: 로컬 실측 성공을 회사 검증이라 말하기. lig-api.env 실값 커밋. 실측 실패 시
mock 경로 수정으로 도피 (실패 사실만 보고).

---

### P10 — git 히스토리 purge (승인 확보됨: 2026-07-03)

**목적**: 공개 repo 히스토리의 내부 hostname(커밋 67e0028, be9f981) 제거.

**작업 항목** (순서 엄수):
1. 전체 백업: `git clone --mirror` 를 repo 밖 별도 폴더에 (완료 확인 전 다음 단계 금지).
2. 집 PC에서 `pip install git-filter-repo` (인터넷 가능).
3. `replacements.txt` 작성: 내부 hostname → `INTERNAL-GATEWAY-PLACEHOLDER`.
   (hostname 원문은 이 파일에만, **커밋 금지** — 사용 후 삭제)
4. `git filter-repo --replace-text replacements.txt` → 로컬 히스토리 전수 검사:
   `git log --all -S"<hostname 일부>" --oneline` 결과 0건 확인.
5. `git push --force origin rebuild/fable5-open-architecture` (+다른 브랜치도 오염 시 처리).
6. GitHub PR #8 본문/코멘트에 hostname 있는지 육안 점검 → 있으면 편집.
7. 완료 후 상태 어휘 갱신: security cleanup **done** (이후 보고에서 pending 제거).

**DoD**: 히스토리 전체 검색 0건 / 백업 존재 / push 후 원격 재클론으로 재확인.

**금지**: 백업 없이 filter-repo 실행. replacements.txt 커밋. 이 단계에서 다른 코드 수정
섞기 (순수 purge 세션으로 유지 — 사고 시 원인 분리).

---

### P11 — Weak-model capability floor

v1과 동일 골자. 대상: 집 Qwen 7B(필수), 3B(참고). 회사 모델(33B/27B)은 훨씬 크므로
집 floor 통과 = 회사 여유. `tests/test_capability_floor.py` (LLM 없으면 SKIP),
시나리오 10종 × 3회 성공률을 `results/reports/capability_floor.md`로. 실패 유형별 대응은
파서 규칙(실측 기반만)/오류 메시지 개선/프롬프트 다이어트(2.3KB 초과 금지) 순.
**DoD**: 7B 성공률 수치 보고(목표 ≥90%, 미달 시 수치 그대로) + 기존 테스트 무손상.

---

### P12 — 브라우저 CDP 어댑터 (첫 실행형)

v1과 동일. `adapters/browser_cdp.py`: stdlib WebSocket 클라이언트(RFC6455, ~200줄) +
`http://127.0.0.1:9222/json`. action: open_url / get_title / extract_text / screenshot.
`launch/chrome-debug.bat`은 **반드시 별도 user-data-dir**. 실측 3 action 성공 후에만
available=True. 사내 시스템 로그인은 company validation pending 유지.
`tests/test_browser_adapter.py` (9222 없으면 SKIP).

---

### P13 — `work` 오케스트레이터 + 승인 게이트 + audit log

**목적**: "한 명령이면 끝". 비서 모듈(P14)과 음성(P20)이 꽂히는 자리.

**작업 항목**:
1. `agentops.py work`:
   ```bat
   py -3.11 agent_ops\agentops.py work --task "..." [--input 경로]... [--mode mock|real] [--execute] [--yes]
   ```
   흐름: ingest → plan 출력 → **승인 게이트** → (필요 시) agent loop → artifact+품질 →
   (--execute && adapter available) 어댑터 실행 → 최종 보고 `results/reports/work_<run_id>.md`.
2. `agent_ops/approval.py`: 위험 분류 `safe`(workspace 내 생성/읽기) / `caution`(기존 파일
   수정) / `dangerous`(workspace 밖 쓰기, 앱 실행, 삭제, 일정 변경). dangerous는 실행 전
   "무엇을 할지" 목록 제시 후 y/n. `--yes`는 audit에 auto-approved 기록.
3. `agent_ops/audit.py`: append-only `%USERPROFILE%\OpenCodeLIG_USERDATA\audit\audit.jsonl`
   {ts, run_id, task 80자, tool/adapter, target, verdict}. **secret/파일 내용 기록 금지.**
   tool_dispatch와 adapter 실행 양쪽에 훅. audit 실패는 경고만 (작업 중단 금지).
4. `tests/test_work_command.py`: mock E2E + 승인 거부 경로 + audit 기록 확인.

**DoD**: work 한 줄로 입력→보고서→최종 보고 md / dangerous 무승인 실행 불가 /
audit 무결 / 기존 테스트 무손상.

**금지**: --yes를 기본값으로 켜기. 승인 게이트 우회 경로 신설.

---

### P14 — 비서/일정 관리 모듈 ★사용자 3대 업무 중 2개★

**목적**: 앱 없이 완성 가능한 비서 기능을 먼저 완성한다 (가장 빨리 가치가 나오는 단계).

**작업 항목**:
1. **일정 저장소** `agent_ops/schedule_store.py` (stdlib):
   - 데이터: `%USERPROFILE%\OpenCodeLIG_USERDATA\schedule\schedule.json`
     (원자적 쓰기 — 기존 atomic_write_json 재사용, 백업 1세대 유지)
   - 항목: {id, title, due(YYYY-MM-DD[ HH:MM]), category(회의/보고/시험/개인),
     status(open/done), source(manual/mail/meeting), created}
   - 자연어 날짜 최소 지원: "오늘/내일/금요일/N일 후/7월 15일" → 결정적 파서
     (LLM 아님 — 오차 금지 영역). 못 알아들으면 되묻는 메시지 반환.
2. **CLI**: `agentops.py schedule add|list|today|week|done|remove` + `work`에서
   capability `schedule_management`로 라우팅 (CAPABILITIES에 등록, keywords: 일정/약속/
   마감/리마인드/캘린더/스케줄/등록/미루/연기 등).
3. **아침 브리핑** `agentops.py briefing` + `launch/briefing.bat`:
   출력(md+콘솔): 오늘/이번 주 일정, 마감 임박(3일 내), 미완료 액션아이템(기존
   액션아이템.md들 스캔), (입력 주어지면) 메일 분류 요약. → `results/reports/briefing_<날짜>.md`
4. **리마인더**: `schtasks /Create`로 매일 아침 briefing.bat 등록/해제하는
   `launch/install-reminder.bat` (등록 전 사용자 확인 문구 출력).
5. **회의록 capability** `meeting_minutes`: 회의 메모/텍스트 입력 → 회의록.md
   (참석/논의/결정/액션아이템 표) + 액션아이템은 schedule에 등록 제안(승인 게이트 경유).
   generator는 기존 document 구조 재사용 + input_ingest 근거 반영.
6. **주간보고 초안** `weekly_report`: 지난 7일 audit log + 완료 일정 + 생성 산출물 목록으로
   "이번 주 한 일" 초안 md 생성 (비서 기능의 핵심 부가가치).
7. `tests/test_secretary.py`: 일정 CRUD/날짜 파서/브리핑 생성/회의록 산출물 품질
   (quality validator 통과) — 전부 mock/로컬로 검증 가능.

**DoD**:
- [ ] `schedule add "금요일 14시 진동시험 보고서 마감"` → today/week 조회 정합
- [ ] briefing.bat 1회 실행으로 브리핑 md 생성 (일정+액션아이템 반영, input-grounded 규칙 준수)
- [ ] 회의 메모 → 회의록+일정 등록 제안 E2E (mock)
- [ ] 날짜 파서가 모호한 입력에 추측 대신 되묻기
- [ ] 기존 테스트 무손상

**금지**: 날짜 해석을 LLM에 맡기기 (결정적 파서만). 일정 삭제/변경을 승인 게이트 없이
수행. Outlook 연동을 이 단계에서 시도 (P15의 COM 검증 후).

---

### P15 — Office 2016 어댑터 + 호환 규칙

**목적**: Excel부터 실제 실행. 집 Excel(최신)로 COM 스모크 → 회사 2016에서 최종 검증.

**작업 항목**:
1. **§6.2 호환 규칙을 코드로**: `artifact_quality.py`에 vba_macro 규칙 추가 —
   2016 부재 함수(XLOOKUP/XMATCH/FILTER/SORT/UNIQUE/SEQUENCE/LET/LAMBDA/TEXTJOIN/CONCAT/
   IFS/SWITCH/MAXIFS/MINIFS/TEXTSPLIT 등) 등장 시 FAIL. 매크로 헤더에 "대상: Office 2016" 명시.
2. `adapters/excel_com.py` `execute(action, ...)`:
   - 항상 `사본_<원본명>.xlsx`로 복사 후 작업 (원본 불가침).
   - 1차 action: open/read_range/write_range/save_as/run_macro_file(가능 시)/close.
     VBProject 접근은 Trust Center 의존 → 차단 시 "Alt+F11 수동 import 안내"로 자동 강등
     (실패 아님, 안내가 결과물).
   - finally에서 Quit + 프로세스 잔류 확인.
3. `adapters/outlook_com.py` (비서 연동): 일정 읽기(오늘/주간)→schedule_store 동기화,
   메일 제목/발신 읽기→기존 mail_report 파이프라인에 입력. **발송은 dangerous 분류**
   (승인 필수). 집에 Outlook 없으면 static reviewed로 두고 회사 검증.
4. Word/PowerPoint COM은 문서/PPT 변환 action만 (md→docx 텍스트 유입, slide_spec→pptx 골격).
5. `tests/test_office_adapters.py`: 앱 없으면 SKIP. 집 Excel로 사본 왕복(read/write/save) 검증.

**DoD**: 집 Excel COM 사본 왕복 성공(locally validated) / 2016 금지 함수 규칙이 벤치에
포함 / available=True는 **회사 2016 실측 후에만** (집 성공은 "app validation pending
(2016 확인 필요)" 유지) / 기존 테스트 무손상.

**금지**: 집 최신 Excel 성공을 2016 검증이라 표기. 원본 파일 직접 조작. 메일 자동 발송
기본 활성화.

---

### P16 — 엔지니어링 SW 어댑터 (기계연구원 코어)

**목적**: HWP 2019 / SolidWorks 2022 / MATLAB 2024a / AutoCAD 2019 / ANSYS 2024R1.
생성(generator)은 집에서, 실행(adapter)은 회사에서. 한 세션에 1~2개씩.

**작업 항목** (공통 패턴: 생성기 강화 → adapter execute → 앱 실측 → available):
1. **MATLAB** (가장 쉬움 — CLI): capability `matlab_automation` 등록, `.m` 생성기
   (시험 데이터 후처리 템플릿: 로드/필터/플롯/저장, 입력 근거 반영),
   `adapters/matlab_batch.py`: `matlab -batch "run('작업.m')"` + exit code/로그 수집.
2. **AutoCAD 2019**: `.scr` 생성기(도면 일괄 인쇄/레이어 정리 등 템플릿) +
   `adapters/autocad_batch.py`: `accoreconsole.exe /i 도면.dwg /s 스크립트.scr` (사본 정책).
3. **ANSYS 2024R1**: capability `simulation_automation` — Fluent journal 생성기
   (읽기→세팅 확인→계산→후처리 export 골격) + `adapters/fluent_batch.py`:
   `fluent 3ddp -g -i job.jou` (배치 실행 가능성이 높음). Mechanical ACT/SpaceClaim
   스크립트는 **생성기만** (실행은 GUI 의존 → app validation pending 명시).
4. **HWP 2019**: `adapters/hwp_com.py` — 문서.md → hwp 변환(텍스트 유입+제목 스타일).
5. **SolidWorks 2022 한글판**: `adapters/solidworks_com.py` — RunMacro(사본 문서),
   기존 VBA scaffold(ActiveDoc guard/GetType)와 정합. 자동 저장 금지.
6. 각 어댑터 테스트: 앱 없으면 SKIP. 실측 로그는 `results/adapter_validation/`.

**DoD** (어댑터별): 사본 기반 실측 ≥1회 → available=True + 검증 날짜 기록.
실측 전엔 static reviewed / app validation pending. 기존 테스트 무손상.

**금지**: 해석(ANSYS) 결과의 공학적 판단을 자동화라 주장 (도구는 실행/정리만, 판단은
사용자). 원본 dwg/sldprt/분석 파일 직접 수정.

---

### P17 — 오프라인 반입 패키지 (용량 무제한 확정)

**작업 항목**:
1. `release/dependencies.json` PENDING_PREFETCH 전량 해소 (집에서 다운로드+SHA256):
   pywin32(Excel/HWP/SW/Outlook COM), openpyxl(xlsx ingest), python-pptx,
   **Qwen2.5 7B/14B GGUF + llama.cpp server exe** (사내 PC 16GB VRAM 백업 서빙용 — gateway
   장애 대비), whisper.cpp exe + ggml-medium(ko) (P20 대비 선반입), ffmpeg.
2. **xlsx ingest 확장** (openpyxl 확보 시점이 여기): `input_ingest.py`에 .xlsx 지원 —
   시트/행열/헤더/이상 행 추출을 CSV와 동일 규칙으로. openpyxl 없으면 기존대로
   unsupported (동작 저하 없음 — optional import 패턴).
3. `release/build_bundle.py` + `release/setup.bat` (pip --no-index --find-links) + 설치 후
   doctor 자동 실행. `docs/BRING_IN_CHECKLIST.md`.
4. **리허설**: 집 PC 네트워크 어댑터 비활성 → setup.bat 전체 → doctor 전 섹션 정상.

**DoD**: PENDING_PREFETCH 0건 / 오프라인 리허설 성공 / xlsx ingest 벤치 추가(있으면 파싱,
없으면 unsupported 정직 표기 양쪽 테스트) / 모델 파일 git 미커밋(.gitignore 확인).

---

### P18 — 운영/보안 마무리

secret 스캔 pre-commit(`workspace-template/scripts/precommit_scan.py`, stdlib),
`docs/RUNBOOK.md`(증상→진단 파일→대응), audit log 크기 순환, lig-api.env 백업 안내
(USERDATA는 repo 밖임을 명시). **DoD**: 훅 동작 / runbook 존재 / doctor에 운영 섹션.

---

### P19 — 회사 파일럿 (최종 수렴)

**1일차 순서**: 반입 zip → setup.bat → doctor → lig-api.env 작성(커밋 금지) →
gateway 스모크(lig-coding/chat/fallback 각 1회) → tool-call 형식 실측(필요 시 파서 보강).

**파일럿 업무 12종** (비서/일정/매크로 = 사용자 3대 업무 반영):

| # | 업무 | 경로 | 구분 |
|---|------|------|------|
| 1 | 아침 브리핑 (일정+액션아이템) | briefing.bat | 비서 |
| 2 | 일정 등록/조회/완료 (자연어) | work→schedule | 일정 |
| 3 | 시험 xlsx → 이상값 보고서+PPT | work --input | 비서 |
| 4 | 메일 분류+오늘 액션아이템 | work --input (+Outlook COM) | 비서 |
| 5 | 회의 메모 → 회의록+일정 등록 | work --input | 비서 |
| 6 | 주간보고 초안 자동 생성 | weekly_report | 비서 |
| 7 | Excel 2016 데이터 정리 (COM 실행) | work --execute | 매크로 |
| 8 | 보고서 → HWP 2019 변환 | hwp adapter | 매크로 |
| 9 | SolidWorks 2022 매크로 실행 (사본) | sw adapter | 매크로 |
| 10 | MATLAB 배치 후처리 실행 | matlab adapter | 매크로 |
| 11 | AutoCAD .scr 일괄 처리 / Fluent journal 실행 중 1 | 배치 adapter | 매크로 |
| 12 | 사내 웹페이지 텍스트 추출→요약 | browser CDP | 비서 |

각 항목: 성공/실패/소요시간/개입 횟수 기록 → `docs/PILOT_BACKLOG.md`. **성공률 조작 금지.**
company validation pending 항목들의 실제 해소 여부를 상태 어휘로 일괄 갱신.

---

### P20 — 음성 입력 (예약 — 파일럿 후, 인터페이스는 P13에서 확보)

P13의 work가 `--task-file` 을 이미 받게 설계하면 음성은 "녹음→whisper.cpp STT→task-file"
파이프만 추가하면 된다. 반입물(P17)에 whisper exe/모델 선포함. 구현 시 v1 계획의 13단계
내용(확인 게이트 필수, 인식 텍스트 무확인 실행 금지)을 그대로 따른다.

---

## 5. 신규 capability 등록 목록 (P14~P16에서 추가 — 이 외 임의 추가 금지)

| capability id | 산출물 kind | 단계 |
|---------------|------------|------|
| `schedule_management` | schedule 조작(+확인 md) | P14 |
| `meeting_minutes` | meeting_minutes(문서 변형) | P14 |
| `weekly_report` | document 재사용 | P14 |
| `matlab_automation` | matlab_script(.m) | P16 |
| `simulation_automation` | fluent_journal(.jou)/ACT script | P16 |
| (기존 office_cad_automation) | AutoCAD .scr 추가 | P16 |

각 추가 시: keywords/pending/status 정직 기입 + ARTIFACT_KIND_INFO + generator +
quality 규칙 + 벤치 시나리오를 **한 세트로** 커밋 (부분 커밋 금지).

---

## 6. 호환성 규칙 (하위 모델 필수 준수)

### 6.1 Windows/한글 환경
- 모든 신규 BAT: UTF-8 no BOM + CRLF, 첫 줄부에 `chcp 65001` + `set PYTHONUTF8=1`
  (한글 경로 참조는 chcp 이후 라인). 기존 launch/*.bat 패턴 복제.
- 파일 경로는 pathlib, 인코딩은 encoding_ops 정책(BOM/CRLF 보존) 재사용.

### 6.2 Office 2016 호환 (사용자 확정: 전 Office 2016 기준)
- 생성 VBA/수식에서 **금지**(2016 부재): XLOOKUP, XMATCH, FILTER, SORT, SORTBY, UNIQUE,
  SEQUENCE, RANDARRAY, LET, LAMBDA, TEXTSPLIT, TEXTBEFORE/AFTER, VSTACK/HSTACK,
  TEXTJOIN, CONCAT, IFS, SWITCH, MAXIFS, MINIFS. 대체: VLOOKUP/INDEX+MATCH/&연결/
  중첩 IF/배열수식.
- COM 코드는 Office 2016 개체 모델 범위만. 집(최신 Excel) 성공은 "문법/COM 스모크"일 뿐,
  2016 실측 전까지 app validation pending 유지.

### 6.3 앱 자동화 공통 안전 수칙
- 원본 불가침: 항상 사본에서 실행. 자동 저장 금지(사용자 확인 후).
- 실패 시 앱 프로세스/임시 파일 잔류 없게 finally 정리.
- available=True는 "해당 버전 실제 앱 실측 성공 + 로그 증빙" 후에만.

---

## 7. 하위 모델 세션 실행 프로토콜

### 7.1 불변 규칙 (위반 = 세션 실패)
1. 기존 테스트가 깨지면: 원인 파악 → 못 고치면 revert → 사실대로 보고. 테스트 약화 금지.
2. 상태 어휘(§0)만 사용. mock→real, scaffold→완성, 집 검증→회사 검증으로 부풀리기 금지.
   전체 제품 성공 선언 금지.
3. secret/내부 hostname: 코드·커밋·보고 어디에도 금지. lig-api.env 실값 커밋 금지.
4. repo 루트 사용자 untracked 5개(.gitignore, docs/home-lab-status.md, logs/, tools/,
   validation/) 불가침. 커밋은 개별 git add (git add -A 금지).
5. 파괴적 git 작업은 이 문서에 승인이 기록된 것(P10)만, 그 절차 그대로.
6. 새 외부 의존성: dependencies.json 선기록. 코어는 stdlib-only.
7. 테스트: pytest 금지, check(label, cond) 스타일. 외부 자원 필요 테스트는 SKIP=exit 0 명시.
8. 같은 접근 2회 실패 → 접근 변경. 3회 실패 → pending 보고 후 다음 항목 (세션 소진 금지).
9. capability/어댑터 임의 추가 금지 — §5 목록만.

### 7.2 세션 프롬프트 템플릿 (복붙용)
```text
이전 결과를 이어서 OpenCodeLIG 작업을 계속해라. 이번 세션은 MASTER_PLAN.md의 P<N>단계다.
1) workspace-template/docs/MASTER_PLAN.md 의 P<N> 섹션과 §6, §7을 읽어라.
2) 공통 시작 의식을 수행해라.
3) [작업 항목]을 순서대로 구현하고, [검증 명령]을 실행해라.
4) [DoD]를 체크하고, 못 채운 항목은 pending으로 남겨라 (조작 금지).
5) 9개 기존 테스트 + 신규 테스트 전부 통과 시에만 commit/push 해라.
6) §7.3 형식으로 보고해라.
```

### 7.3 보고 형식
```text
Outcome: / Files changed: / (단계 핵심 섹션): / Local validation: /
App/company validation pending: / Dependency impact: / Maintainability notes: /
Security cleanup status: / New HEAD commit: / Next exact command:
```

---

## 8. 리스크 레지스터

| 리스크 | 가능성 | 대비 (반영 위치) |
|--------|--------|-----------------|
| gateway 스펙 변경 | 중 | env 완전 오버라이드(P9) — 코드 수정 없이 흡수 |
| **gateway 라우트 404** | **해소 — 3라우트 200** | `/gateway/` 접두 반영 후 전부 200 (company_check 2026-07-03) |
| **EXAONE tool-call 신뢰성** | ~~최대 미지수~~ **해소(실측)** | gateway가 **OpenAI native function calling 완전 지원** (tool_calls_present=True) → 텍스트 파싱 의존 제거, P11-A native 경로 1차. 파서 리스크 소멸 |
| VBProject COM 차단 | ~~높음~~ **해소(실측)** | Excel VBProject 접근 실동작 성공 (company_check) → P15-02 자동 주입 확정 |
| 앱 COM 실동작 (Office/HWP/SW) | ~~app validation pending~~ **연결 확인(실측)** | Outlook/HWP/SolidWorks COM 접속 + MATLAB -batch 실행(22s) + Chrome CDP 전부 성공. 실기 작업 로직만 남음 |
| AutoCAD accoreconsole | **해소(실측)** | `C:\AutoCAD 2019\accoreconsole.exe` 확인 (Mechanical 2019) |
| OpenCode 느린 창 | 추적 중 | exe는 빠름(cold 1.3s) — 원인은 TUI 초기화. 현재 구 런처 사용 중(PURE/플러그인차단 env 미적용) → 강화 런처 재설치 후 재측정 |
| EXAONE tool-call 형식 특이 | 중 | P19 1일차 실측+파서 보강 절차, Qwen3.6 fallback 자동 |
| gateway 장애/점검 | 중 | 사내 PC 16GB VRAM 로컬 GGUF 백업 서빙(P17 반입) |
| VBProject COM 차단 | 높음 | P15 이중 경로(COM 데이터 작업 + 수동 import 안내 강등) |
| 2016 비호환 수식 생성 | 중 | §6.2 금지 목록을 quality 규칙으로 강제(P15) |
| ANSYS/CAD 배치 제약 | 중 | 생성기 우선, 실행은 pending 정직 표기 (P16) |
| 집(Win10/최신Excel)↔회사(Win11/2016) 차이 | 중 | "집 성공=스모크" 원칙, 회사 실측 전 pending 유지 |
| 날짜/일정 오해석 | 중 | 결정적 파서 + 모호 시 되묻기 (P14, LLM 배제) |
| weak tool-call 불안정 | 중 | P11 floor + 파서 복구 + fallback 라우트 |

---

## 9. 현재 운영 모드 (2026-07-03 갱신 — 이 절만 갱신하며 §1~§8은 전략 원본 유지)

> 실행은 **repo 루트 `plan/` 보드가 주도**한다 (이 문서는 전략/근거 원본).
> - 구현: Codex 워커 — 원라인 프롬프트로 auto-advance (plan/README.md)
> - 리뷰/설계/hard gate: Fable — 배치 리뷰, task·계획 갱신, P10-01 purge 전담
> - 회사 실측: 사용자 — `plan/NEXT_ONSITE.md` 목록을 방문 때마다 수행/반출
>
> 진행 요약 (2026-07-03): P9 전체·P12~P15 선두·P17-01·P18-01 등 **11개 task APPROVED**,
> gateway 3라우트 200 (연결 company validated — probe/results/), Excel 자동 주입 가능
> 확정, `work` 한 명령 E2E 완성. 최대 남은 미지수는 EXAONE tool-call 실동작(P00-03)과
> Office 2016 실기 실행(P15 계열 회사 검증).
