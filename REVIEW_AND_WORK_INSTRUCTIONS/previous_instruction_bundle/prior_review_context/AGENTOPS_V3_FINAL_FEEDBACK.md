# OpenCode AgentOps v3 Runtime — 최종 검토 피드백

> 검토: Claude Opus · 대상: `OPENCODE_AGENTOPS_V3_RUNTIME_PATCH.zip` (GPT가 Opus v2 피드백 반영해 재작성)
> 검증 방식: 52개 파일 전량 정독 + **실제 설치·실행 테스트**. 가짜 프로젝트(기존 opencode.json/AGENTS.md 보유)에 설치해 머지 안전성 확인, CLI 10종 실행, 오케스트레이터 루프·STOP·실패분류·메모리·안전분류·LLM클라이언트(mock 서버)까지 전 경로 동작 검증.

---

## 0. 한 줄 결론

**v2와 비교하면 다른 물건이다. "리포트 생성기"에서 "실제로 동작하는 런타임"으로 넘어왔다.** 내가 v2에서 지적한 P0/P1 결함은 **거의 전부 정확히 반영**됐고, 실행 테스트도 통과했다. 다만 (1) **interruption 감지가 실질적으로 작동 안 하는 버그**, (2) **맥락 보존이 "파일은 있으나 강제력이 없는" 상태**, (3) **병렬·co-growth는 아직 설계 여백**이 남아있다. 방향은 내 의도대로 잘 가고 있고, 지금은 "안 깨지게 만들기"는 끝났으니 "더 똑똑하게/함께 자라게 만들기" 단계다.

---

## 1. v2 → v3, 내 피드백이 얼마나 반영됐나 (실측 기준)

전부 코드로 확인하고 실행으로 검증했다.

| v2 지적사항 | v3 반영 | 실측 결과 |
|---|---|---|
| **P0** bash 무한루프(120초 침묵사) | ✅ `run_loop`은 외부 전용. `/agentrun`은 "OpenCode 안에서 돌리지 마라" 안내로 전면 재작성. RULES에도 명문화 | STOP 걸고 `orchestrator` 실행 → 즉시 exit 0 확인 |
| **P0** append-only 메모리를 instructions에 등록 → compaction 루프 | ✅ `merge_unique`가 `.agent-memory` 경로를 **명시적으로 필터링**. instructions엔 고정파일만 | 기존 `.agent-memory/LESSONS_LEARNED.md`가 설치 후 instructions에서 **제거됨** 확인 |
| **P0** dead safety 파일(안 읽힘) | ✅ `safety.py`가 `DANGEROUS_ACTIONS.txt`를 **실제로 읽어** 다중신호 분류 | `결재 승인 submit` → `blocked`, `상세 조회` → `safe`, 아이콘버튼 → `review_required` 확인 |
| **P0** `/selfheal` ↔ read-only agent 모순 | ✅ 2단계: analyst가 plan만, repair에게 위임. `subtask: true` 명시 | selfheal 실행 → `next_owner` 분기 확인 |
| **P0** `tools:`/`patch:` 오류 | ✅ 9개 agent 전부 `permission:`으로 전환, `patch` 단어 0 | grep 결과 잔존 0. verifier가 `scan_agents()`로 **재발 방지 자가검사**까지 |
| **P0** supervisor 수정권한 단일화 | ✅ supervisor `edit: deny`, repair만 `edit: allow` | frontmatter 확인 |
| **P0** agent JSON+MD 이중정의 | ✅ 설치 시 `cfg['agent'].pop('agentops-supervisor')` | 기존 JSON agent 제거되고 `myother`는 보존 확인 |
| **P1** REPEATED_FAILURE + 미구현 4종 | ✅ 12종 전부 구현 + history 기반 REPEATED 감지 | 같은 실패 3회 → 3번째에 `REPEATED_FAILURE` 확인 |
| **P1** 실제 task executor | ✅ `orchestrator.execute_task`가 kind별 실제 실행. `llm_plan`은 사내 LLM 호출 | doctor task 실제 실행 done, llm_plan은 mock 서버로 정상 호출 확인 |
| **P1** safe_write 검증 확장 + 원자적 쓰기 | ✅ `.py`/`.json`/UTF-8 검증 + 실패시 롤백. 전 I/O가 `atomic_write_*`(tmp+os.replace) | safe-write 경로 확인 |
| **P1** 파일 락 | ✅ `file_lock`(O_CREAT\|O_EXCL) 큐·메모리 쓰기에 적용 | 코드 확인 |
| **P1** LAST_KNOWN_GOOD | ✅ verify 통과시 `mark_last_known_good` | verify ok → 갱신 확인 |
| **P2** 메모리 JSONL source-of-truth + 2단계 | ✅ `memory.jsonl`이 진실, `.md`는 렌더뷰, `MEMORY_UPDATE_PLAN`은 제안만(자동삭제 X) | error_pattern 4건 JSONL 기록 + 뷰 렌더 + index `source_of_truth` 확인 |
| **P2** `ROOT`를 `__file__` 기준 | ✅ `Path(__file__).resolve().parents[1]` | cwd 무관 동작 확인 |
| planned/approved 구분(안전구멍) | ✅ RESUME_PLAN/COMPACT_HANDOFF에 "planned, not approved" 명문 + risk 필드 | 파일 확인 |

**정직한 평가: 반영률이 매우 높다.** GPT가 내 리뷰를 형식만 따라간 게 아니라 **의도까지** 구현했다. 특히 verifier의 `scan_agents()`(틀린 frontmatter를 스스로 잡아냄)와 safety의 `review_required` 기본값(모르는 건 일단 위험 취급)은 내가 시키지 않았는데도 "안전한 기본값" 철학을 제대로 적용한 부분이라 칭찬할 만하다.

---

## 2. 실제로 실행해보고 발견한 버그 (코드만 봐선 안 보임)

설치·실행 테스트에서 2개의 실질 결함을 찾았다. 둘 다 "있다고 적혀 있지만 실제론 작동 안 하는" 유형이라 v2의 dead-file과 같은 함정이다.

### 2.1 [버그·중요] interruption 감지가 실질적으로 절대 안 켜진다

**증상**: 강제종료(forced shutdown) 후 재개 시 "이전 작업이 중단됐다"를 감지하는 `detect_interruption()`이 — 단독 호출하면 정상 작동하지만 — **실제 사용 경로(`/status`, `/resume`)에서는 거의 항상 `False`를 반환**한다.

**근본 원인**: `cmd_status`가 이 순서로 실행된다.
```python
def cmd_status(args):
    heartbeat('status');  # ← 여기서 last_heartbeat를 "지금"으로 덮어씀
    data={..., 'interruption':detect_interruption(), ...}  # ← 그 다음에 감지 → 이미 stale 아님
```
`detect_interruption`은 `last_heartbeat`가 오래됐는지로 판단하는데, 바로 직전 `heartbeat()`가 그 값을 현재시각으로 갱신해버린다. **실측 확인**: 2020년 heartbeat를 심어두고 `detect_interruption()`을 직접 부르면 `interrupted: True, reason: stale heartbeat 204956893s`가 나오지만, `/status`를 거치면 `False`가 된다.

**더 큰 문제**: 설령 감지가 켜져도 **아무것도 그걸 소비하지 않는다**. grep 결과 `detect_interruption`은 `cmd_status`에서 화면 출력용으로만 호출되고, `resume`/`init`은 이 값으로 분기하지 않는다. RESUME_PLAN.md에 'interrupt'라는 단어는 0회 등장. 즉 **"forced shutdown 복구"는 이름만 있고 실제 복구 행동이 없다.**

**영향**: 사용자가 가장 원하는 시나리오 중 하나 — "PC 꺼졌다 켜도 중단된 작업을 알아서 이어받기" — 가 실제로는 "아무 일 없었던 것처럼" 진행된다. 중단 중 `active` 상태로 멈춘 task가 좀비로 남아도 경고가 없다.

**수정 방향**:
```python
def cmd_status(args):
    interruption = detect_interruption()   # heartbeat 호출 "전"에 먼저 감지
    heartbeat('status')
    if interruption['interrupted']:
        # ACTIVE_TASK가 active로 멈춰있으면 pending으로 되돌리고(좀비 회수)
        # CHECKPOINT.interrupted=True 기록, RESUME_PLAN 맨 위에 경고 삽입
        ...
    data = {..., 'interruption': interruption, ...}
```
그리고 `init_state`/`cmd_resume`에서도 동일하게 **감지 → 행동(좀비 task 회수 + RESUME_PLAN에 명시)** 흐름을 넣어야 "이름만 복구"를 면한다.

### 2.2 [설계 갭] orchestrator의 `manual`/`llm_plan` 외 "실제 작업"이 없다

**증상**: `execute_task`의 kind 중 실제로 외부 세계를 바꾸는 건 `llm_plan`(LLM이 텍스트 생성 → 파일로 저장)뿐이다. 나머지(doctor/verify/report/memorycheck/selfheal/safety_check)는 전부 **내부 상태 점검**이고, `manual`은 "supervisor가 처리해야 함"이라며 blocker만 남긴다.

**무슨 뜻이냐**: 무인 오케스트레이터가 큐를 돌려도, 실제로 "코드를 고치고/포털을 탐색하고/리포트를 만드는" 생산적 작업은 못 한다. `llm_plan`조차 "계획 텍스트를 파일로 쓰는" 것이지, 그 계획을 **실행**하는 닫힌 루프가 없다. 실측에서 llm_plan 태스크는 LLM 미설정 시 그냥 실패→pending 재큐만 반복했다.

이건 "버그"라기보단 **v3가 의도적으로 멈춘 지점**이다(README도 "runtime patch"라고만). 하지만 사용자 질문("나랑 함께 성장하는 구조인가")의 핵심이 여기 걸려 있어 §4에서 별도로 다룬다.

### 2.3 [사소] 기타 관찰

- `compaction.reserved`가 기존값 12000을 `setdefault`로 보존 — 동작은 맞으나, 내가 v2에서 지적한 "모델 context에 맞춰 가변" 의도는 미반영. 신규 설치 시 기본 8000은 32K 로컬모델엔 여전히 큼. **불확실**: 사내 EXAONE/Qwen의 실제 context window를 모름 → 사용자가 직접 산정 필요.
- `classify_failure`가 단순 substring 매칭이라 **오탐 여지**. 예: 정상 로그에 "save"가 있으면 안전분류에서 안 걸리지만, 실패분류의 "no data"/"login required" 등은 정상 텍스트에서도 우발 매칭 가능. 실측에서 LLM 미설정 에러가 `UNKNOWN`으로 분류됐는데, 이건 맞지만 "LLM_NOT_CONFIGURED" 같은 전용 타입이 있으면 더 정확.
- `file_lock`이 POSIX `os.open(O_EXCL)` 기반 — Windows에서도 동작하나, 프로세스가 죽으면 **lock 파일이 안 지워지고 남는다**(stale lock). timeout(10초) 후 `TimeoutError`만 던지고 stale lock 자동회수가 없다. 무인 오케스트레이터가 크래시하면 다음 실행이 락에 막힐 수 있다. → lock 파일에 pid+timestamp를 쓰고 있으니, timeout 시 "그 pid가 살아있나" 확인 후 죽었으면 강제 회수하는 로직 추가 권장.

---

## 3. 에이전트의 맥락(context) 보존 — 잘 되고 있나?

**현재 상태: "저장은 견고, 강제는 약함, 압축 개입은 0".** 세 층으로 나눠 평가한다.

### 3.1 저장 계층 (state files) — 잘 됨 ✅

`agent_ops/state/*`가 원자적 쓰기로 안전하게 유지된다. CHECKPOINT/RESUME_PLAN/COMPACT_HANDOFF가 매 checkpoint마다 갱신되고, planned/approved 구분도 들어갔다. 재시작 후 `/resume`이 RESUME_PLAN을 출력한다. **이 부분은 v2 대비 확실히 개선됐고 믿을 만하다.**

### 3.2 강제 계층 (모델이 실제로 읽게 만들기) — 약함 ⚠️

문제는 **"파일이 있다"와 "모델이 그걸 읽고 따른다"는 다르다**는 점이다. 현재 맥락 보존은 전적으로:
- AGENTS.md/RULES의 자연어 지시("compact 후 handoff 읽어라"), 그리고
- `instructions`에 등록된 고정 파일

에 의존한다. 그런데 내가 v2 리뷰에서 확인했듯, **OpenCode의 `instructions`/AGENTS.md는 compaction을 거치면 유지가 보장되지 않고**(이슈 #16960), 약한 로컬 모델은 자연어 지시를 무시할 확률이 높다. 즉 **가장 약한 모델에게 가장 중요한 순간(compaction 직후)을 자연어 지시에만 맡기고 있다.**

### 3.3 압축 개입 계층 (compaction hook) — 미구현 ❌ ← 가장 큰 빈틈

v2 리뷰에서 내가 "compact 직전 개입 가능한 유일한 공식 지점"으로 지목한 **`experimental.session.compacting` 플러그인 훅이 v3에도 없다.** `.opencode/plugins/` 폴더 자체가 없다. `/compactprep`은 여전히 "수동 호출 시 운 좋게 타이밍 맞으면" 동작하는 수준.

이게 맥락 보존의 **진짜 강제 지점**이다. 이 훅으로 compaction summary 프롬프트 자체에 COMPACT_HANDOFF.md를 강제 주입하면, 약한 모델이 "compact 후 첫 행동은 handoff 읽기"를 어길 수 없게 된다.

**권장 (P1)**: `.opencode/plugins/compaction-handoff.ts` 추가.
```ts
import { readFileSync } from "fs"
export const CompactionHandoff = async () => ({
  "experimental.session.compacting": async (input, output) => {
    let h = ""
    try { h = readFileSync("agent_ops/state/COMPACT_HANDOFF.md","utf-8") } catch {}
    output.prompt = [
      "Summarize the session. Preserve verbatim all durable state references below.",
      "After compaction, your FIRST action MUST be to read:",
      "  agent_ops/state/COMPACT_HANDOFF.md, RESUME_PLAN.md, ACTIVE_TASK.json, CHECKPOINT.json",
      "CRITICAL: items under next_step/queue are PLANNED, not approved.",
      "Do not perform any risk:review_required action without explicit user approval this session.",
      "",
      "=== DURABLE HANDOFF (inject verbatim) ===",
      h,
    ].join("\n")
  },
})
```
(주의: `experimental.*`는 버전 불안정. OpenCode 버전 핀 권장. 사내 빌드에서 이 훅이 지원되는지 **실측 필요** — 미지원이면 차선책은 AGENTS.md 최상단에 "STOP. 먼저 handoff부터 읽어라"를 두는 것.)

### 3.4 한 가지 더 — 맥락의 "압축 손실" 대비

상태파일이 계속 커지면 그 자체가 다음 compaction을 유발한다(v2의 교훈). CHECKPOINT가 `active_task`를 통째로 임베드하는데, payload가 크면 비대해진다. **권장**: CHECKPOINT는 `active_task_id`만 참조하고 전체는 큐에서 조회. RESUME_PLAN/HANDOFF에 들어가는 JSON도 핵심 필드만 추리는 게 좋다(지금은 통째 dump).

---

## 4. 나와 함께 성장하는 구조인가? (co-growth) — 가장 중요한 질문

솔직하게: **"학습의 뼈대는 깔렸지만, 학습 루프가 아직 닫히지 않았다."** 메모리가 쌓이긴 하는데, 그게 다음 행동을 실제로 바꾸는 경로가 약하다. 네 단계로 진단한다.

### 4.1 지금 되는 것 ✅

- 실패가 자동으로 `memory.jsonl`에 `error_pattern`으로 기록된다(실측 확인: 4건 누적).
- JSONL이 진실이고 .md는 렌더뷰라 구조화돼 있어 **나중에 질의·필터가 가능한 형태**다. 이건 co-growth의 좋은 토대다.
- `MEMORY_UPDATE_PLAN`으로 2단계 deprecate(제안→반영)라 잘못된 자동삭제로 기억을 날릴 위험이 낮다.
- `USER_PREFERENCES`(v2에 있던 것)처럼 사용자 성향을 담을 자리가 있다.

### 4.2 안 되는 것 — 학습 루프가 안 닫혔다 ❌

**핵심 결함: 기록된 교훈이 "다음 작업의 입력"으로 자동 주입되지 않는다.**

현재 흐름은 `실패 → 기록`에서 끝난다. 이상적 흐름은 `실패 → 기록 → 다음 유사 task 시작 시 관련 교훈을 자동으로 끌어와 프롬프트에 주입 → 같은 실수 회피`인데, 마지막 두 단계가 없다. `execute_task`의 `llm_plan`을 보면:
```python
content=chat([
  {'role':'system','content':'You are an AgentOps specialist...'},  # ← 고정 시스템 프롬프트
  {'role':'user','content':prompt}                                    # ← 메모리 주입 없음
])
```
관련 `error_pattern`이나 `lesson`을 검색해서 system 프롬프트에 넣는 코드가 없다. 즉 **3개월 전 똑같이 실패한 교훈이 memory.jsonl에 있어도, 오늘 같은 task를 할 때 그걸 안 본다.**

### 4.3 co-growth를 닫는 구체적 설계 (P1, 이게 사용자 질문의 핵심 답)

**(a) 메모리 검색 → 프롬프트 주입 (가장 중요)**
`llm_client.chat` 호출 전에 관련 메모리를 끌어오는 레이어를 둔다. 사내망이라 임베딩 모델이 없을 수 있으니 **키워드/태그 기반**으로 시작:
```python
# memory_manager.py에 추가
def recall(task_kind: str, keywords: list[str], limit: int=5) -> list[dict]:
    rows = load_memory(status='active')
    scored = []
    for r in rows:
        text = (r.get('title','')+' '+r.get('body','')).lower()
        score = sum(1 for k in keywords if k.lower() in text)
        if r.get('kind') in ('lesson','error_pattern'): score += 1  # 교훈 가중
        if r.get('priority')=='high': score += 1
        if score: scored.append((score, r))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [r for _, r in scored[:limit]]

# orchestrator.execute_task의 llm_plan 분기에서
lessons = recall(task['kind'], extract_keywords(prompt))
system = 'You are an AgentOps specialist...\n\nRELEVANT PAST LESSONS (avoid repeating these mistakes):\n' + \
         '\n'.join(f"- {l['title']}: {l['body']}" for l in lessons)
content = chat([{'role':'system','content':system},{'role':'user','content':prompt}])
```
이 한 가지가 "기록만 하는 메모리"를 "행동을 바꾸는 메모리"로 만든다. **co-growth의 핵심 스위치.**

**(b) 성공도 기억하라 (지금은 실패만 적힘)**
현재 `add_memory_event`는 실패 시에만 호출된다(`failures.log_failure`). 성공 패턴·해결책도 적어야 "이건 이렇게 하면 됐다"가 쌓인다. `mark_task_done` 시 `add_memory_event('lesson', ...)`로 성공 전략을 기록(특히 repair가 고친 방법).

**(c) 사용자 피드백을 1급 시민으로**
네가 "그거 아니야" "이렇게 해줘"라고 하면 그게 `USER_PREFERENCES` 또는 `lesson`으로 들어가는 명시적 경로가 필요하다. 예: `/remember <텍스트>` 같은 command를 추가해, 네 교정이 즉시 `add_memory_event('preference', ..., priority='high', source='user')`로 박히게. **사용자 발화가 가장 신뢰도 높은 메모리**여야 한다(`source='user'`는 검색에서 최우선 가중).

**(d) 주기적 회고(reflection)**
지금 `memorycheck`은 중복 title만 본다. 여기에 "최근 실패 N건에서 공통 패턴 추출 → 상위 교훈으로 승격" 같은 가벼운 회고를 추가하면, 개별 실패가 일반 원칙으로 자라난다. 사내 LLM에 H100을 쓸 수 있으니(비용 무관 전제), 하루 1회 `reflect` task를 큐에 넣어 LLM이 메모리를 정리·승격하게 하는 것도 현실적.

### 4.4 co-growth 성숙도 한눈에

```
[기록]      ✅ 실패 자동 기록, JSONL 구조화
[조직화]    ✅ active/resolved/deprecated, 2단계 deprecate
[회상]      ❌ ← 여기가 끊김. 기록을 다음 작업에 안 끌어옴
[주입]      ❌ ← 프롬프트에 메모리 안 들어감
[승격]      ❌ ← 개별 실패 → 일반 원칙으로 자라는 회고 없음
[사용자루프] △  자리는 있으나(USER_PREFERENCES) 명시적 입력 경로 없음
```
**[회상]+[주입] 두 개만 닫으면** co-growth가 실제로 돌기 시작한다. 나머지(승격·사용자루프)는 그 다음.

---

## 5. 병렬 에이전트 — 더 효과적으로 가능한가?

**가능하다. 그리고 v3의 현재 구조가 오히려 병렬화에 유리한 토대를 이미 깔아놨다.** 단, "어디서 병렬을 하느냐"를 정확히 나눠야 한다.

### 5.1 먼저 사실관계 (v2 리뷰에서 공식 확인)

- **OpenCode 코어의 subagent Task 호출은 순차 실행이다**(이슈 #14195: `tasks.pop()`로 하나씩). 한 응답에 Task 3개 던져도 동시 실행 안 된다.
- 따라서 **"OpenCode 세션 안에서 진짜 병렬 specialist"는 코어만으로는 불가능**. oh-my-opencode 같은 서드파티 background task 플러그인이 필요한데, 내부망 no-download라 비현실적.

### 5.2 결론: 병렬은 "외부 오케스트레이터"에서 한다 ← v3 구조의 강점

여기가 핵심이다. v3는 이미 **OpenCode와 독립된 Python 오케스트레이터**를 갖고 있고, 사내 LLM은 H100급에 비용 무관이다. 그러면 병렬의 올바른 위치는 **오케스트레이터의 큐 소비를 동시화**하는 것이다. OpenCode의 순차 제약과 무관하게, Python 레벨에서 사내 LLM을 동시 호출하면 된다.

**현재 `run_loop`은 한 번에 task 하나씩(`run_once`)** 처리한다. 이걸 병렬화하는 구체안:

```python
# orchestrator.py — 병렬 버전 (개념)
import concurrent.futures as cf

def run_loop_parallel(interval_seconds=60, max_workers=3):
    heartbeat('continuous_parallel')
    with cf.ThreadPoolExecutor(max_workers=max_workers) as pool:
        while not is_stop_requested():
            batch = get_next_independent_batch(max_workers)  # ← 핵심: 의존성 없고 파일충돌 없는 task만
            if not batch:
                time.sleep(interval); continue
            futures = {pool.submit(run_one_isolated, t): t for t in batch}
            for fut in cf.as_completed(futures):
                ...  # 결과 수집
    heartbeat('stopped')
```

### 5.3 병렬화의 3대 안전 규칙 (이게 없으면 재앙)

v3가 깔아놓은 토대 덕에 1·2는 절반 이미 됐다.

**(1) 분석은 병렬, 수정은 직렬 (file write 단일화)**
- doctor/explorer/verifier/failure-analyst/reporter처럼 **읽기전용·독립** task는 마음껏 병렬.
- repair처럼 **파일을 쓰는** task는 절대 병렬 금지 → 항상 한 번에 하나(또는 파일경로별 락).
- v3는 이미 `edit: deny`로 분석 에이전트를 읽기전용으로 강제했으니 **권한 레벨에서 이 규칙이 반쯤 보장된다**. 좋다.

**(2) 의존성 + 파일충돌 기반 배치 선택**
`get_next_task`는 이미 `depends_on`을 본다. 병렬에선 여기에 **"같은 배치 내 task들이 같은 파일을 안 건드리는가"**를 추가해야 한다. task schema에 `touches: [파일경로...]` 필드를 넣고, 배치 선택 시 touches가 겹치는 task는 같은 배치에 안 넣는다.

**(3) 락 + 원자적 쓰기 (이미 있음)**
`file_lock`과 `atomic_write_*`가 이미 있으니 동시 쓰기 레이스는 기본 방어됨. 단 §2.3의 stale lock 회수만 보강하면 된다.

### 5.4 더 야심찬 형태 — "specialist 팬아웃 → 단일 머지"

사용자가 v2 때부터 원한 "병렬 분석 후 단일 수정" 패턴의 이상적 구현:
```
supervisor가 문제 인식
  → 오케스트레이터가 동일 문제를 3개 specialist에 팬아웃 (병렬, H100이라 비용 무관)
     - failure-analyst: 원인 분류
     - explorer: 관련 코드/상태 인벤토리
     - doctor: 환경 요인
  → 3개 결과를 supervisor가 머지 → 단일 repair task 생성(touches 명시)
  → repair 1개만 파일 수정 (직렬)
  → verifier 검증 → 통과시 LAST_KNOWN_GOOD 갱신
```
이건 OpenCode 밖 오케스트레이터에서 `ThreadPoolExecutor`로 자연스럽게 구현된다. **사내 H100 + 비용무관 전제와 완벽히 맞는 패턴**이고, v3 구조에 가장 적은 추가로 얹을 수 있다.

### 5.5 병렬 요약

| 위치 | 병렬 가능? | 방법 |
|---|---|---|
| OpenCode 세션 내 subagent | ❌ (코어 순차) | 시도하지 마라. 단일 bounded task만 |
| 외부 오케스트레이터 — 읽기전용 분석 | ✅ 적극 | ThreadPoolExecutor 팬아웃 |
| 외부 오케스트레이터 — 파일 수정 | ⚠️ 직렬 | repair 단일화 + touches 락 |
| specialist 팬아웃 → 머지 → 단일 repair | ✅ 권장 | §5.4 패턴 |

**핵심: OpenCode의 순차 제약을 우회하려 애쓰지 말고, 이미 갖춘 외부 오케스트레이터에서 병렬하라.** v3는 이걸 할 준비가 거의 됐다 — `run_loop`를 배치 병렬로 바꾸고 touches 필드만 추가하면 된다.

---

## 6. v3.1 우선순위 (다음 패치)

### P0 — 버그 수정 (작동 안 하는 것을 작동하게)
1. **interruption 감지 순서 버그 수정** (§2.1). `cmd_status`/`cmd_resume`/`init_state`에서 `heartbeat()` "전에" `detect_interruption()` 호출. 그리고 감지 시 **좀비 task 회수**(active→pending) + RESUME_PLAN 최상단 경고 삽입. "이름만 복구"를 실제 복구로.
2. **stale lock 자동회수** (§2.3). `file_lock` timeout 시 lock 파일의 pid가 죽었으면 강제 회수. 무인 크래시 후 데드락 방지.

### P1 — 맥락 보존 + co-growth (방향성의 핵심)
3. **compaction 플러그인 훅** (§3.3). `.opencode/plugins/compaction-handoff.ts`로 handoff 강제 주입. 맥락 보존의 진짜 강제 지점. (사내 빌드 지원 여부 실측 후)
4. **메모리 recall→주입** (§4.3a). `memory_manager.recall()` + `llm_plan`이 관련 교훈을 system 프롬프트에 주입. **co-growth를 닫는 단 하나의 스위치.**
5. **성공도 기억** (§4.3b). `mark_task_done` 시 성공 전략을 `lesson`으로 기록.
6. **`/remember` command** (§4.3c). 사용자 교정을 즉시 `source='user', priority='high'` 메모리로.

### P2 — 병렬 + 견고성
7. **외부 오케스트레이터 배치 병렬** (§5.2~5.4). `run_loop_parallel` + task schema에 `touches` 필드. 읽기전용 분석 팬아웃, 수정은 직렬.
8. **CHECKPOINT 슬림화** (§3.4). active_task 통째 임베드 대신 id 참조.
9. **회고(reflect) task** (§4.3d). 주기적으로 실패 패턴 → 일반 원칙 승격.
10. **compaction.reserved 모델별 산정** (§2.3). 사내 모델 context window 실측 후.

### P3 — 확장
11. **LLM_NOT_CONFIGURED 전용 failure type** + classify 오탐 줄이기.
12. **portal plugin 완성** (click_gate는 safety.py에 이미 토대 있음 → CDP 쿠키/storage 화이트리스트 차단, 셀렉터 schema).

---

## 7. v3.1 검증 체크리스트 (완료 기준)

이번에 내가 실제로 돌려본 것처럼, 다음을 실행으로 확인하라:

- [ ] 2020년 heartbeat 심고 `/status` → `interrupted: True` 나오는가 (지금은 False = 버그)
- [ ] 중단된 `active` task가 재개 시 `pending`으로 회수되는가
- [ ] `recall()`이 관련 error_pattern을 끌어와 llm_plan 프롬프트에 들어가는가 (로그로 확인)
- [ ] 같은 실패를 한번 겪은 뒤, 다음 유사 task의 LLM 입력에 그 교훈이 보이는가
- [ ] `mark_task_done` 후 memory.jsonl에 `lesson`(성공)이 쌓이는가
- [ ] compaction 훅 주입 후, 강제 compaction 시 summary에 handoff가 들어가는가 (사내 빌드 지원 시)
- [ ] 병렬 배치에서 같은 파일 건드리는 task가 동시 실행 안 되는가 (touches 충돌 회피)
- [ ] 오케스트레이터 크래시 후 다음 실행이 stale lock에 안 막히는가
- [ ] (이미 통과) 설치 시 기존 opencode.json 보존 + `.agent-memory` instructions 제거 + agent 이중정의 해소
- [ ] (이미 통과) 안전분류 dangerous=blocked / safe=safe / 미지=review_required

---

## 8. 총평 — 방향은 맞다

**v2가 "골격", v3가 "작동하는 런타임"이라면, v3.1은 "함께 자라는 시스템"이어야 한다.**

GPT는 내 피드백을 형식뿐 아니라 의도까지 충실히 반영했고, 실행 테스트를 통과하는 진짜 코드를 만들었다. 안전(권한 강제, planned/approved, review_required 기본값)과 견고함(원자적 쓰기, 락, 검증, 롤백)은 이제 충분히 단단하다. "안 깨지게 만들기"는 사실상 끝났다.

남은 것은 두 가지 본질적 도약이다:
1. **맥락을 자연어 부탁이 아니라 compaction 훅으로 강제**해서, 약한 모델도 끊김 없이 이어가게.
2. **메모리를 기록 창고가 아니라 회상→주입 루프로 닫아서**, 너와의 작업이 쌓일수록 같은 실수를 덜 하고 너의 방식을 더 잘 알게.

특히 §4의 **recall→주입(P1-4)** 하나가 "나랑 함께 성장하는 구조인가"라는 네 질문의 직접적 답이다. 지금은 메모리가 쌓이기만 하고 행동을 못 바꾼다. 그 한 줄을 닫으면, 이 시스템은 비로소 너와 함께 자라기 시작한다.

병렬은 걱정 안 해도 된다 — OpenCode 안에서 억지로 하지 말고, 이미 갖춘 외부 오케스트레이터에서 하면 사내 H100과 완벽히 맞는다. 토대는 이미 거의 다 있다.

---

### 부록: 불확실성 (실측 권장)
1. 사내 OpenCode 빌드가 `experimental.session.compacting` 훅을 지원하는지 — 미지원이면 §3.3 차선책(AGENTS.md 최상단 강제문구).
2. 사내 EXAONE/Qwen의 실제 context window 크기 — `compaction.reserved` 산정에 필요.
3. 사내망에 임베딩 모델이 있는지 — 있으면 recall을 키워드가 아니라 의미검색으로 격상 가능.
4. `file_lock`의 Windows 동작 — POSIX `O_EXCL`은 Windows Python에서도 되지만, 네트워크 드라이브/망분리 환경에서의 원자성은 실측 권장.
