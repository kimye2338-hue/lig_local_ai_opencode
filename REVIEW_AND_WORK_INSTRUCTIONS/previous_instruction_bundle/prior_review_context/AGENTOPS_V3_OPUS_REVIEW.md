# OpenCode AgentOps Continuous v2 — 최종 검토 및 v3 패치 지시서

> 검토: Claude Opus · 입력: `CLAUDE_REVIEW_AGENTOPS_v2_LIGHT.zip` 전체 코드 직접 리딩 + Sonnet 4.6 심층조사 보고서
> 검증 방식: ZIP 내부 `FILES` dict(37개 생성파일) 전량 추출·정독, `agentops.py` 664라인 라인단위 분석, `py_compile`로 컴파일 확인, dead-file/dead-schema는 grep으로 직접 검증. Sonnet이 "확인 불가"로 남긴 4개 항목은 OpenCode 공식 문서·이슈트래커로 직접 재확인했고, 그 결과 일부 권고가 바뀌었다(아래 명시).

---

## Sonnet이 못 풀고 남긴 4개 불확실성 — 직접 검증 결과 (이게 결론을 바꾼다)

Sonnet 보고서 부록의 4개 미확인 항목을 공식 소스로 확인했다. **두 개는 Sonnet 권고를 강화하고, 하나는 새로운 P0 결함을 드러내고, 하나는 진단을 정정한다.**

| # | Sonnet의 질문 | 확인된 사실 | 영향 |
|---|---|---|---|
| 2 | OpenCode bash tool에 타임아웃이 있나 | **있다. 하드코딩 기본 120초** (`OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS`로만 변경 가능, AI SDK `streamText` `stepMs:120000`가 상한). | `run-until-stop`은 "UI 영구 블로킹"이 아니라 **120초에 SIGTERM으로 조용히 죽는다**. 진단 정정 — 더 나쁜 종류의 실패(조용한 실패). |
| 3 | `instructions`/AGENTS.md가 compaction 후에도 유지되나 | **아니다.** 이슈 #16960 "losing instructions after compaction" 공식 확인. 게다가 AGENTS.md는 **매 loop() 이터레이션마다 system prompt에 통째로 재주입**되며 size guard가 없음(#18037). | append-only 메모리를 `instructions`에 넣은 v2 설계는 **compaction 무한루프 유발 P0 결함**. Sonnet의 "instructions에 넣지 마라"가 맞고, 이유는 더 치명적. |
| 4 | subagent Task 호출이 진짜 병렬인가 | **아니다.** 이슈 #14195: 한 응답에 Task를 3개 호출해도 `tasks.pop()`으로 **하나씩 순차 실행**. 일반 tool만 `Promise.all` 병렬. | Sonnet의 "진짜 병렬 노리지 말고 순차 파이프라인" 권고가 **공식적으로 증명됨**. 코어 OpenCode만으로 병렬 specialist는 불가능. |
| — | (신규 발견) compaction summary의 안전성 | 이슈 #14923: compaction summary의 "next steps"를 모델이 **사용자 승인으로 오인**해 승인 없이 git push까지 실행한 사례. | "continue-until-stop" + "위험버튼 차단"을 같이 추구하는 v2 설계에 **직접적인 안전 위협**. 새 failure type과 가드 필요(§9). |

**한 줄 요약**: Sonnet 보고서는 OpenCode 사실관계가 정확하고 결함 지적도 옳다. 단, (a) `run-until-stop`의 실패 양상은 "블로킹"이 아니라 "120초 침묵사", (b) append-only 메모리의 `instructions` 등록은 P2가 아니라 **P0 compaction 루프 폭탄**, (c) compaction-summary-as-approval이라는 안전 구멍이 추가로 존재한다.

---

# 1. 총평

**v2를 그대로 쓰면 안 된다. 단, skeleton으로는 의미가 있다 — 절반만.**

`agentops.py` 664라인을 전부 읽은 결론은 Sonnet과 동일하다: **이 스크립트는 "마크다운/JSON 리포트 생성기"이지 AgentOps 런타임이 아니다.** 구체적으로:

- `classify_failure()`는 단순 문자열 `in` 매칭 8개. 12개 선언된 failure type 중 **4개(NO_DATA, REPEATED_FAILURE, SESSION_EXPIRED, RISKY_ACTION_BLOCKED)는 분류기에 코드가 아예 없다** (grep 확인).
- `selfheal()`은 "무엇을 해야 하는지 적힌 텍스트(SELFHEAL_PLAN.md)"만 쓰고 **실제로 아무것도 고치지 않는다**.
- `run_until_stop()`은 `while True: heartbeat(); continue_once(); sleep(30)` — 30초마다 타임스탬프만 갱신하는 **빈 루프**. 실제 LLM 호출도 task 실행도 없다.
- `continue_once()`는 `ACTIVE_TASK.json`의 `next_action` **문자열 필드만 갱신**. 실제 "다음 작업 수행"이 없다.
- `TASK_QUEUE.jsonl`은 `init`에서 **빈 파일로 생성만 되고 어디서도 읽히지 않는다** (grep 확인). queue executor가 없으므로 queue가 무의미.
- `DANGEROUS_ACTIONS.txt` / `ALLOWED_ACTIONS.txt`는 생성되지만 **`agentops.py` 어디서도 open/read 안 함** (grep 확인). 위험버튼 차단은 현재 **순수 자연어 프롬프트뿐**, 코드 enforcement 0.

**그래서 "skeleton으로 의미 있나?"의 정직한 답**: 상태파일 레이아웃(`agent_ops/state/*`, `.agent-memory/*`)과 역할분리(9 subagent)와 stop-file 개념은 **재사용 가치가 있다**. 하지만 v2가 약속하는 4대 기능 — (1)실패복구 (2)지속실행 (3)compact 후 이어가기 (4)재시작 resume — 은 **현재 코드로는 하나도 실제 동작하지 않는다**. 전부 "그렇게 하라고 적힌 마크다운"만 있다.

**v3에서 반드시 바꿔야 할 핵심 3가지** (나머지는 부차적):

1. **OpenCode 세션 안에서 장기 실행을 시도하는 것 자체를 포기하라.** bash tool 120초 상한 때문에 "OpenCode를 켜둔 채 계속 진행"은 원천 불가능. 지속실행은 **OpenCode 외부 독립 프로세스(Python orchestrator + Windows 작업 스케줄러)**로만 가능하다. 이게 가장 큰 아키텍처 결정이다.
2. **안전·권한을 프롬프트가 아니라 코드/permission으로 강제하라.** 약한 로컬 모델이 전제인데, 가장 약한 방어(모델 자기판단)를 가장 위험한 영역(포털 위험클릭)에 두고 있다. dead policy 파일을 실제로 읽는 코드 게이트 + agent `permission.edit: deny`로 수정권한 단일화.
3. **append-only를 끝내라.** `add_lesson()`이 무한 append하는 `LESSONS_LEARNED.md`를 `instructions`에 넣은 조합은 compaction 무한루프를 부른다(#18037 확인). 메모리는 JSONL source-of-truth + 크기상한 + 2단계 deprecate로 재설계.

OpenCode 공식 문법 측면에서 **존재하지 않는 `patch` tool 이름을 9개 agent 전부와 룰 문서에 일관되게 사용**하는 것은 단순 오타가 아니라 설계자의 정신모델 오류 신호다. 공식명은 `apply_patch`이고, 애초에 `tools:` 필드 자체가 deprecated이며 `write`/`edit`/`apply_patch`는 **`edit` permission 하나로 통합 통제**되므로 `permission:`으로 전환하면 이 문제는 자동 소멸한다.

---

# 2. 치명적 문제 / 반드시 고칠 것

## 2.1 [P0] `run-until-stop`을 OpenCode bash tool 안에서 실행 → 120초 침묵사

- **문제**: `/agentrun` command 본문이 모델에게 `python agent_ops/agentops.py run-until-stop --cycle-seconds 30`을 bash tool로 실행하라고 지시. 이 함수는 `while True ... sleep(30)` 무한루프.
- **왜 깨지나**: OpenCode bash tool은 **하드코딩 120초 타임아웃**(검증됨, #25509/#4197). 무한루프는 120초 시점에 `The operation timed out`으로 **SIGTERM 종료**된다. Sonnet은 "UI 블로킹"으로 봤지만 실제로는 더 나쁘다 — 모델은 타임아웃 에러를 받고 "실패했네" 하고 **재시도 루프**에 빠지거나(#11313 패턴), heartbeat 4번 찍힌 뒤 죽은 걸 모른 채 "계속 진행 중"이라 착각한다.
- **영향**: "사용자가 멈출 때까지 계속"이라는 v2의 간판 기능이 **2분마다 죽는다**. command 본문의 "If it blocks the UI, run the BAT" 안내는 모델이 이미 잘못 실행한 뒤에야 보는 사후약방문.
- **수정 방향**: bash tool 안에서 무한루프 실행을 **룰로 금지**. 지속실행은 (a) 별도 CMD에서 `RUN_AGENTOPS_CONTINUOUS.bat`, 또는 (b) Windows 작업 스케줄러로 `continue-once`를 N분마다 호출 — **둘 다 OpenCode 프로세스 밖**. `/agentrun` command를 "실행"이 아니라 "외부 실행 방법 안내"로 재작성(§14에 전문 제공). `run_until_stop()`은 외부 전용으로 명시하고, `--once` 게이트를 둬서 OpenCode가 실수로 무한모드를 못 켜게 한다.

## 2.2 [P0] append-only 메모리를 `instructions`에 등록 → compaction 무한루프 폭탄

- **문제**: `merge_opencode()`가 `.agent-memory/LESSONS_LEARNED.md`, `ERROR_PATTERNS.md`, `ACTIVE_MEMORY.md`를 `instructions`에 영구 등록. 동시에 `add_lesson()`은 이 파일들에 **무한정 append**.
- **왜 깨지나**: 공식 확인(#18037) — AGENTS.md와 instructions 파일은 **매 loop() 이터레이션마다 system prompt에 통째로 주입되며 size guard가 없다**. 331KB instruction 파일이 128K 컨텍스트의 81%를 먹어 첫 턴부터 compaction이 터지고 **무한 compaction 루프**에 빠진 실제 사례가 보고됨. v2는 lesson이 쌓일수록 이 방향으로 간다.
- **영향**: 시스템을 오래 쓸수록(=lesson이 쌓일수록) compaction 빈도가 올라가고, 결국 모델이 작업은 안 하고 compaction만 반복하게 된다. "메모리로 똑똑해진다"는 의도와 정반대로 **메모리가 시스템을 마비시킨다**.
- **수정 방향**: (1) `instructions`에는 **고정 크기 파일만** — `AGENTS.md`, `agent_ops/AGENTOPS_RULES.md`만 남기고 휘발성·증식성 메모리는 제거. (2) `add_lesson()`에 **크기 상한**(최근 N개만 유지, 오래된 건 `.agent-memory/archive/`로 이동). (3) 메모리는 모델이 **필요할 때 read tool로 읽게** 하지, system prompt에 상주시키지 않는다.

## 2.3 [P0] dead safety 파일 — "있어 보이지만 작동 안 하는" 가짜 안전장치

- **문제**: `DANGEROUS_ACTIONS.txt`(삭제/저장/제출/승인/결재... 33개 키워드)와 `ALLOWED_ACTIONS.txt`가 생성되지만, `agentops.py` 전체에서 이 파일을 **읽는 코드가 0** (grep 확인).
- **왜 깨지나**: 위험버튼 차단이 전적으로 모델의 자연어 판단(`agentops-safety` 프롬프트)에만 의존. 약한 로컬 모델이 전제인데, 가장 강한 방어가 필요한 곳에 가장 약한 방어만 있다.
- **영향**: 사용자가 "안전장치 파일이 있으니 보호된다"고 **오인**할 수 있어, 차라리 없는 것보다 위험하다. OTP 포털에서 모델이 "제출/승인" 버튼을 누르는 걸 막을 코드가 없다.
- **수정 방향**: v3에서 `portal_research/policies/click_gate.py`로 **실제 코드 게이트** 구현 — 클릭 대상의 text/aria-label/value를 `DANGEROUS_ACTIONS.txt`와 매칭해 차단 + `BLOCKERS.md` 기록. 그때까지는 이 파일들이 "작동한다"는 인상을 주지 않도록 README에 "현재 미연결, 프롬프트 레벨만"이라 명시.

## 2.4 [P0] `/selfheal` command ↔ 지정 agent 권한 모순 (복구 불가능 구조)

- **문제**: `selfheal.md` 본문은 "apply safest recovery(복구를 적용하라)"를 지시하지만, 지정 agent `agentops-failure-analyst`는 frontmatter에서 `edit:false, write:false, bash:false`(완전 읽기전용).
- **왜 깨지나**: **이 agent는 물리적으로 복구를 적용할 수 없다.** command와 agent 권한이 정면 모순. 게다가 `agent:`가 subagent를 가리키므로 공식 동작상 child session(subtask)으로 트리거되는데, 그 child가 read-only라 아무것도 못 고친다.
- **영향**: "self-heal"이라는 이름과 달리 self-heal이 **구조적으로 불가능**. 분석만 하고 끝난다.
- **수정 방향**: `/selfheal`을 2단계로 — 본문에서 `agentops-failure-analyst`로 분류·계획(SELFHEAL_PLAN.md) 생성 후, **Task tool로 `agentops-repair`에게 위임**하도록 명시(§14에 전문). 또는 `/selfheal-plan`(analyst) + `/selfheal-apply`(repair) 분리.

## 2.5 [P1] `question: deny` ↔ 위험시 확인 정책 모순

- **문제**: supervisor에 `question: deny`를 걸어 "끊김 없이 계속"을 보장. 동시에 `agentops-safety`의 역할은 "위험버튼은 사용자가 명시 지시하지 않으면 차단".
- **왜 깨지나**: 위험액션 직전 사용자 확인이 필요한 상황에서 supervisor는 **질문 자체를 못 한다**. "계속 진행"과 "위험시 확인"은 한 agent에 공존 불가.
- **영향**: 위험상황에서 모델은 (a)질문 못 하니 그냥 진행하거나 (b)막혀서 멈춘다. 둘 다 나쁘다.
- **수정 방향**: 위험 판단을 **코드 게이트(2.3)로 이관**해 모델 질문에 의존하지 않게 한다. supervisor는 위험액션을 만나면 `BLOCKERS.md`에 기록하고 **해당 task만 blocked 처리 후 다음 task로 진행**(전체 중단 아님). 사용자 확인은 비동기로(블로커 리뷰).

## 2.6 [P1] `compaction summary = 승인`으로 오인하는 안전 구멍 (신규)

- **문제**: (신규 발견, #14923) "continue-until-stop"은 compaction 후 "다음 단계 목록"을 모델이 **이미 승인된 작업으로 오인**하기 쉬운 패턴. 실제로 승인 없이 git push까지 실행한 사례 보고.
- **왜 깨지나**: v2의 `COMPACT_HANDOFF.md`/`RESUME_PLAN.md`는 "다음 행동"을 나열하는데, compaction을 거치면 "이게 승인된 건지 그냥 계획인지"의 맥락이 소실된다. 약한 모델일수록 "목록에 있으니 하라는 거겠지"로 진행.
- **영향**: 포털 자동화처럼 부수효과(제출/전송)가 있는 작업에서 compaction 직후 **승인 없는 위험액션** 위험.
- **수정 방향**: handoff/resume 파일에서 **"승인됨(approved)" vs "계획됨(planned)"을 명시적으로 구분**하는 필드 도입. `next_step`은 항상 "계획"으로 표기하고, 위험액션은 코드 게이트(2.3)가 별도로 막는다. 새 failure type `UNAPPROVED_RESUME_ACTION` 추가(§9).

## 2.7 [P1] agent를 JSON과 Markdown 양쪽에 이중 정의

- **문제**: `merge_opencode()`가 `cfg["agent"]["agentops-supervisor"] = {...}` 설정. 동시에 `.opencode/agents/agentops-supervisor.md`도 같은 이름 존재.
- **왜 깨지나**: 공식 문서가 **이 충돌의 병합/우선순위를 명시 안 함**(나도 소스레벨까지는 확정 못 함 — **불확실**). 불확실한 상태에서 의도적 이중정의는 위험.
- **영향**: 어느 정의가 이기는지 OpenCode 버전에 따라 달라질 수 있어, supervisor 권한이 예상과 다르게 적용될 수 있다.
- **수정 방향**: **Markdown 단일 정의로 통일**, `opencode.json`의 `agent` 블록은 제거. `merge_opencode()`에서 `agent.setdefault(...)` 라인 삭제.

## 2.8 [P1] "수정은 repair만"을 supervisor 권한이 위반 가능

- **문제**: 아키텍처 원칙은 "분석은 병렬, 수정은 단일 repair agent". 그런데 supervisor가 `edit:true/write:true/patch:true` 전부 열려 있어 **직접 고칠 수 있다**.
- **왜 깨지나**: 권한이 열려 있으면 시스템 프롬프트의 "repair에게 위임하라"는 자연어 권고는 약한 모델에게 강제력이 없다. 약한 모델일수록 권고 무시하고 직접 고치려 든다.
- **영향**: 수정이 여러 경로로 일어나 추적·롤백·검증 흐름이 깨진다.
- **수정 방향**: supervisor `permission.edit: deny`. 모든 파일 수정은 Task로 `agentops-repair`에게만. **권한으로 강제하지 프롬프트로 설득하지 않는다**(§7).

## 2.9 [P2] `ROOT = Path.cwd()` — cwd 의존성

- **문제**: `agentops.py`가 프로젝트 루트를 `Path.cwd()`로 잡음. OpenCode bash tool의 실제 cwd에 의존.
- **수정 방향**: `Path(__file__).resolve().parent.parent`(스크립트 위치 기준)로 고정. cwd가 예상과 달라도 정확히 동작.

---

# 3. OpenCode 공식 호환성 문제 (파일별 정확한 수정안)

Sonnet의 1부 레퍼런스를 공식 기준으로 채택하되, 내가 직접 재확인한 부분을 보강한다.

## 3.1 `patch` → `apply_patch` + `tools:` → `permission:` 전면 전환

| 항목 | v2 현재 | 공식 기준 문제 | 수정안 |
|---|---|---|---|
| tool 이름 | `patch` (9개 agent + RULES.md) | **존재하지 않는 tool명**. 공식은 `apply_patch`. `tools:`의 `patch:false`는 실존 tool과 매칭 안 돼 **dead key** | `permission:`으로 전환하면 `edit` 키 하나가 write/edit/apply_patch 통합 통제 → 오타 문제 소멸 |
| `tools:` 필드 | 9개 agent 전부 boolean `tools:` | 공식 문서 명시: **"`tools` is deprecated. Prefer the agent's `permission` field"** | 전부 `permission:` 객체로 |
| `write`/`patch` 통제 이해 | "write and patch are controlled by edit permission" | **이해 자체는 정확** (공식: edit permission이 edit/write/apply_patch 커버). 단 명칭만 틀림 | 문장 유지, `patch`→`apply_patch` |

**중요 보강 — `bash: true`는 read-only가 아니다**: doctor/explorer/verifier/reporter/memory-curator가 "읽기전용" 의도로 `bash:true`를 줬지만, **bash는 `del`/`>` 리디렉션으로 파일을 변경·삭제할 수 있는 만능 명령**이다. 진짜 읽기전용을 강제하려면 bash를 패턴 화이트리스트로 좁혀야 한다:

```yaml
permission:
  read: allow
  grep: allow
  glob: allow
  edit: deny
  bash:
    "*": ask
    "python agent_ops/agentops.py *": allow
    "python -m py_compile *": allow
  task: deny
```

## 3.2 commands frontmatter — `subtask` 명시 누락

- **현재**: `/doctor`, `/selfheal`, `/verify`, `/memorycheck`, `/report`가 `agent:`에 **subagent**를 지정. 공식 동작상 **기본적으로 child session(subtask) 트리거**(공식: "If this is a subagent the command will trigger a subagent invocation by default").
- **문제**: 이게 의도인지 frontmatter에 명시 없음 — "기본값에 우연히 의존". 메인 컨텍스트 직접실행을 원하면 `subtask: false`, child session을 원하면 `subtask: true`를 **명시**해야 한다.
- **수정안**: 각 command에 의도를 명시. 진단/보고처럼 컨텍스트 오염 방지가 목적이면 `subtask: true` 명시.

## 3.3 `compaction.reserved = 12000` 고정값

- **현재**: 모든 모델에 `reserved: 12000` 고정.
- **문제**: 로컬 모델(Qwen 3.6 27B / EXAONE)의 실제 context window가 32K 수준이면 12000 reserved는 **가용 작업영역을 과도하게 잠식**. 공식이 권장값을 안 줌 → 모델별 산정 필요(**불확실** — 실제 context window 확인 후 결정).
- **수정안**: 모델 context window의 대략 10~15%로 산정. 32K면 4000~5000, 128K면 12000~16000. opencode.json에 모델별로 다르게.

## 3.4 잘 된 부분 (유지)

- `permission.task: {"*": deny, "agentops-*": allow}` — **공식 문법과 정확히 일치**, last-match-wins도 맞음. 유지.
- 전역 `webfetch: deny, websearch: deny` — "외부 다운로드 금지" 요구와 정확히 일치. **좋은 설계**, 유지.
- `$ARGUMENTS` 사용(`goal.md`) — 공식 문법 일치. 유지.
- backup 후 merge하는 `merge_opencode()`의 방어적 구조(기존 config 파싱 실패시 invalid 폴더로 백업) — 견고함. 유지.

**단, `permission.task`의 공식 한계 반드시 인지**: 공식 명시 — "Users can always invoke any subagent directly via the `@` autocomplete menu, even if the agent's task permissions would deny it." 즉 `permission.task`는 **모델의 자동호출만 막을 뿐 사용자의 `@직접호출`은 절대 못 막는다**. 안전경계를 `permission.task`에만 의존하면 안 된다.

---

# 4. v2 코드리뷰 (파일/함수 기준)

## `INSTALL_OPENCODE_AGENTOPS_CONTINUOUS_v2.py.txt`

| 위치 | 문제 | 수정 방향 |
|---|---|---|
| `merge_opencode()` instructions | append-only 메모리 3개를 instructions 영구등록 → **compaction 루프**(§2.2) | 고정 파일만 등록 |
| `merge_opencode()` agent setdefault | JSON+MD 이중정의(§2.7) | 라인 삭제, MD 단일화 |
| `merge_opencode()` compaction.reserved | 12000 고정(§3.3) | 모델별 가변 |
| `main()` 메모리 보존 로직 | `.agent-memory/` 존재시 skip — **방향은 옳음**. 단 `MEMORY_INDEX.json`은 매번 재생성되어야 하는데 같이 skip됨 | 메모리 데이터는 보존하되 인덱스는 재생성 분리 |
| `main()` AGENTS.md append | MARKER 체크 후 append — **재실행 안전성 좋음**. 단 append만 하고 갱신은 안 함 | 블록 단위 교체(MARKER~END 사이) 지원 |
| 전체 | Python stdlib-only — **내부망 no-download 요구에 정확히 부합**, 좋음 | 유지 |
| `subprocess.run(... agentops.py init)` | 설치 직후 init 실행 — 좋음. 단 실패해도 `check=False`라 조용히 넘어감 | init 실패시 경고 출력 |

## `agent_ops/agentops.py`

| 함수 | 문제 | 수정 방향 |
|---|---|---|
| `classify_failure()` | 12개 중 4개 미구현(NO_DATA/REPEATED_FAILURE/SESSION_EXPIRED/RISKY_ACTION_BLOCKED). 단순 `in` 매칭이라 오탐 가능(예: 정상 로그에 "syntaxerror" 단어) | §9 매핑대로 4개 추가 + history 기반 REPEATED_FAILURE |
| `selfheal()` | **계획만 쓰고 복구 안 함**. action_map에 4개 type 누락 | repair agent 위임 트리거 + action_map 완성 |
| `run_until_stop()` | bash tool 120초 상한에 죽음(§2.1). 실제 작업 없는 빈 루프 | 외부 전용 명시 + 실제 executor(§5) |
| `continue_once()` | `next_action` **문자열만 갱신**, 실제 작업 없음 | queue에서 task pop → executor 호출 구조로 |
| `safe_write()` | `.py`만 py_compile 검증. **롤백은 있으나 .json/.md 검증 없음**. 경로탈출 방어(`startswith(ROOT)`)는 좋음 | `.json`은 json.loads, `.md`는 UTF-8 디코딩 검증 추가 |
| `safe_write()` 백업 | `.bak` 단일 백업 — 연속 호출시 직전 것 덮어씀 | 타임스탬프 백업 또는 .bak.N 순환 |
| `add_lesson()` | **무한 append, 크기상한 없음**(§2.2) | 상한 + 아카이브 |
| `update_compact_handoff()` | lessons tail 3000자 자름 — 좋음. 단 실패로그 5개만 | 유지, 단 handoff에 approved/planned 구분(§2.6) |
| `doctor()` | Chrome 9222 체크/인코딩 라운드트립 — **실용적, 좋음**. ChromeDriver 후보경로 하드코딩(Desktop/local_LLM) | 후보경로를 env/config로 외부화 |
| `ROOT = Path.cwd()` | cwd 의존(§2.9) | `__file__` 기준 고정 |
| 동시성 | `ACTIVE_TASK.json` 등 **lock 없음, 원자적 쓰기 없음**. 여러 subagent 동시 쓰기시 레이스 | temp+rename 원자적 쓰기, lock 파일 |
| 전체 구조 | 단일 789라인(주석포함) 모놀리식 | §13처럼 모듈 분리 |

**doctor/verify/status/resume/checkpoint 실효성 평가**: 이들은 **실제로 도움이 된다** — 환경진단·상태스냅샷·체크포인트는 정직하게 동작하고 디버깅에 유용. 문제는 이것들이 "운영"이 아니라 "관찰·기록"이라는 점. v2의 가치는 여기(관찰가능성)에 있고, 결함은 "행동(복구·실행)"이 없다는 데 있다.

**`safe-write` rollback 충분성**: py_compile 실패시 백업복원은 **올바른 패턴**이나 (1).py만 검증 (2)단일 .bak (3)json/md 무검증으로 불충분. §6/§13에서 보강.

---

# 5. Continue-until-stopped 구조 개선안

## 현재 구조 평가

**근본적으로 잘못된 가정 위에 서 있다.** v2는 "OpenCode 세션 안에서 모델이 계속 돈다"를 전제하는데, bash tool 120초 상한(검증됨) 때문에 **OpenCode 안에서의 장기 실행은 불가능**하다. 모델 세션 자체도 사용자가 턴을 주지 않으면 멈춘다 — LLM은 자발적으로 다음 턴을 시작하지 못한다. 즉 "사용자가 멈출 때까지 계속"을 **OpenCode 세션만으로 구현하는 것은 원천 불가능**하다.

## 실제 task executor 필요 여부 → **반드시 필요. v3의 핵심.**

검토 prompt의 "사내 LLM API를 직접 호출하는 Python orchestrator가 필요한가?"에 대한 답은 **명백히 YES**. 이유:

- `agentops.py`에는 사내 LLM API 호출 코드가 **0**. 현재는 OpenCode의 LLM 호출에 100% 의존.
- OpenCode 세션은 (a)120초 bash 상한 (b)사용자 턴 필요 때문에 무인 장기실행 불가.
- 따라서 "OpenCode를 꺼도 계속"은 **OpenCode 외부 독립 프로세스 없이는 달성 불가능**.

## 권장 아키텍처: 이중 모드

```
[모드 A: 대화형 / OpenCode 세션 내]
  사용자가 OpenCode에서 작업 → supervisor가 task queue에 적재 → 
  /continue로 한 task씩 처리(continue-once) → checkpoint → 다음
  (각 turn은 사용자 입력으로 트리거, 120초 내 끝나는 단위작업만)

[모드 B: 무인 지속 / OpenCode 외부 Python orchestrator]
  RUN_AGENTOPS_ORCHESTRATOR.bat (별도 CMD) 또는 Windows 작업 스케줄러
    → orchestrator.py가 TASK_QUEUE.jsonl을 polling
    → 각 task를 사내 LLM API(OpenAI-compatible)로 직접 실행
    → 실패시 classify → repair task 자동 적재 → 재시도(max_retries)
    → STOP 파일 보이면 종료
    → 모든 상태를 agent_ops/state/*에 기록 (OpenCode와 공유)
```

핵심: **상태파일(`agent_ops/state/*`)이 두 모드의 공유 버스**. 모드 B가 무인으로 돌다가 사용자가 OpenCode를 켜면 모드 A가 같은 상태파일을 읽어 이어받는다. 이게 "OpenCode 껐다 켜도 이어가기"의 진짜 구현.

## 권장 queue schema (`TASK_QUEUE.jsonl`)

현재는 빈 파일로만 존재. 실제 schema:

```json
{"task_id":"task_0001","priority":1,"status":"pending","title":"...","goal_ref":"CURRENT_GOAL.md","owner_agent":"agentops-repair","depends_on":[],"attempt_count":0,"max_retries":3,"blocked_reason":null,"created_at":"ISO8601","updated_at":"ISO8601","risk":"safe|review_required"}
```

executor 루프:
1. STOP 있으면 종료
2. `status==pending && depends_on 모두 done`인 최우선 task pop
3. `attempt_count >= max_retries`면 `status=failed`, BLOCKERS 기록, 다음으로
4. 실행 → 성공시 `done`+DONE_LOG, 실패시 `attempt_count++` + classify + repair task 적재
5. 매 step CHECKPOINT 갱신 → 1로

## UI blocking 방지 방안

- **OpenCode bash tool 안에서 무한루프/장기명령 절대 금지** (룰 + command 본문에서 추천 삭제).
- 장기작업은 항상 외부 프로세스. OpenCode에서는 "외부 실행하세요" 안내만.
- OpenCode 세션 내 작업은 **단위작업(120초 내)**으로만 쪼개서 `continue-once`로.

---

# 6. Compact / resume 구조 개선안

## 현재 구조 평가

상태파일 레이아웃은 합리적이나, **compaction 후 모델이 이 파일들을 읽도록 강제할 수단이 없다**. 공식 확인(#16960): instructions/AGENTS.md는 compaction 후 신뢰성 있게 유지되지 않는다. AGENTS.md 텍스트로 "compact 후 읽어라"라고 적는 건 **강제력 없는 기대**일 뿐.

## compact 후 handoff 보장 — 유일한 진짜 강제 지점

공식적으로 compaction에 개입 가능한 단 하나의 지점: **plugin의 `experimental.session.compacting` 훅**. `output.prompt`를 설정하면 기본 compaction 프롬프트를 완전 대체한다.

```ts
// .opencode/plugins/compaction-handoff.ts
import { readFileSync } from "fs"
export const CompactionHandoff = async (ctx) => ({
  "experimental.session.compacting": async (input, output) => {
    let handoff = ""
    try { handoff = readFileSync("agent_ops/state/COMPACT_HANDOFF.md","utf-8") } catch {}
    output.prompt = [
      "Summarize the session below. Preserve verbatim the durable state references.",
      "After compaction, the FIRST action MUST be to read these files in order:",
      "agent_ops/state/COMPACT_HANDOFF.md, RESUME_PLAN.md, ACTIVE_TASK.json, CHECKPOINT.json.",
      "CRITICAL: items under 'next_step' are PLANNED, NOT approved. Do not perform any",
      "risk:review_required action without explicit user approval in THIS session.",
      "",
      "=== CURRENT DURABLE HANDOFF (inject verbatim) ===",
      handoff,
    ].join("\n")
  },
})
```

**주의**: `experimental.*`는 공식적으로 안정성 미보장 — OpenCode 업그레이드시 동작 변경 가능. v3에서 쓰되 버전 핀 권장.

**`COMPACT_HANDOFF.md`를 instructions에 넣을지 → 넣지 마라** (Sonnet 권고 동의, 이유 강화):
- instructions는 매 이터레이션 재주입 + size guard 없음(#18037). 휘발성 핸드오프를 넣으면 갱신될수록 컨텍스트 압박.
- 대신 이중방어: (1)AGENTS.md에 "compact 후 handoff 읽어라" 고정 안내 + (2)위 plugin 훅으로 summary 프롬프트에 강제 주입.

**불확실성 정정**: Sonnet 부록 #3은 "instructions가 compaction 후 재주입되면 권고가 바뀔 수 있다"고 했으나, #16960으로 **재주입이 보장되지 않음을 확인** → 권고 유지 확정. plugin 훅이 정답.

## 권장 schema

`CHECKPOINT.json`:
```json
{"checkpoint_id":"ckpt_xxxx","updated_at":"ISO8601","run_id":"run_xxxx","cwd":"...","active_task_id":"task_xxxx","last_completed_step":"...","next_step":"...","next_step_status":"planned","stop_file_exists":false,"compaction_count":0,"restart_count":0,"interrupted":false}
```

`ACTIVE_TASK.json`:
```json
{"task_id":"task_xxxx","status":"pending|active|blocked|done|failed","owner_agent":"agentops-repair","title":"...","created_at":"ISO8601","updated_at":"ISO8601","depends_on":[],"attempt_count":0,"max_retries":3,"last_failure_type":null,"blocked_reason":null,"risk":"safe|review_required"}
```

**`ACTIVE_TASK.json` vs `CHECKPOINT.json` 역할 중복 여부**: 부분 중복이나 **분리 유지가 맞다**. ACTIVE_TASK는 "지금 무슨 task"(task 도메인), CHECKPOINT는 "런 전체 진행상태"(run 도메인 — compaction_count, restart_count, interrupted 등 task 외 메타). CHECKPOINT가 ACTIVE_TASK를 임베드(현재 코드처럼)하되 역할은 분리.

## forced shutdown / interrupted 감지

현재 v2에 **없는 중요 기능**. 방법:
- `RUN_STATE.json`에 `status` + `last_heartbeat`. 
- 새 세션 시작시 `init`/`resume`이 last_heartbeat 확인 → status가 `running`인데 heartbeat가 N분 이상 오래됐으면 **이전 런이 비정상 종료(interrupted)**로 판정 → `CHECKPOINT.interrupted=true` 세팅 → resume 플랜에 "직전 작업이 중단됨, ACTIVE_TASK부터 검증 후 재개" 명시.

## `LAST_KNOWN_GOOD.json` 필요 여부 → **필요. 추가 권장.**

verify가 통과한 마지막 상태의 스냅샷. repair가 망가뜨렸을 때 롤백 기준점. `verify()` 성공시 현재 CHECKPOINT를 `LAST_KNOWN_GOOD.json`으로 복사. selfheal이 N회 실패하면 LAST_KNOWN_GOOD로 롤백.

---

# 7. Subagent / 병렬 처리 추천 구조

## 유지할 agent (9개 분리는 과하지 않다 — 합리적)

역할분리(진단/분류/수정/탐색/보고/메모리/검증/안전/supervisor)는 명확하고 적절. **단순화보다 권한 강제 정교화가 맞다.**

## 합칠 agent → 없음. 단 권한 재설계

- `agentops-doctor` + `agentops-verifier`는 합칠 수도 있으나(둘 다 진단성), 역할이 다르므로(환경 vs 변경검증) **분리 유지** 권장.

## 추가할 agent → `agentops-orchestrator` (개념적)

OpenCode subagent가 아니라 **외부 Python orchestrator**(§5 모드 B). 이건 .md agent가 아니라 별도 프로세스.

## OpenCode 내부 subagent vs Python API orchestrator → **둘 다, 역할 분리**

- **OpenCode subagent**: 대화형 모드(A)에서 사용자가 켜둔 세션 내 위임. 분석·계획·검증·보고.
- **Python orchestrator**: 무인 모드(B)에서 사내 LLM API 직접 호출로 queue 소비.
- 두 세계의 접점은 상태파일.

## 분석 병렬화 / 수정 단일화 전략 → **"순차 위임 + 락"이 현실적**

**공식 확인(#14195): 한 응답의 다중 Task는 `tasks.pop()`으로 순차 실행된다. 진짜 병렬 아님.** 따라서:

- "여러 specialist 동시 분석"은 **코어 OpenCode만으로 불가능**(oh-my-opencode 같은 서드파티 플러그인의 background task가 필요한데, 내부망 no-download 환경에선 비현실적).
- **순차 위임 체인**으로 설계: supervisor가 analyst→(필요시)repair→verifier 순서로 Task 위임, 각 사이 CHECKPOINT 갱신. 디버깅·롤백이 쉽고 레이스 없음.
- 수정 단일화: **`permission.edit`로 강제**. analyst/explorer/verifier/reporter/doctor/safety = `edit:deny`, repair만 `edit:allow`. supervisor도 `edit:deny`(§2.8). 이러면 "수정은 repair만"이 권한으로 보장된다 — 프롬프트 설득 불필요.
- 동시성을 굳이 쓴다면 독립 탐색(explorer)을 사용자가 `@mention`으로 수동 다중 호출하는 정도로 제한하고, **파일 수정은 항상 직렬**.
- 무인 모드(B)의 병렬은 Python orchestrator가 `asyncio`/스레드풀로 사내 H100 LLM을 동시 호출(비용 무관 전제) — **여기가 진짜 병렬을 둘 곳**. 단 파일 수정 task는 락으로 직렬화.

---

# 8. Memory lifecycle 추천 구조

## Markdown vs JSONL → **JSONL을 source-of-truth, Markdown은 파생 뷰**

현재 `LESSONS_LEARNED.md`/`ERROR_PATTERNS.md`는 freeform append이며 ID/timestamp/status/출처 메타데이터가 **전무**. 자동 curate(분류·deprecate)하려면 구조화 필수.

```
.agent-memory/memory.jsonl   ← 진실의 원천 (source of truth)
.agent-memory/*.md           ← memory.jsonl에서 렌더링되는 읽기용 뷰
```

## metadata schema (각 JSONL 라인)

```json
{"id":"mem_xxxx","type":"lesson|error_pattern|preference|project_state","status":"active|resolved|deprecated|needs_review","text":"...","related_failure_type":"TOOL_TEXT_ONLY","related_task_id":"task_xxxx","created_at":"ISO8601","updated_at":"ISO8601","supersedes":null,"superseded_by":null,"source":"selfheal|user|verify"}
```

## 자동 deprecate 위험 통제 → **2단계 구조가 정답** (검토 prompt 제시안 채택)

약한 모델이 메모리를 **단일 단계로 직접 영구삭제/변경하는 것은 위험**(잘못된 deprecate = 영구손실). 따라서:

1. `agentops-memory-curator`는 **제안만** → `agent_ops/state/MEMORY_UPDATE_PLAN.md` 생성 (어떤 id를 어떤 status로 바꿀지, 근거 포함).
2. **반영은 별도 단계**: `agentops-verifier`가 plan을 검증 후 적용, 또는 위험한 deprecate는 사용자 승인 게이트.
3. curator는 `memory.jsonl`을 직접 못 쓰게 — `permission.edit`를 plan 파일 경로로만 제한하거나, 반영은 `agentops.py memory-apply` CLI로만.

**현재 코드는 deprecate 로직 자체가 없으므로**, 처음부터 2단계로 만드는 게 1단계로 만들었다 나중에 안전장치 붙이는 것보다 쉽다.

## MEMORY_UPDATE_PLAN 방식 필요 여부 → **필요.** 위 2단계의 핵심.

## 사용자 불만/실패를 다음 작업에 반영하는 가장 안정적 방식

1. 실패 발생 → `selfheal`이 `memory.jsonl`에 `type:lesson, status:active, related_failure_type:X` 추가.
2. `next_action_text()`가 최근 active lesson/error_pattern을 읽어 "이 실패 반복 금지"를 명시.
3. **단, instructions에 상주시키지 않고**(§2.2) executor/supervisor가 task 시작 전 read tool로 관련 lesson만 조회.
4. 동일 실패 2회 → REPEATED_FAILURE(§9) → 해당 접근법을 deprecated로 제안, 대안 강구.

---

# 9. Failure classifier / self-heal 개선안

## 추가할 failure type (4개 미구현 + 신규)

| type | 감지 방법 | recovery action |
|---|---|---|
| `REPEATED_FAILURE` | 최근 3건 failure_log의 type이 동일 ≥2 | 같은 접근 중단, 대안 시도, max 도달시 task=failed+BLOCKERS, 사용자 알림 |
| `SESSION_EXPIRED` | "session expired/login required/302 redirect to login" | 자동 로그인 금지(OTP). BLOCKERS에 "사용자 재로그인 필요" 기록, 해당 포털 task 일시중지 |
| `RISKY_ACTION_BLOCKED` | click_gate가 위험버튼 차단시 | 해당 액션 skip, BLOCKERS 기록, 안전한 대안 경로 탐색 |
| `NO_DATA` | 탐색 결과 0건/빈 result 파일 | 셀렉터/검색조건 재확인, explorer 재위임, 그래도 0이면 "데이터 없음" 보고하고 다음 task |
| `UNAPPROVED_RESUME_ACTION` (신규) | compaction/resume 직후 risk:review_required 액션 시도 | 차단 + 사용자 승인 대기. compaction-summary-as-approval 구멍(§2.6) 방어 |
| `BASH_TIMEOUT` (신규) | "operation timed out / timed out after 120000ms" | 장기명령을 외부 프로세스로 이관 안내. 무한루프를 bash로 실행했는지 점검 |

## repeated failure 감지 (가장 작은 코드로 가장 큰 안전성)

```python
def classify_failure_with_history(text: str, recent: list) -> str:
    ftype = classify_failure(text)
    recent_types = [r.get("type") for r in recent[-3:] if isinstance(r, dict)]
    if ftype != "UNKNOWN" and recent_types.count(ftype) >= 2:
        return "REPEATED_FAILURE"
    return ftype
```
`log_failure()`에서 `tail_jsonl(failure_log, 5)`를 먼저 읽고 이 함수로 분류. **이게 selfheal 무한루프(자기치유가 자기치유 호출)를 막는 핵심 가드.**

## self-heal이 실제 복구까지 하려면

현재 selfheal은 계획만 씀. 실제 복구 흐름:
```
selfheal → classify(history) → SELFHEAL_PLAN.md 생성 →
  Task로 agentops-repair 위임(실제 수정) →
  agentops-verifier로 검증(py_compile + status + 회귀) →
  성공: LAST_KNOWN_GOOD 갱신, checkpoint, 계속
  실패+attempt<max: 다른 전략으로 재시도
  실패+attempt>=max: LAST_KNOWN_GOOD 롤백, task=failed, BLOCKERS, 사용자 알림
```

## rollback / safe-write / verify 강화

- **safe_write**: `.py`→py_compile, `.json`→json.loads, `.md`→UTF-8 디코딩 검증. 백업을 타임스탬프로(단일 .bak 덮어쓰기 방지).
- **원자적 쓰기**: 모든 상태파일 쓰기를 temp파일+`os.replace`(원자적 rename)로. 쓰기 중 크래시시 손상 방지.
- **rollback 기준점**: `LAST_KNOWN_GOOD.json`(§6). verify 통과시 갱신, repair 연속실패시 복원.

---

# 10. Windows 내부망 안정성 보강

## 전반 평가

정책(BAT ASCII-only, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, `errors="replace"`)은 **합리적이고 v2에서 잘 지켜진다**. BAT도 ASCII-only 준수 확인. 보강점만:

## BAT vs Python launcher → **Python 중심 + 얇은 BAT 런처**

- `.bat.txt` 방식 유지(내부망 반입 편의). 단 BAT는 **환경설정+python 호출만** 하는 얇은 런처로 유지하고 로직은 전부 Python.
- **`python`이 PATH에 없는 환경 대비책 부재** — 사내 PC가 `py` launcher만 있거나 Anaconda면 BAT 실패. `where python` 체크 후 `py -3` fallback 추가:
```bat
@echo off
setlocal EnableExtensions
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
where python >nul 2>nul && (set PYEXE=python) || (set PYEXE=py -3)
%PYEXE% "%~dp0agent_ops\agentops.py" %*
```

## encoding

충분. 단 BAT가 `chcp 65001`을 안 함 — ASCII-only라 당장 문제없지만, 혹시 BAT에서 한글 경로를 echo할 일이 생기면 `chcp 65001 >nul` 추가 고려(현재는 불필요).

## path handling

- BAT의 `"%~dp0..."` 인용 — **잘 됨**.
- `agentops.py`의 `subprocess.run`이 인자를 **리스트로 전달**(셸 문자열 결합 아님) — 경로 공백/한글에 **안전. 좋음**.
- 보강: `ROOT = Path.cwd()` → `Path(__file__).resolve().parent.parent`로 고정(§2.9).

## no-download environment

- stdlib-only 설계 — **정확히 부합, 좋음**.
- `merge_opencode()`의 `webfetch:deny, websearch:deny` — 정확히 부합.
- 보강: orchestrator(§5)가 사내 LLM API를 호출할 때도 사내 엔드포인트만, 외부 의존성 0 유지.

## logging

- JSONL 로그(failure/controller/recovery) — **좋은 패턴**. 단 무한 증식. 로그 로테이션(크기/날짜 상한, 오래된 건 `logs/archive/`) 추가.

---

# 11. Portal automation plugin 설계 제안

## 모듈 위치

- **Chrome attach doctor → `agent_ops` 공통 유지** (현재 `doctor()`의 9222 체크). Chrome 9222 점검은 포털 전용이 아니라 환경진단의 일부. Sonnet 동의.
- **포털 자동화 runner → `portal_research/` plugin으로 분리**. AgentOps 코어와 독립.

## Chrome attach doctor

현재 `doctor()`의 `urllib.request.urlopen("http://127.0.0.1:9222/json/version")` 체크 유지. 보강: 9222 살아있는지 + attach 가능한지 + 현재 탭 URL이 기대 포털인지까지 확인.

## safe click classifier → **반드시 코드 레벨** (현재 dead policy)

```
portal_research/policies/click_gate.py
  - 입력: 클릭 대상 element의 {text, aria-label, title, value, id, class, href, form_action}
  - DANGEROUS_ACTIONS.txt 키워드와 매칭
  - 단순 키워드 매칭만으로는 부족 → scoring:
      text/aria-label/value 매칭 = 위험 가중치 高
      href가 submit/delete 엔드포인트 = 高
      form action이 POST + 위험 URL = 高
      id/class에 'btn-danger','delete' = 中
  - score >= 임계값 → 차단 + BLOCKERS.md 기록 + RISKY_ACTION_BLOCKED
  - "사용자가 그 액션을 명시 지시"한 경우만 예외(화이트리스트 task_id 대조)
```

**단순 위험키워드 방식으로 충분한가 → 불충분.** DOM text만 보면 "확인"같은 모호한 버튼을 놓치거나, 아이콘 버튼(텍스트 없음)을 못 잡는다. **aria-label/title/value/href/form_action 다중신호 scoring 필요**(검토 prompt 제시안 채택).

## result schema (selector 저장, JSONL)

```json
{"selector":"...","label":"...","aria_label":"...","page_url":"...","element_type":"button|link|input","risk":"safe|dangerous|unknown","risk_score":0.0,"last_verified":"ISO8601","task_id":"task_xxxx"}
```

## screenshot / html snapshot 저장 정책

- **매 스텝 저장 금지**(디스크 부담). **위험액션 직전/직후 + 실패시에만** 저장.
- 파일명: `{task_id}_{timestamp}_{before|after|fail}.png`.
- `watcher.ignore`에 이미 `portal_research/screenshots/**`, `html_snapshots/**` 포함됨 — **좋음**(워처 부하 방지).

## safety policy (OTP/비밀번호/쿠키/토큰)

- 현재 시스템 프롬프트 금지만 → **코드 레벨로 강화**.
- Selenium `debuggerAddress=127.0.0.1:9222` attach만 허용(신규 브라우저 기동 금지).
- **CDP 레벨에서 쿠키/storage 접근 API 호출 자체를 차단** — plugin이 허용 API 화이트리스트만 노출. `Network.getCookies`, `Storage.*` 등은 호출 경로 자체를 막는다.
- OTP/비밀번호 입력 필드(`type=password`, OTP 패턴)에는 **자동 입력 절대 금지** — 사용자가 직접 로그인한 세션에 attach만.

## v3에서 portal plugin 분리 형태

```
portal_research/
  plugin.py            # attach + 탐색 runner (Selenium debuggerAddress)
  policies/
    click_gate.py      # 코드 레벨 위험클릭 차단
    DANGEROUS_ACTIONS.txt  # click_gate가 실제로 읽음
    ALLOWED_ACTIONS.txt
  schema/
    selectors.jsonl    # 발견한 셀렉터 + risk
  reports/ results/ logs/ screenshots/ html_snapshots/
```
AgentOps 코어는 portal_research를 **선택적 plugin으로만** 의존(없어도 코어 동작).

---

# 12. v3 구현 우선순위

## P0 (안전·정합성, 즉시)

1. **`run-until-stop`을 OpenCode bash tool에서 분리** — `/agentrun`을 외부실행 안내로 재작성, 함수에 `--once` 게이트. (120초 침묵사 차단)
2. **append-only 메모리를 `instructions`에서 제거** + `add_lesson()` 크기상한. (compaction 루프 폭탄 해체)
3. **dead safety 파일을 실제로 읽는 코드 게이트** — 최소한 click_gate.py 스텁이라도. (가짜 안전장치 제거)
4. **`/selfheal` ↔ failure-analyst 권한 모순 해결** — repair 위임 2단계.
5. **`tools:` → `permission:` 전면 전환 + `patch`→`apply_patch`** — 9개 agent. (리스크 거의 0, 즉시)
6. **supervisor `edit:deny` + 수정권한 repair 단일화** — 권한으로 강제.
7. **agent JSON+MD 이중정의 제거** — MD 단일화.

## P1 (핵심 기능, 다음)

8. **REPEATED_FAILURE + 미구현 4개 failure type 구현** — history 기반 분류.
9. **`experimental.session.compacting` plugin 훅** — compact handoff 강제 주입 + approved/planned 구분.
10. **실제 task executor(Python orchestrator)** — 사내 LLM API 직접 호출, queue 소비, 무인 모드 B.
11. **interrupted 감지 + LAST_KNOWN_GOOD** — forced shutdown 복구.
12. **safe_write 검증 확장(.json/.md) + 원자적 쓰기 + lock**.

## P2 (견고성)

13. **메모리 JSONL source-of-truth + MEMORY_UPDATE_PLAN 2단계**.
14. **`ROOT`를 `__file__` 기준 고정** + `py -3` fallback BAT.
15. **로그 로테이션** + compaction.reserved 모델별 가변.

## P3 (확장)

16. **portal plugin 완성** — click_gate scoring, CDP API 화이트리스트, 셀렉터 schema.
17. **agentops.py 모듈 분리**(§13).

---

# 13. v3 파일 구조 (생성/수정 트리)

```
프로젝트루트/
  opencode.json                      # 수정: instructions 축소, agent블록 제거, reserved 가변
  AGENTS.md                          # 수정: MARKER 블록 교체식, planned/approved 구분 안내

  .opencode/
    agents/                          # 9개 전부 수정: tools:→permission:, edit단일화
      agentops-supervisor.md         #   edit:deny, bash 화이트리스트, task allow
      agentops-repair.md             #   유일하게 edit:allow
      (나머지 7개)                    #   edit:deny, bash 화이트리스트
    commands/                        # 수정: subtask 명시, selfheal 2단계
      agentrun.md                    #   외부실행 안내로 전면 재작성
      selfheal.md                    #   repair 위임 명시
    plugins/                         # 신규
      compaction-handoff.ts          #   experimental.session.compacting 훅

  agent_ops/
    AGENTOPS_RULES.md                # 수정: patch→apply_patch, bash무한루프 금지룰
    agentops.py                      # 수정: §4 전부. ROOT고정, history분류, 검증확장
    orchestrator.py                  # 신규: 사내 LLM API 호출, queue executor (모드 B)
    llm_client.py                    # 신규: OpenAI-compatible 사내 게이트 클라이언트
    state_io.py                      # 신규: 원자적 쓰기 + lock 공통모듈
    state/
      CURRENT_GOAL.md ACTIVE_TASK.json CHECKPOINT.json RESUME_PLAN.md
      COMPACT_HANDOFF.md HEARTBEAT.json RUN_STATE.json BLOCKERS.md DONE_LOG.md
      TASK_QUEUE.jsonl               # 신규 활성화: §5 schema, executor가 실제 소비
      LAST_KNOWN_GOOD.json           # 신규: verify통과 스냅샷
      MEMORY_UPDATE_PLAN.md          # 신규: 메모리 2단계 제안
    policies/
      DANGEROUS_ACTIONS.txt ALLOWED_ACTIONS.txt   # 유지(이제 click_gate가 읽음)
    logs/ (+ archive/)               # 로그 로테이션
    reports/ results/ control/

  .agent-memory/
    memory.jsonl                     # 신규: source of truth (metadata schema)
    *.md                             # memory.jsonl에서 렌더링되는 뷰로 전환
    archive/                         # 신규: 오래된 lesson 이동처
    MEMORY_INDEX.json

  portal_research/                   # plugin (선택적)
    plugin.py click_gate.py(→policies/)  # 신규: 코드 게이트
    schema/selectors.jsonl
    reports/ results/ logs/ screenshots/ html_snapshots/

  RUN_AGENTOPS_ORCHESTRATOR.bat.txt  # 신규: 모드 B 외부 실행(별도 CMD)
  RUN_AGENTOPS_*.bat.txt             # 수정: py -3 fallback
```


---

# 14. v3 구현 지시문 (다음 모델에게 그대로 전달)

> 아래는 v3 빌더 모델에게 바로 줄 수 있는 지시문이다. OpenCode 공식 사실은 위 보고서를 신뢰하고, 추가 웹리서치 없이 구현에 집중하라.

## 지시 0: 전제

- Windows 10 내부망, Python 3.11, 외부 다운로드 금지(stdlib + 사내 LLM API만).
- OpenCode bash tool은 **하드코딩 120초 타임아웃**이 있다. bash tool 안에서 무한루프/장기명령을 절대 실행하지 마라.
- OpenCode subagent의 다중 Task는 **순차 실행**된다(병렬 아님). 병렬 가정 금지.
- OpenCode `instructions`/AGENTS.md는 **매 이터레이션 재주입되고 compaction 후 유지가 보장되지 않는다**. 증식하는 파일을 instructions에 넣지 마라.

## 지시 1 [P0]: agent frontmatter 전면 교체

`.opencode/agents/*.md` 9개 전부 `tools:` 블록을 삭제하고 `permission:`으로 교체. `patch`라는 단어를 전부 제거(`apply_patch`가 정식명이나, `edit` permission이 write/edit/apply_patch를 통합 통제하므로 개별 명시 불필요).

**supervisor** (`agentops-supervisor.md`):
```yaml
---
description: Primary controller for durable continue-until-stop AgentOps workflow
mode: primary
permission:
  read: allow
  grep: allow
  glob: allow
  edit: deny
  bash:
    "*": ask
    "python agent_ops/agentops.py *": allow
  todowrite: allow
  question: deny
  task:
    "*": deny
    "agentops-*": allow
---
(본문 유지)
```

**repair만 수정 허용** (`agentops-repair.md`):
```yaml
---
description: Code and script repair specialist
mode: subagent
permission:
  read: allow
  grep: allow
  glob: allow
  edit: allow
  bash:
    "*": ask
    "python *": allow
    "rm *": deny
    "del *": deny
  task: deny
---
(본문 유지)
```

**나머지 7개**(doctor/failure-analyst/explorer/reporter/memory-curator/verifier/safety) 공통:
```yaml
permission:
  read: allow
  grep: allow
  glob: allow
  edit: deny
  bash:
    "*": ask
    "python agent_ops/agentops.py *": allow
    "python -m py_compile *": allow
  task: deny
```
(failure-analyst/safety는 bash도 불필요하면 `bash: deny`)

## 지시 2 [P0]: command 수정

**`agentrun.md`** 전면 재작성 (bash 무한루프 실행 금지):
```markdown
---
description: How to run AgentOps continuously OUTSIDE the OpenCode session
agent: agentops-supervisor
subtask: false
---

Do NOT run `run-until-stop` inside the OpenCode bash tool. The bash tool kills any
command after 120 seconds, so the loop dies silently and you will falsely believe
it is still running.

To run continuously, tell the user to do ONE of:
1. Open a separate CMD window and run `RUN_AGENTOPS_ORCHESTRATOR.bat`.
2. Register `python agent_ops/agentops.py continue-once` in Windows Task Scheduler
   to run every N minutes.

Both run independently of OpenCode, so closing OpenCode does not stop them.
```

**`selfheal.md`** 2단계 (read-only analyst가 복구 못 하는 모순 해결):
```markdown
---
description: Classify the latest failure and delegate the fix to the repair agent
agent: agentops-failure-analyst
subtask: true
---

Run `python agent_ops/agentops.py selfheal` to classify the latest failure (with
repeat detection) and produce SELFHEAL_PLAN.md. Read SELFHEAL_PLAN.md.

You are READ-ONLY. Do not fix anything yourself. Delegate the recommended actions to
`agentops-repair` via the Task tool. After repair, run `/verify`. If verify fails and
attempt_count < max_retries, retry with a different strategy. If max reached, roll back
to LAST_KNOWN_GOOD.json, mark the task failed, record BLOCKERS.md, and notify the user.
```

진단/보고 command(`doctor`/`verify`/`memorycheck`/`report`)에 `subtask: true` 추가(컨텍스트 오염 방지 의도 명시).

## 지시 3 [P0]: opencode.json 머지 로직 수정

`merge_opencode()`에서:
- `instructions`를 **고정 파일만**으로: `["AGENTS.md", "agent_ops/AGENTOPS_RULES.md"]`. `.agent-memory/*`는 **제거**(증식→compaction 루프).
- `agent.setdefault("agentops-supervisor", {...})` **라인 삭제**(MD 단일정의).
- `compaction.reserved`를 모델 context window의 ~12%로(32K면 4000, 128K면 16000). 모르면 사용자에게 모델 context 크기를 물어라.

## 지시 4 [P0]: agentops.py 핵심 수정

```python
# (1) ROOT 고정
ROOT = Path(__file__).resolve().parent.parent

# (2) history 기반 분류 — selfheal 무한루프 방지
def classify_failure_with_history(text, recent):
    ftype = classify_failure(text)
    rt = [r.get("type") for r in recent[-3:] if isinstance(r, dict)]
    if ftype != "UNKNOWN" and rt.count(ftype) >= 2:
        return "REPEATED_FAILURE"
    return ftype
# log_failure()에서 tail_jsonl(failure_log,5)를 읽어 이 함수로 분류

# (3) 미구현 failure type 추가 (classify_failure 내)
#   SESSION_EXPIRED: "session expired"/"login required"/"redirect to login"
#   NO_DATA: 결과 0건 (호출부에서 판정해 log-failure로 전달)
#   RISKY_ACTION_BLOCKED: click_gate가 전달
#   UNAPPROVED_RESUME_ACTION: resume 직후 risk:review_required 시도
#   BASH_TIMEOUT: "timed out after 120000"/"operation timed out"

# (4) safe_write 검증 확장
#   .py → py_compile (기존)
#   .json → json.loads 검증, 실패시 백업복원
#   .md → UTF-8 디코딩 검증
#   백업을 .bak 단일이 아니라 .bak.{timestamp}로

# (5) add_lesson 크기상한
def add_lesson(text):
    path = MEM / "LESSONS_LEARNED.md"
    existing = read_text(path)
    if text.strip() and text.strip() not in existing:
        write_text(path, existing.rstrip() + f"\n\n## Lesson {now()}\n\n{text.strip()}\n")
    # 라인수/바이트 상한 초과시 오래된 lesson을 .agent-memory/archive/로 이동

# (6) 원자적 쓰기 — write_text/write_json을 temp+os.replace로
def write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content.replace("\r\n","\n"), encoding="utf-8")
    os.replace(str(tmp), str(path))  # 원자적

# (7) interrupted 감지 — init/resume에서
#   RUN_STATE.last_heartbeat가 status=running인데 N분 이상 오래면
#   CHECKPOINT.interrupted=true, RESUME_PLAN에 "직전 중단, ACTIVE_TASK 검증 후 재개"

# (8) LAST_KNOWN_GOOD — verify() 성공시 CHECKPOINT를 복사
```

## 지시 5 [P1]: 실제 task executor (모드 B)

`agent_ops/orchestrator.py` 신규. OpenCode와 독립 프로세스. 사내 LLM API(OpenAI-compatible)를 `llm_client.py`로 호출.

```python
# orchestrator.py 골격
def run():
    while not (CONTROL/"STOP").exists():
        task = pop_next_ready_task()          # TASK_QUEUE.jsonl, depends_on 충족+우선순위
        if task is None:
            heartbeat("idle"); time.sleep(POLL); continue
        if task["attempt_count"] >= task["max_retries"]:
            mark_failed(task); record_blocker(task); continue
        if task.get("risk") == "review_required" and not approved(task):
            mark_blocked(task, "needs user approval"); continue
        heartbeat("running", task["task_id"])
        result = execute_task_via_llm(task)   # llm_client로 사내 LLM 호출
        if result.ok:
            mark_done(task); append_done_log(task)
            if verify_ok(): update_last_known_good()
        else:
            ftype = classify_failure_with_history(result.text, recent_failures())
            task["attempt_count"] += 1; task["last_failure_type"] = ftype
            enqueue_repair_task(task, ftype)  # repair task 적재
        update_checkpoint(f"executor step {task['task_id']}")
    heartbeat("stopped")
```
`llm_client.py`는 사내 게이트 엔드포인트만(EXAONE/Qwen). 외부 호출 0. 타임아웃·재시도·토큰상한 처리.

## 지시 6 [P1]: compaction plugin

`.opencode/plugins/compaction-handoff.ts` (§6 코드 사용). `experimental.session.compacting`에서 `COMPACT_HANDOFF.md`를 summary 프롬프트에 강제 주입 + "next_step은 planned이지 approved가 아니다" 경고 + "compact 후 첫 행동은 handoff/resume 파일 읽기" 강제. `experimental.*`는 버전 불안정하니 OpenCode 버전 핀.

## 지시 7 [P1]: click_gate 코드 게이트

`portal_research/policies/click_gate.py` 신규. `DANGEROUS_ACTIONS.txt`를 **실제로 읽어** 클릭 대상의 text/aria-label/title/value/href/form_action를 multi-signal scoring. 임계값 초과시 차단+BLOCKERS+RISKY_ACTION_BLOCKED. 사용자 명시지시(화이트리스트 task_id) 예외. password/OTP 필드 자동입력 절대금지. CDP 쿠키/storage API 화이트리스트 차단.

## 지시 8 [P2]: 메모리 2단계

`.agent-memory/memory.jsonl`을 source-of-truth로(metadata schema §8). `.md`는 렌더 뷰. `agentops-memory-curator`는 `MEMORY_UPDATE_PLAN.md`만 생성(직접 deprecate 금지). 반영은 `agentops.py memory-apply` 또는 verifier 검증 후. 자동 영구삭제 절대 금지.

## 검증 체크리스트 (v3 완료 기준)

- [ ] `python -m py_compile agent_ops/agentops.py orchestrator.py llm_client.py state_io.py` 전부 통과
- [ ] 9개 agent .md에 `patch`/`tools:` 단어 0 (grep)
- [ ] `instructions`에 `.agent-memory` 경로 0
- [ ] `DANGEROUS_ACTIONS.txt`를 읽는 코드 존재 (grep — dead file 아님)
- [ ] `TASK_QUEUE.jsonl`을 읽어 소비하는 executor 존재 (grep — dead schema 아님)
- [ ] bash tool로 `run-until-stop` 추천하는 command 본문 0
- [ ] supervisor `edit:deny`, repair만 `edit:allow`
- [ ] REPEATED_FAILURE 감지 코드 존재
- [ ] 원자적 쓰기(os.replace) 적용
- [ ] orchestrator가 사내 LLM API만 호출, 외부 도메인 0

---

# 불확실성 명시 (정직하게)

다음은 공식 문서·이슈로도 **확정하지 못한** 부분이다. v3 적용 전 실측 권장:

1. **`opencode.json` agent블록 + `.opencode/agents/*.md` 동일이름 충돌 병합규칙** — 공식 문서 미명시, 소스레벨 미확인. → MD 단일정의로 회피(충돌 자체를 만들지 않음).
2. **로컬 모델(Qwen 3.6 27B/EXAONE)의 실제 context window 크기** — 사용자만 안다. `compaction.reserved` 산정에 필요.
3. **`experimental.session.compacting` 훅의 버전 안정성** — `experimental.*`라 OpenCode 업그레이드시 동작 변경 가능. 공식이 안정성 미보장 명시.
4. **bash 120초 타임아웃이 사내 OpenCode 빌드/버전에도 동일한지** — 공식 기본값은 120초(확인)이나, 사내 설치본이 `OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS`로 바꿔놨을 수 있음. 사내 환경에서 `time python -c "import time;time.sleep(180)"`를 bash tool로 실행해 실측 권장.

이 네 가지는 "추정으로 코드를 박지 말고 실측 후 결정"하라.
