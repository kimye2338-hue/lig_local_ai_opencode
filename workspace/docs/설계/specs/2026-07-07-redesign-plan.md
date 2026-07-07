# 재설계 계획서 — 구조 단순화·직관화·유기적 연결·최적화·문서 단일화

작성 2026-07-07 (Fable 5). 상태: **계획(승인 대기)**. 구현·패키지는 승인 후 마지막에 일괄.

목표(사용자 요구 원문 반영):
1. 구조 단순화 + 직관화(폴더 이름만 보고 전 기능 파악·관리·확장)
2. 기능들 더 유기적·자연스럽게 연결
3. 시스템 최적화
4. 사용자 가이드·설명 문서를 한 곳에 통합
5. 미구현 부분 고도화(완성도)
6. 현 구조 팩트체크
7. 정보를 효율적·효과적으로 관리하는 법
8. GitHub 인기 에이전트루프 프로젝트 패턴 반영 (§7에서 통합)

---

## 1. 현 구조 팩트체크 (주장 vs 실제)

측정 결과(2026-07-07, 코드 직접 확인):

| 항목 | 문서 주장 | 실제 | 판정 |
|---|---|---|---|
| Tab 모드 | 3개(build/plan/agent) | primary=agent 1개 강제, clean_stale 자동청소 | ✅ 일치 |
| 승인정책 | ASK/AUTO/FULL | 패치 빌드에 구현 | ✅ 일치 |
| 작업 플래너 | 능력 자동선택 | **기본 deterministic_keyword**, semantic(LLM) 플래너는 코드에 있으나 "company validation pending"(미검증·기본 off) | ⚠️ 부분 |
| 앱 어댑터 | Office/CAD/메일/HWP 자동화 | office/outlook/hwp/browser/matlab/autocad = validated, **solidworks(연결만)/fluent/ocr_screen/desktop_ui = available:False(미검증)** | ⚠️ 부분 |
| 능동(proactive) | PRODUCT_VISION 문서가 강조 | schedule/watch/briefing/timeline은 실재, "proactive" 단일 기능은 코드에 없음 | ⚠️ 문서 과장 |
| 실 게이트웨이 왕복 | 무설정 연결 | self-heal로 설정은 자동, **실 LLM 왕복은 사내망에서만 검증 가능(현재 mock/bench 222 checks)** | ⚠️ 환경의존 |
| 기억→위키→책→recall 복리 | 자동 | 실재·검증됨(hot-path 훅) | ✅ 일치 |

**결론**: 핵심 루프·기억·안전은 실재하고 견고. "미구현"은 (a) semantic 플래너 기본화, (b) 미검증 어댑터 4종, (c) 능동성 심화. 문서는 일부 과장(특히 vision류)이라 실제에 맞춰 정리 필요.

## 2. 구조 단순화·직관화

**문제**: `agent_ops/`가 **53개 .py 평면 배치** — 폴더로 안 나뉘어 무엇이 어디 있는지 파일명으로만 유추. 관심사 7군으로 명확히 나뉘는데 폴더가 없음.

**제안**: 관심사별 서브패키지로 재편(폴더 이름 = 기능 지도). 임포트 churn 위험은 **재-export 셈(shim)**으로 단계적 이행해 한 번에 안 깨지게.

```
agent_ops/
  loop/        진입·에이전트 루프·도구 디스패치·툴콜 파싱·상태   (agentops→cli, tool_dispatch, toolcall_parser, core, state_manager, local_tools)
  gateway/     LLM 게이트웨이·라우팅·폴백·진단·능력·플래너        (lig_providers, lig_runtime, capabilities, probe_*, doctor)
  memory/      기억·위키·지식책·자율유지·비서·일정               (memory_manager, wiki_manager, wiki_vault, knowledge_book, auto_maintain, secretary, schedule_store)
  artifacts/   산출물 생성·품질·입력적재·리포트·Office/문서       (artifact_generators, artifact_quality, input_ingest, html_report, office_writer, doc_*, activity_timeline)
  knowledge/   지식 자동주입(공식API·디자인·도메인·스킬·프로필)   (api_reference, design_guidance, domain_context, skill_router, project_profile) + 기존 knowledge/ 데이터
  safety/      명령가드·승인·감사·실패·시크릿·정리               (command_guard, approval, audit, failures, clean_stale)
  adapters/    앱 제어(그대로)
  runtime/     인코딩·안전쓰기·목업·렌더·llm_client              (encoding_ops, safe_file_writer, mock_transport, render_ko, llm_client)
```
- 미분류 14개(dashboard/menu/ocd/orchestrator/queue_manager/reporter/routines/safety/verifier 등)는 위 군에 흡수하거나 `cli/` 하위로.
- 이행 방식: 파일 이동 + `agent_ops/<old>.py`에 `from .memory.manager import *` 재-export shim 1줄 → 기존 임포트/테스트/.opencode 무중단. 안정화 후 shim 제거.

## 3. 유기적 연결(이미 상당수 완료 + 남은 것)

이미 연결됨(이번 세션): 8층 지식주입, 기억→위키→책→recall 복리, 어댑터 대화형 노출, 자율유지 하루 2회, Obsidian 자동 시드.
**남은 유기화**:
- **단일 Capability Registry**: 능력(capability)·도구·어댑터·지식주입·산출물 kind를 하나의 표로 정의해 doctor/plan/agent.md 레시피가 그 표를 참조(현재 여러 곳에 흩어짐).
- **피드백 루프 명시화**: 작업 결과→감사→기억→위키→다음 recall 을 한 모듈(예: `loop/feedback.py`)로 모아 추적성 확보.

## 4. 최적화 (이미 일부 + 추가)

완료: recall 점수식, 뷰 재렌더 제거, log.md 상한, 중복정리. 추가 후보:
- 지식주입 8층을 매 작업 전부 로드 → 작업 유형에 맞는 층만 지연 로드(토큰·지연 절감; weak model 정확도↑).
- 위키 consolidate O(n²) 모순탐지를 증분(변경분만).
- 도구 스키마 10.4KB → 작업 유형별 도구 서브셋 노출(29개 전부 대신).

## 5. 문서 단일화 (한 곳, 폴더명으로 파악)

**문제**: docs/ 21개 + 흩어진 README/rules 7개, master-plan/vision 3중복.

**제안**: `docs/` 를 역할별 소수 폴더로. 이름만 보고 파악:
```
docs/
  README.md          ← 유일 진입점(무엇을·어디서·어떻게 5분 파악)
  1-사용법/          설치·사용·문제해결(GUIDE+INSTALL+RUNBOOK 통합)
  2-기능/            기능별 1장씩(office/doc/ocr/obsidian/overlay/memory)
  3-설계/            아키텍처·하네스원칙·이 계획서·결정기록(ADR)
  4-운영/            반입툴·외부도구판정·체인지로그
  archive/           옛 master-plan/vision/handoff(통합 후 보관, 삭제 아님)
```
- 중복 3종(MASTER_PLAN/PRODUCT_MASTER_PLAN_FABLE5/PRODUCT_VISION)은 3-설계/아키텍처.md 한 편으로 통합, 원본은 archive/.
- 흩어진 rules(AGENTOPS_RULES/COMMAND_GUARD_RULES)는 3-설계/ 로, 코드 옆 README는 남기되 docs 색인에서 링크.
- 루트 CLAUDE.md는 세션 진입점으로 유지하되 docs/README.md를 가리키게.

## 6. 미구현 고도화

- **semantic 플래너 기본화 경로**: self-heal 게이트웨이가 붙었으니, 실 LLM 플래너를 켜되 실패 시 keyword로 자동 폴백(이미 폴백 코드 있음) — 기본 semantic 시도로 승격 검토.
- **미검증 어댑터 4종**: solidworks(run_macro 검증), ocr_screen(엔진 반입 후), desktop_ui(windows-use 대체 경량화), fluent — 각각 "검증 체크리스트 + 우아한 미가용" 정비. windows-use 138MB 회피 대안 조사.
- **능동성**: schedule/watch/briefing을 하나의 "능동 루프"로 묶어 문서-실제 간극 해소.

## 7. 정보 관리 + GitHub 리서치 반영 (인기 프로젝트 근거)

리서치 요약(고스타·유지보수 활발 프로젝트에서 추출). 우리 시스템은 **오프라인·약한모델·단일 primary 루프**라 취사선택.

### 7-A. 에이전트 루프
- **ReAct**(관찰-사고-행동 인터리브)가 표준. mini-swe-agent(SWE-bench 74%+, 100줄): **선형 append-only 히스토리 + 액션 독립성**. OpenHands: **이벤트 스트림**(User→Agent→LLM→Action→Runtime→Observation)로 실행 전 위험검사·결정적 재생(replay)·체크포인트.
- AutoGPT/BabyAGI 실패(성공률 24%): 블랙박스 재계획 + 약한 메모리로 순환. 성공작(Claude Code/Aider)은 "적은 도구 + 나은 컨텍스트 관리"로 수렴.
- **채택**: 우리 tool-loop는 이미 선형 messages. → 승인가드를 **이벤트 스트림화**해 재현가능 디버깅(runtime-last 확장). 도구 수는 유형별 서브셋으로(§4).

### 7-B. 약한 모델 도구 (가장 강한 실측)
- 소형 모델 malformed 도구호출 **31.6%**(대형 1.7%, ~19배). **단 1회 실패로 정확도 73.2%→43.4%**. 도구 성공률 70% 미만이면 부적합.
- **reflect-then-repair**: 스키마 검증 후 오류를 **개별 호출 단위 국소 수정**(전역 재계획 금지), 고정 예산. 재시도는 **명시 에러 피드백 + 상한**.
- **채택(우리 이미 보유 → 강화)**: `toolcall_parser` 복구 + `FALLBACK_POLICY` 캡은 이미 있음(이번 세션 strict-mode 추가가 정확히 이 방향). 추가: **앱 도달 전 로컬 검증**(Office/CAD 어댑터 실행 전 인자·파일 존재 확인 → 잘못된 호출이 실제 앱에 도달 차단), 스키마 최소 유지.

### 7-C. 장기 기억
- MemGPT/Letta: **core(고정 스크래치패드, 항상 주입)/recall/archival 3계층**. Generative Agents: append-only stream + **주기적 reflection(고차 통찰 합성)** + 검색 **recency×importance×relevance 3축**. A-MEM: Zettelkasten 자기조직 링크 = **우리 [[backlinks]] 위키와 거의 동일**.
- **채택**: 우리는 이미 A-MEM+MemGPT 근접. 추가 2가지 —
  (a) **importance 점수**: 저장 시 LLM 1줄 평가(0~1)로 중요도 부여 → recall/위키 검색 랭킹을 recency×importance×relevance로(현재 키워드 매칭만).
  (b) **core-memory 스크래치패드**: 위키 검색과 별도로 소규모 고정 컨텍스트(사용자 규칙·현재 목표) 항상 주입 — **약한 모델의 검색 실패 안전망**. pinned_recall을 이 개념으로 정식화.

### 7-D. 루프 안전/폭주 방지
- 탐지: **최근 k액션 해시 매칭**(오프라인 계산만) + 토큰 소비 **속도** 모니터. 다층 정지: max_iterations + 예산 + N스텝 무진행.
- **채택**: 현재 `repeated_failure`(동일 인자 반복)만 있음. 추가: **해시 기반 반복 탐지**(동일 액션 시퀀스) + **완료 선언 전 목표충족 재검증** 스텝을 승인가드 옆에.

### 7-E. 리포지토리 구조
- Claude Code: **CLAUDE.md 단일 진입 + 서브에이전트 프롬프트 분리**(우리와 이미 일치). Aider **repo map**: 심볼 그래프+PageRank로 **관련 코드만 예산 내 선택 주입**.
- **채택**: knowledge/apis·design·domain·skills 주입을 **항상 전체가 아니라 relevance 랭킹으로 예산 내 선택**(§4 최적화와 동일 결론 — 리서치가 뒷받침).

### 정보 관리 원칙(리서치 반영 확정)
- **단일 진실원(SoT)**: 능력/도구/상태는 코드 registry가 SoT, 문서는 링크/생성만.
- **3계층 기억 + core 스크래치패드**: core(항상) → 원장(사실) → 위키(증류) → 책(열람), reflection/compaction 정책 명문화.
- **relevance 예산 주입**: 8층을 전부가 아니라 작업 relevance 순 예산 내.
- **결정기록(ADR)**: docs/3-설계/decisions/ 에 축적.
- **이벤트 스트림 + 해시 반복탐지 + done-검증**: 재현가능·폭주방지.

## 7-F. 사내 모델 맞춤 최적화 (EXAONE-4.5-33B / Qwen3.6-27B)

스펙이 확정돼 있으므로 두 모델 성능에 맞춰 튜닝(리서치 결과 반영 예정):
- **온도**: 도구호출/코딩 경로 저온(0.0~0.2) 고정. 라우트: EXAONE=한국어 문서/메일/보고, Qwen=코드/매크로.
- **도구 스키마 최소 + 작업별 서브셋**: 27~33B는 도구 많으면 정확도↓ — 유형별 노출.
- **few-shot 매크로 예시**: 지식주입에 실제 동작 예제 1개를 함께 넣어 첫 시도 성공률↑.
- **reflect-repair + 캡**: 이미 보유(strict-mode/FALLBACK_POLICY). 실행 전 로컬 검증으로 앱 도달 차단.

## 7-G. CAD/엔지니어링 지식 대폭 보강 ("말만 하면 바로 구현")

내 버전(**SolidWorks 2022 / AutoCAD 2019 / ANSYS Fluent 2024R1 / MATLAB R2024a**)의 공식
API·작업 레시피를 `knowledge/apis/*.md`에 총망라(공식 사이트 근거, 버전 정확). 주입은
task별 relevance 발췌(api_reference `_excerpt` 개선 완료)로 큰 파일에서도 작업에 맞는
레시피만 주입. 목표: "이거 만들어줘"만으로 올바른 매크로/스크립트 즉시 생성.

## 8. 실행 순서(승인 후, 일괄)

1) 문서 통합(무손실: archive 보존) → 2) capability registry 단일화 → 3) 서브패키지 재편(shim) → 4) 최적화(지연주입·증분lint) → 5) 미구현 고도화 → 6) 전 회귀 green → 7) 패키지 1회 재빌드·전달.
