# OpenCode AgentOps Continuous v2 — 심층 검토 보고서

> 작성: Claude Sonnet 4.6 (claude.ai) · 대상: `CLAUDE_REVIEW_AGENTOPS_v2_LIGHT.zip` 전체 코드 직접 리딩 기반 분석
> 목적: 이 문서를 **Claude Opus에게 최종 검토를 맡기기 위한 입력 자료**로 사용. 따라서 1부는 OpenCode 공식 사용법을 Opus가 별도로 재검색하지 않아도 되도록 충분히 정확하고 자세하게 정리했고, 2부는 v2 코드/설계에 대한 구체적 결함과 수정안이다.
> 검증 방법: opencode.ai/docs (공식 문서, 2026-06-24~28 갱신본) 직접 fetch + `INSTALL_OPENCODE_AGENTOPS_CONTINUOUS_v2.py.txt` 내부 `FILES` dict를 Python으로 안전 추출하여 35개 생성 파일 전체 원문 검사 + `agentops.py` 전체 로직 라인 단위 분석.

---

# 0. 문서 구조

1부. OpenCode 공식 사용법 레퍼런스 (Opus가 신뢰하고 바로 쓸 수 있는 기준점)
2부. v2 심층 검토 (요청하신 13개 섹션 형식)

---

# 1부. OpenCode 공식 사용법 레퍼런스

## 1.1 Tools (공식: `/docs/tools/`)

OpenCode의 built-in tool 목록은 다음과 같다. **`patch`라는 이름의 tool은 존재하지 않는다.** 공식 명칭은 `apply_patch`다.

| Tool 이름(공식) | 역할 | 통제 permission 키 |
|---|---|---|
| `bash` | 셸 명령 실행 | `bash` |
| `read` | 파일 읽기(라인 범위 지원) | `read` |
| `grep` | ripgrep 기반 정규식 검색 | `grep` |
| `glob` | 패턴 기반 파일 탐색 | `glob` |
| `edit` | 정확한 문자열 치환 수정 | `edit` |
| `write` | 신규 생성/덮어쓰기 | `edit` |
| `apply_patch` | 패치/diff 적용 (**"patch" 아님**) | `edit` |
| `lsp` (experimental) | LSP 연동, `OPENCODE_EXPERIMENTAL_LSP_TOOL=true` 필요 | `lsp` |
| `skill` | SKILL.md 로드 | `skill` |
| `todowrite` | 작업 todo 리스트 관리, subagent는 기본 비활성 | `todowrite` |
| `webfetch` | URL fetch | `webfetch` |
| `websearch` | Exa 기반 검색, `OPENCODE_ENABLE_EXA=1` 필요 | `websearch` |
| `question` | 사용자에게 선택형 질문 | `question` |

**확실한 공식 사실 (그대로 인용 가능)**:
> "The `write` tool is controlled by the `edit` permission, which covers all file modifications (`edit`, `write`, `apply_patch`)."

즉 `write`/`apply_patch`가 `edit` permission으로 통제된다는 v2의 이해는 **틀리지 않았다.** 다만 tool 이름 자체를 `patch`로 잘못 쓰고 있는 게 문제다(아래 2부에서 상세).

`tool.execute.before/after` 훅에서는 `input.tool === "apply_patch"`로 체크해야 하며 `"patch"`가 아니다. `apply_patch`는 `output.args.patchText`를 쓰고 `filePath`가 아니다.

## 1.2 Agents (공식: `/docs/agents/`)

### 구조
- 파일 위치: 프로젝트별 `.opencode/agents/*.md`, 전역 `~/.config/opencode/agents/`.
- 파일명 = agent 이름. (`review.md` → `review` agent)
- JSON(`opencode.json`의 `agent` 필드)으로도 동일하게 정의 가능. **Markdown과 JSON 둘 다 같은 agent명을 정의하면 어떻게 병합/우선되는지는 공식 문서에 명시되어 있지 않다 (불확실).**

### Frontmatter 정식 문법
```yaml
---
description: ...        # 필수
mode: primary | subagent | all   # 생략 시 기본값 all
model: provider/model-id
temperature: 0.0~1.0
steps: 5                 # 구 maxSteps는 deprecated
disable: true
hidden: true              # subagent 전용, @autocomplete에서만 숨김(Task 호출은 가능)
top_p: 0.9
color: "#ff6b6b" | primary|secondary|accent|success|warning|error|info
permission:
  read: allow|ask|deny
  edit: allow|ask|deny
  bash: allow|ask|deny | { "*": ask, "git *": allow }
  task:
    "*": deny
    "orchestrator-*": allow
---
(본문 = system prompt)
```

### `mode: primary` vs `mode: subagent`
- **Primary**: Tab 키로 전환하는 메인 대화 에이전트. 빌트인 `build`, `plan`.
- **Subagent**: 직접 대화 대상이 아니며 (a) primary agent가 **Task tool**로 호출, (b) 사용자가 `@mention`으로 수동 호출. 빌트인 `general`(전체 권한, 단 todo 제외, "복수 작업을 병렬로 실행하는 데 사용"), `explore`(읽기 전용), `scout`(읍기 전용, 외부 의존성/문서 조사 전용).
- 숨김 시스템 primary agent로 `compaction`/`title`/`summary`도 존재(UI 비노출, 자동 실행만).

**Subagent 실행 모델에 대한 정확한 이해 (중요)**: subagent 호출은 "동시 멀티스레드 실행"이 보장된다고 공식 문서가 명시하지는 않는다. 공식적으로 확인되는 것은 Task tool 호출 시 **child session**이 생성되고, `session_child_first/cycle/parent` 키바인드로 부모-자식 세션 간 이동이 가능하다는 점뿐이다. `general` agent 설명에 "Use this to run multiple units of work in parallel"라는 표현이 있어 병렬성을 암시하지만, 이것이 OS 레벨 동시성인지 다수의 child session을 순차/비동기로 위임하는 구조인지는 **공식 문서에서 확인 불가**. AgentOps 설계 시 "진짜 병렬 실행이 보장된다"고 가정하면 위험하다.

### `tools:` 필드는 **deprecated**
공식 문서 원문:
> "`tools` is **deprecated**. Prefer the agent's `permission` field for new configs, updates and more fine-grained control."

레거시 동작 방식: agent의 `tools:` 블록에서 `true`는 `{"*": "allow"}` permission, `false`는 `{"*": "deny"}` permission과 동치. **deprecated이지만 동작은 한다** — 즉, 키 이름이 실존하는 tool 이름과 일치해야만 의미가 있다. 존재하지 않는 tool 이름(`patch`)을 키로 넣으면 그냥 무시되는 dead key가 된다.

### `permission` (agent 레벨)
허용 키와 매핑 tool:

| 키 | 게이팅 대상 |
|---|---|
| `read` | `read` |
| `edit` | `write`, `edit`, `apply_patch` |
| `glob` | `glob` |
| `grep` | `grep` |
| `list` | `list` |
| `bash` | `bash` |
| `task` | `task`(subagent 호출) |
| `external_directory` | 워크트리 밖 경로 접근 모든 tool |
| `todowrite` | `todowrite`, `todoread` |
| `webfetch` / `websearch` / `lsp` / `skill` / `question` | 동명 tool |
| `doom_loop` | 동일 tool call 3회 반복 시 |

값: `"allow" | "ask" | "deny"`, 또는 glob 패턴 객체(`{ "git push": "ask", "git *": "allow" }`)로 세분화. **마지막 매칭 규칙이 우선**(last-match-wins). 글로벌 설정과 agent 설정이 머지되며 agent 쪽이 우선.

### `permission.task` (subagent 호출 제어)
```yaml
permission:
  task:
    "*": deny
    "orchestrator-*": allow
    "code-reviewer": ask
```
- `deny`로 설정되면 해당 subagent가 **Task tool 설명 자체에서 제거**되어 모델이 시도조차 못 함.
- **공식 명시된 우회 경로**: "Users can always invoke any subagent directly via the `@` autocomplete menu, even if the agent's task permissions would deny it." 즉 `permission.task`는 **모델의 자동 호출만 막을 뿐, 사용자가 `@subagent명`으로 직접 호출하는 것은 절대 막지 못한다.** 보안/안전 설계에서 이 한계를 반드시 인지해야 함.

### `hidden: true`
`@` 자동완성 메뉴에서만 숨김. Task tool을 통한 모델의 프로그래매틱 호출은 여전히 가능. subagent에만 적용.

## 1.3 Commands (공식: `/docs/commands/`)

- 위치: `.opencode/commands/*.md` (project), `~/.config/opencode/commands/` (global). **파일명 = 슬래시 명령 이름** (1:1 매핑, `test.md` → `/test`).
- JSON으로도 `command` 필드에 정의 가능, 이 경우 `template` 필드가 필수.

### Frontmatter
```yaml
---
description: ...
agent: build          # 선택. 미지정 시 "현재 agent" 사용
model: provider/model-id
subtask: true|false   # 선택
---
(본문 = 프롬프트 템플릿)
```

### `agent:` 필드의 실제 동작 (중요, 공식 명시)
> "If this is a subagent the command will trigger a subagent invocation by default. To disable this behavior, set `subtask` to `false`."

즉:
- `agent:`가 `mode: subagent`인 agent를 가리키면 → **기본적으로 child session(subtask) 호출이 트리거**된다. `subtask: false`로 끌 수 있다.
- `agent:`가 `mode: primary`인 agent를 가리키면 → 그냥 그 agent로 전환되어 메인 컨텍스트에서 실행된다(자식 세션 안 만듦).
- `subtask: true`를 명시하면, agent가 `mode: primary`여도 **강제로 subagent처럼(child session으로) 동작**하게 만들 수 있다 — "부모 컨텍스트 오염 방지" 목적.

### 플레이스홀더
- `$ARGUMENTS` — 전체 인자 문자열.
- `$1`, `$2`, `$3` ... — 위치 기반 개별 인자.
- `` !`command` `` — bash 실행 결과를 프롬프트에 삽입.
- `@filename` — 파일 내용 자동 삽입.

## 1.4 Config 스키마 (공식: `/docs/config/`)

### 로드 우선순위 (낮음→높음, **병합** 방식, 충돌 키만 override)
Remote(`.well-known/opencode`) → Global(`~/.config/opencode/opencode.json`) → Custom(`OPENCODE_CONFIG` env) → Project(`opencode.json`) → `.opencode/` 디렉터리 → Inline(`OPENCODE_CONFIG_CONTENT`) → Managed 파일(OS별 admin 경로) → macOS `.mobileconfig`(MDM, 최우선).

### `instructions`
```json
{ "instructions": ["CONTRIBUTING.md", "docs/guidelines.md", ".cursor/rules/*.md"] }
```
경로/glob 배열. **공식 문서는 instructions가 compaction 이후에도 유지되는지 명시적으로 설명하지 않는다 (불확실 — Opus 검토 시 별도 검증 필요).**

### `permission`
```json
{ "permission": { "edit": "deny", "bash": "ask", "webfetch": "allow" } }
```
와일드카드 `*`(0개 이상), `?`(1개) 지원. **기본값**: 대부분 `"allow"`. `doom_loop`/`external_directory`만 기본 `"ask"`. `read`는 `"allow"`이나 `*.env`류는 기본 `"deny"`.

### `watcher.ignore`
```json
{ "watcher": { "ignore": ["node_modules/**", "dist/**", ".git/**"] } }
```
glob 배열, 파일 워처 무시 패턴.

### `compaction`
```json
{ "compaction": { "auto": true, "prune": false, "reserved": 10000 } }
```
- `auto` (기본 `true`): 컨텍스트가 찰 때 자동 압축.
- `prune` (기본 `false`): 오래된 tool output 제거.
- `reserved`: 압축용 토큰 버퍼. **모델 context window 크기에 비례해서 설정해야 하며 고정값을 모든 모델에 동일 적용하면 비효율적** — 공식 문서가 권장값을 제시하지 않으므로 환경(로컬 모델의 실제 context window)에 맞춰 산정해야 함.

### Agent 정의 충돌 가능성
공식 문서는 `opencode.json`의 `agent` 필드와 `.opencode/agents/*.md` 둘 다 같은 이름의 agent를 정의할 수 있다고만 설명하며, **두 군데서 동일 이름을 정의했을 때의 병합/우선순위 규칙은 명시되어 있지 않다.** 실무적으로는 혼란을 피하기 위해 "한 agent는 한 곳에서만 정의"를 권장.

## 1.5 Permissions 상세 (공식: `/docs/permissions/`)

- `"allow" | "ask" | "deny"` 세 가지.
- 객체 문법으로 세분화 가능, **마지막 매칭 규칙이 우선** (catch-all `"*"`을 먼저 쓰고 구체 규칙을 뒤에 쓰는 게 정석).
- `external_directory`: 워크트리 밖 경로 접근 시 필요. `~`/`$HOME` 확장은 패턴 표기에만 영향, 그것만으로 외부 경로가 자동 허용되지는 않음 — 별도 `external_directory` 룰 필요.
- `"ask"`가 뜨면 사용자는 `once`(이번만) / `always`(세션 동안 패턴 일치 자동승인) / `reject` 중 선택.
- 주의: Permissions 문서 원문에는 구버전 표현으로 "`edit` — all file modifications (covers `edit`, `write`, `patch`)"라는 문구가 남아있어, Tools 문서가 말하는 정식 tool명 `apply_patch`와 표기가 다르다 — **실제 tool 이름은 `apply_patch`이며, "patch"는 OpenCode 공식 문서 내부에서도 구버전 잔존 표현일 뿐 실제 tool명이 아니다.**

## 1.6 Compaction / Context (공식 + 공식 plugin 훅)

- 자동 compaction이 가능하다 (`compaction.auto: true` 기본값). 이를 수행하는 것은 숨김 시스템 `compaction` agent.
- **공식적으로 존재하는 유일한 "compact 직전 개입 지점"**: plugin의 `experimental.session.compacting` 훅.
```ts
export const CustomCompactionPlugin: Plugin = async (ctx) => {
  return {
    "experimental.session.compacting": async (input, output) => {
      output.prompt = `...완전히 교체된 compaction 프롬프트...`
    },
  }
}
```
`output.prompt`를 설정하면 기본 compaction 프롬프트를 완전히 대체할 수 있다. 이 훅이 v2/v3 설계에서 가장 중요한 활용 지점이다 (2부에서 상세).
- **"compact 후 모델이 특정 파일을 강제로 먼저 읽게 하는" 공식 기능은 존재하지 않는다.** `instructions` 파일, `AGENTS.md` 텍스트 지시, command 모두 "모델이 따르기를 기대하는" 수준이며, 강제 메커니즘이 아니다. 유일한 실질적 강제 지점은 위 plugin 훅으로 compaction summary 프롬프트 자체를 조작하는 것.
- `experimental.*` 네임스페이스이므로 공식적으로 "안정성 보장 없음"이 명시되어 있다 — v3에서 사용하더라도 버전 업그레이드 시 동작이 바뀔 수 있음을 전제해야 함.

---

# 2부. AgentOps Continuous v2 심층 검토

## 1. 총평

v2는 "약한 로컬 모델이 실패해도 운영을 지속한다"는 목표에 대해 **상태 파일 기반 골격(skeleton)은 합리적으로 잡았지만, 실제로 "복구"나 "지속 실행"을 수행하는 로직은 거의 없다.** `agentops.py`를 전부 읽어본 결과, 이 스크립트는 본질적으로 **"마크다운/JSON 리포트 생성기"**다. 실패 분류(`classify_failure`)는 단순 문자열 매칭이고, self-heal은 "무엇을 해야 하는지 적힌 텍스트"만 만들고 실제로 아무것도 고치지 않으며, `run-until-stop`은 30초마다 상태 파일 타임스탬프만 갱신하는 빈 루프다. 즉, 사용자가 `01_CONTEXT_SUMMARY.md`에서 직접 인정한 "v2는 skeleton"이라는 평가는 **정확하다.** 구조 설계 의도(역할 분리, stop-file 기반 지속, compact handoff)는 옳은 방향이지만, 구현은 그 의도를 실제로 달성하지 못한다.

또한 OpenCode 공식 문법 측면에서 **`patch`라는 존재하지 않는 tool 이름을 모든 agent frontmatter와 룰 문서에 일관되게 사용**하고 있어, 의도한 권한 제어(특히 read-only 역할 agent들이 패치 적용을 막으려는 의도)가 실제로는 작동하지 않을 가능성이 있다. 이는 단순 오타 수준이 아니라 **보안/안전 경계 설계의 실효성 자체에 영향을 주는 결함**이다.

## 2. 치명적 문제 / 반드시 고칠 것

1. **`patch` tool은 존재하지 않는다.** 공식 tool 이름은 `apply_patch`다. 영향받는 파일: `agent_ops/AGENTOPS_RULES.md`("tools such as ... `patch`, and `todowrite`", "`write` and `patch` are controlled by `edit` permission"), `.opencode/agents/agentops-supervisor.md`(`tools: patch: true`), `agentops-doctor.md`/`agentops-failure-analyst.md`/`agentops-explorer.md`/`agentops-verifier.md`/`agentops-safety.md`(`tools: patch: false`), `agentops-repair.md`(`tools: patch: true`), `agentops-reporter.md`/`agentops-memory-curator.md`(`tools: patch: false`). **"read-only여야 하는 7개 subagent가 patch:false를 줬지만, OpenCode가 인식하는 tool은 `apply_patch`이므로 이 deny가 실제로 해당 tool에 적용되지 않을 위험이 있다.** (`tools:` 필드 자체도 deprecated이므로 영향이 제한적일 수 있으나, 이름이 틀렸다는 사실 자체가 설계자의 정신모델이 틀렸다는 신호이며 v3에서 `permission.edit`로 전환하지 않으면 동일한 착오가 반복된다.)

2. **`tools:` 필드는 전부 deprecated 문법.** 9개 agent .md 전부가 `tools:` 블록(boolean)을 쓴다. 공식 권장은 `permission:` 필드. v3에서는 전부 `permission:` 객체로 전환해야 하며, 그 과정에서 위 1번 문제도 자동 해결된다(`apply_patch`가 아니라 `edit` permission 키 하나로 write/edit/apply_patch가 통합 통제되므로 tool명 오타 문제 자체가 사라짐).

3. **`agent_ops/policies/DANGEROUS_ACTIONS.txt`, `ALLOWED_ACTIONS.txt`는 생성되지만 어디에서도 읽히지 않는 죽은 파일(dead file)이다.** `agentops.py` 전체(789라인)를 grep한 결과 이 두 파일을 `open`/`read_text`하는 코드가 전혀 없다. 즉, "위험 버튼 차단"은 현재 **순수 자연어 prompt-level 안전장치뿐**이고, 코드 레벨 enforcement가 전무하다. 이는 사용자가 가장 우려하는 전제("로컬 약한 모델은 자주 실패한다")와 정면으로 충돌하는 설계 공백이다 — 안전이 가장 필요한 영역(포털 자동화, 위험 클릭 차단)에 가장 약한 방어(모델의 자체 판단)만 있다.

4. **`run-until-stop`은 실질적으로 아무 작업도 하지 않는 빈 루프다.** `continue_once()`는 `ACTIVE_TASK.json`의 `next_action` 텍스트 필드만 갱신할 뿐, 실제 LLM 호출/task 실행이 전혀 없다. `/agentrun` 명령이 모델에게 "Use actual bash tool: python agent_ops/agentops.py run-until-stop"을 실행하라고 지시하는데, 이는 **OpenCode의 bash tool 안에서 무한루프(`while True: ... time.sleep(30)`)를 실행하라는 뜻**이며, bash tool이 응답을 영원히 기다리게 되어 **OpenCode 세션/UI가 블로킹될 가능성이 매우 높다.** command 본문에 "If it blocks the UI, run RUN_AGENTOPS_CONTINUOUS.bat in a separate CMD window"라는 사후 안내가 있지만, 이는 모델이 처음에 잘못된 명령을 실행한 뒤에야 발견되는 사후 대응이다. **v3에서는 OpenCode의 bash tool 안에서 무한루프/장기 블로킹 명령을 절대 실행하지 않도록 룰을 바꿔야 한다.**

5. **`question: deny` 전역 설정과 안전 정책의 모순.** `agentops-supervisor`에 `question: deny`를 걸어 "계속 진행"을 보장하려 했지만, 동시에 `agentops-safety` 서브에이전트의 역할은 "위험 버튼 차단... unless explicitly instructed"다. 위험한 액션 직전에 사용자 확인이 필요한 시나리오가 생겨도 supervisor는 질문 자체를 할 수 없는 구조다. "계속 진행"과 "위험 시 확인"은 같은 agent에 공존할 수 없는 정책이므로, 둘을 분리해야 한다(아래 7번 권고 참조).

6. **failure type 12개 중 4개가 미구현.** 검토 prompt(`00_REVIEW_PROMPT_FOR_CLAUDE.md`)에 나열된 `NO_DATA`, `REPEATED_FAILURE`, `SESSION_EXPIRED`, `RISKY_ACTION_BLOCKED`는 실제 `classify_failure()` 함수(agentops.py)에 구현되어 있지 않다. **특히 `REPEATED_FAILURE` 누락이 가장 심각하다** — 동일 실패가 반복되는지 감지하는 로직이 전혀 없어서, `selfheal`이 똑같은 실패에 대해 매번 동일한(무력한) 계획만 반복 생성할 수 있고, 진짜 무한 루프(자기치유가 자기치유를 호출)를 막을 장치가 없다.

7. **opencode.json에서 agent를 JSON과 Markdown 양쪽에 정의.** `merge_opencode()`가 `cfg["agent"]["agentops-supervisor"] = {...}`를 설정하는데, 동시에 `.opencode/agents/agentops-supervisor.md`도 같은 이름으로 존재한다. 공식 문서는 이 충돌 시 병합/우선순위 규칙을 명시하지 않는다(1부 1.4 참조) — **불확실성이 있는 상태에서 의도적으로 이중 정의를 만든 것은 위험.** v3에서는 Markdown 단일 정의로 통일하고 `opencode.json`의 `agent` 블록은 제거해야 한다.

## 3. OpenCode 공식 호환성 문제 (파일별 정확한 수정안)

### `agent_ops/AGENTOPS_RULES.md`
- 원문: `"OpenCode provides real tools such as bash, read, grep, glob, edit, write, patch, and todowrite"` / `"write and patch are controlled by edit permission"`
- 수정: `patch` → `apply_patch`로 교체. (참고: `write`/`apply_patch`가 `edit` permission으로 통제된다는 설명 자체는 공식과 일치하므로 그대로 유지)

### `.opencode/agents/*.md` 9개 전체
- 현재: `tools:` 블록(boolean) 사용, `patch:` 키 사용.
- 수정 (예: `agentops-doctor.md`):
```yaml
---
description: Environment diagnosis specialist
mode: subagent
permission:
  read: allow
  grep: allow
  glob: allow
  edit: deny
  bash:
    "*": ask
    "python *": allow
    "where *": allow
  task: deny
---
```
- 모든 `tools:` 블록 → `permission:` 블록으로 전환. `edit: true/false` 한 줄이 `write`+`edit`+`apply_patch`를 동시에 통제하므로 `patch:` 키는 삭제(어차피 무의미).
- **`bash: true`를 단순 boolean으로 주는 모든 read-only agent(doctor/explorer/verifier/reporter/memory-curator)는 사실상 "read-only"가 아니다.** bash는 `del`, 리디렉션(`>`) 등으로 파일을 변경/삭제할 수 있는 만능 명령이다. "읍기 전용"이라는 의도를 실제로 강제하려면 bash를 세분화된 패턴(`{"*": "ask", "python -m py_compile *": "allow", "del *": "deny", "rm *": "deny"}`)으로 제한해야 한다.

### `.opencode/agents/agentops-supervisor.md`
- `permission.task` 구조(`{"*": deny, "agentops-*": allow}`)는 **공식 문법과 정확히 일치한다.** 좋은 점으로 유지.
- 다만 supervisor 자체에 `edit: true`/`write: true`/`apply_patch`(구 `patch: true`)를 전부 열어둔 것은 아키텍처 의도("수정은 repair agent만")와 모순된다 → `permission.edit: deny`로 바꾸고 모든 파일 수정은 `agentops-repair`에게 task로 위임하도록 강제해야 함.
- `question: deny`는 위 치명적 문제 5번 참조.

### `.opencode/commands/*.md`
- frontmatter 문법(`description`, `agent:`) 자체는 공식과 일치.
- 단, `/doctor`, `/selfheal`, `/verify`, `/memorycheck`, `/report`는 `agent:`에 **subagent**(`agentops-doctor`, `agentops-failure-analyst`, `agentops-verifier`, `agentops-memory-curator`, `agentops-reporter`)를 지정하므로, 공식 동작상 **기본적으로 child session(subtask) 호출이 트리거된다.** 이게 의도된 것인지 frontmatter에 명시가 없다 — 의도라면 `subtask: true`를 명시해 명확히 하고, 메인 컨텍스트에서 직접 실행을 원한다면 `subtask: false`를 명시해야 한다. 현재는 "기본값에 우연히 의존"하는 상태.
- **`/selfheal` command 본문의 치명적 불일치**: 본문은 "apply safest recovery"(복구를 적용하라)를 지시하지만, 지정된 agent `agentops-failure-analyst`는 frontmatter에서 `edit: false, write: false, bash: false`(읍기 전용)로 정의되어 있다. **이 agent는 절대 복구를 "적용"할 수 없다.** command 본문과 agent 권한이 서로 모순된다. 수정안: `/selfheal` 본문을 "분류 후 `agentops-repair`에게 위임"으로 바꾸거나, command를 2단계로 분리(`/selfheal-plan`은 failure-analyst, `/selfheal-apply`는 repair).
- `$ARGUMENTS` 사용(`goal.md`)은 공식 문법과 일치.

### `opencode.json` 머지 로직 (`merge_opencode()` in installer)
- `instructions` 배열 추가는 문법상 맞음. 다만 `.agent-memory/ACTIVE_MEMORY.md`, `ERROR_PATTERNS.md`, `LESSONS_LEARNED.md` 3개를 instructions에 영구 등록하는 것은 — 이 파일들이 append-only로 계속 자라난다는 점을 고려하면(`add_lesson()`이 무한정 append), **장기적으로 시스템 프롬프트 크기가 계속 증가해 오히려 컨텍스트 압박/컴팩션 유발 빈도를 높이는 역설**이 생길 수 있다. v3에서는 이 파일들에 크기 상한(예: 최근 N개 lesson만 유지, 오래된 건 별도 아카이브로 이동)을 두어야 한다.
- `compaction.reserved = 12000` 고정값은 "내부 LLM이 GPT/Claude보다 약하고, Qwen/EXAONE 계열"이라는 전제와 맞물려 검증이 필요하다 — 로컬 모델의 실제 context window가 32K 수준이라면 12000 reserved는 가용 작업 영역을 과도하게 줄일 수 있다. 모델별로 가변 설정해야 한다.
- `agent.agentops-supervisor`를 JSON에도 `setdefault`로 추가 — 위 치명적 문제 7번 참조, markdown 정의와 충돌 가능성.
- `permission` 전역에 `webfetch: deny, websearch: deny`를 건 것은 "외부 다운로드 금지" 요구사항과 정확히 일치하는 좋은 설계.

## 4. 아키텍처 문제

- **"분석은 병렬, 수정은 단일 repair agent"라는 원칙을 supervisor 자신이 위반할 수 있는 권한 구조.** supervisor가 자기 권한으로 직접 edit/write를 할 수 있는 한, repair agent를 거치도록 강제할 방법이 없다(시스템 프롬프트의 "Use specialist subagents aggressively"라는 자연어 권고뿐). 약한 모델일수록 권고를 무시하고 직접 고치려 들 가능성이 높다 — **권한(permission)으로 강제해야지 프롬프트로 설득해서는 안 된다.**
- **동시성/파일 충돌 방지 장치가 전혀 없다.** `ACTIVE_TASK.json`, `CHECKPOINT.json` 등은 여러 subagent가 동시에 읍고 쓸 수 있는데, lock 파일이나 원자적 쓰기(temp 파일 후 rename) 로직이 없다. "분석은 병렬"이라는 설계를 실제로 채택한다면 레이스 컨디션이 발생할 수 있다. 그러나 1부에서 다뤘듯 OpenCode subagent의 "진짜 동시성"은 공식적으로 보장되지 않으므로, 차라리 **"순차 위임 + 락 파일"**로 안전하게 설계하는 게 현실적이다.
- **task executor가 사실상 없다.** `agentops.py`에는 사내 LLM API를 직접 호출하는 코드가 전혀 없다. 검토 prompt가 질문한 "사내 LLM API를 직접 호출하는 Python orchestrator가 필요한가?"에 대한 답은 명확히 **"필요하다"** — 현재 v2는 OpenCode 자신의 LLM 호출에 전적으로 의존하는데, OpenCode 세션이 bash tool 안에서 무한루프를 돌릴 수 없다는 제약(위 4번 치명적 문제) 때문에, "OpenCode를 꺼도 계속 진행"이라는 목표는 **OpenCode 외부의 별도 프로세스(Python orchestrator 또는 Windows 작업 스케줄러)** 없이는 원천적으로 달성 불가능하다.

## 5. v2에서 제거하거나 단순화할 것

- `run_until_stop()`의 `while True` 루프를 **OpenCode bash tool 안에서 직접 실행하는 패턴 자체를 제거.** command(`/agentrun`)에서 이 함수를 추천하는 문구를 삭제하고, 대신 외부 실행(스케줄러/별도 cmd)만 안내.
- `agentops-reporter`, `agentops-memory-curator`에 부여된 `bash: true`(boolean) — 이들의 실제 필요 작업(`agent_ops/agentops.py memorycheck` 등 고정 명령 실행)은 매우 제한적이므로, `bash`를 boolean이 아니라 구체적 명령 화이트리스트로 좁혀야 한다.
- `agent_ops/policies/DANGEROUS_ACTIONS.txt`/`ALLOWED_ACTIONS.txt` — 코드가 안 읍는다면 차라리 v2에서는 제거하고, v3에서 실제로 이 파일을 읍어서 클릭 전 검사하는 코드와 함께 재도입하는 게 낫다(현재는 "있어 보이지만 작동 안 하는" 가짜 안전장치라 오히려 더 위험할 수 있음 — 사용자가 "안전장치가 있다"고 오인할 수 있음).
- `tools:` 키 전부 제거 → `permission:`으로 전면 교체(중복 작업 제거).

## 6. v3에서 반드시 추가할 것

1. **실제 task executor.** Python에서 사내 LLM API(OpenAI-compatible)를 직접 호출해 `TASK_QUEUE.jsonl`을 소비하는 별도 프로세스. OpenCode 세션과는 독립적으로 동작해야 "OpenCode를 꺼도 계속" 요구사항을 만족할 수 있다.
2. **`experimental.session.compacting` 플러그인 훅 활용.** 현재 v2는 이 훅을 전혀 쓰지 않는다. 이게 1부에서 설명한 "compact 직전 개입 가능한 유일한 공식 지점"이므로, v3에서 `.opencode/plugins/compaction-handoff.ts`를 만들어 `output.prompt`에 `COMPACT_HANDOFF.md` 내용을 강제로 주입해야 한다. 현재 방식(AGENTS.md/instructions에 "compact 후 읍어라"라고 적어두는 것)은 강제력이 없다.
3. **`REPEATED_FAILURE`, `SESSION_EXPIRED`, `RISKY_ACTION_BLOCKED`, `NO_DATA` failure type 구현.** 특히 `REPEATED_FAILURE`는 `failure_log.jsonl`에서 최근 N건의 `type`이 동일한지 체크하는 단순 로직으로도 충분히 구현 가능.
4. **위험 액션 코드 레벨 게이트.** `DANGEROUS_ACTIONS.txt`를 실제로 읍어서, 포털 자동화 plugin이 클릭 직전 버튼 텍스트/aria-label과 매칭해 차단하는 Python 함수.
5. **safe-write의 검증 확장.** 현재는 `.py`만 `py_compile` 체크. `.json`은 `json.loads` 검증, `.md`는 최소 UTF-8 디코딩 검증을 추가해야 한다.
6. **파일 잠금(lock) 메커니즘.** `ACTIVE_TASK.json` 등 공유 상태 파일에 대해 최소한 "쓰기 전 임시파일+원자적 rename" 패턴 적용.
7. **MEMORY_UPDATE_PLAN.md 2단계 구조** (8번 섹션에서 상세).

## 7. Subagent / 병렬 처리 추천 구조

- **현재 9개 subagent 분리는 과하지 않고 합리적이다.** 역할별 책임이 명확히 분리되어 있어(진단/분류/수정/탐색/보고/메모리/검증/안전) 단순화보다는 권한 강제를 정교화하는 방향이 맞다.
- **권한 재설계 원칙**: "분석 agent는 `edit: deny`를 절대적으로 유지, 수정은 오직 `agentops-repair`만, 그 결과를 `agentops-verifier`가 검증"이라는 흐름을 **agent 권한(permission)으로 강제**해야 한다. 현재는 시스템 프롬프트 문구(자연어)로만 강제하고 있어 약한 모델에게는 보장력이 낮다.
- **"진짜 병렬"을 노리지 말고 "순차 위임 체인 + 락 파일"로 설계.** OpenCode subagent의 동시성이 공식적으로 보장되지 않으므로(1부 참조), 여러 subagent를 동시에 호출하는 설계보다는 supervisor가 순서대로 task를 위임하고 각 task 사이에 `CHECKPOINT.json`을 갱신하는 직렬 파이프라인이 더 안전하고 디버깅하기 쉽다. "병렬"이 꼭 필요한 경우(예: 여러 독립 탐색 작업)는 `agentops-explorer`를 여러 번 `@mention`으로 동시에 호출하는 정도로 제한하고, 파일 수정은 항상 직렬화.

## 8. Memory lifecycle 추천 구조

- **Markdown 단독 → JSONL+Markdown 하이브리드로 전환 권장.** 현재 `LESSONS_LEARNED.md`, `ERROR_PATTERNS.md`는 freeform append이며 ID, timestamp, status(active/resolved/deprecated), 출처 failure_type, 관련 task_id 등 메타데이터가 전혀 없다. 자동 curate(분류/deprecate)를 하려면 구조화 데이터가 필수다. 권장:
  - `.agent-memory/memory_index.jsonl` — 각 줄이 `{id, type(lesson|error_pattern|preference), status, created_at, related_failure_type, text, supersedes_id}` 구조.
  - 사람이 읍는 `.md` 파일들은 이 JSONL에서 **생성(render)**하는 뷰로 전환 — 즉 진실의 원천(source of truth)은 JSONL, `.md`는 파생물.
- **자동 deprecate는 직접 수행하지 말고 2단계 구조로.** 질문에 제시된 "Memory Curator가 `MEMORY_UPDATE_PLAN.md`를 만들고 supervisor/verifier가 반영"하는 안이 정답이다. 약한 모델이 스스로 메모리를 영구 삭제/변경하는 단일 단계 구조는 위험하다(잘못된 deprecate가 영구 손실로 이어짐). Curator는 항상 "제안"만 하고, 별도 단계(또는 사람의 승인)에서 반영.
- 현재 코드는 deprecate 로직 자체가 구현되어 있지 않아(자동 deprecate가 "위험한지"를 따질 단계조차 아직 없음), v3 설계 시 처음부터 2단계 구조로 만드는 게 1단계로 만들었다가 나중에 안전장치를 추가하는 것보다 쉽다.

## 9. Restart / compact / resume 추천 schema

`CHECKPOINT.json` 권장 schema:
```json
{
  "checkpoint_id": "ckpt_xxxxxxxx",
  "updated_at": "ISO8601",
  "run_id": "run_xxxxxxxx",
  "cwd": "...",
  "active_task_id": "task_xxxxxxxx",
  "last_completed_step": "...",
  "next_step": "...",
  "stop_file_exists": false,
  "compaction_count": 0,
  "restart_count": 0
}
```

`ACTIVE_TASK.json` 권장 schema:
```json
{
  "task_id": "task_xxxxxxxx",
  "status": "pending|active|blocked|done|failed",
  "agent": "agentops-repair",
  "title": "...",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "depends_on": [],
  "retry_count": 0,
  "last_failure_type": null
}
```

`TASK_QUEUE.jsonl` 권장 schema (현재는 빈 파일로만 존재, 실제 사용 코드 없음):
```json
{"task_id":"task_001","priority":1,"status":"pending","title":"...","created_at":"...","depends_on":[]}
```

- `COMPACT_HANDOFF.md`를 `instructions`에 넣을지: **넣지 않는 것을 권장.** `instructions`는 "정적 규칙" 슬롯의 의미가 강하고, 동적으로 계속 갱신되는 휘발성 핸드오프 파일을 넣는 것은 의미상 부적절하며 사이즈 관리도 어렵다. 대신:
  1. `AGENTS.md`(매 세션 시작 시 읍히는 고정 안내문)에 "compact 후 반드시 `COMPACT_HANDOFF.md`를 읍어라"는 지시를 유지하고,
  2. **`experimental.session.compacting` 플러그인 훅**으로 compaction summary 프롬프트 자체에 `COMPACT_HANDOFF.md` 내용을 강제 주입하는 이중 방어를 구성한다(이게 1부에서 설명한 유일한 진짜 강제 지점).
- `/compactprep`을 수동으로만 호출하는 현재 방식은 compact 타이밍과 우연히 맞아떨어질 때만 효과가 있다. plugin 훅 없이는 "compact 직전 자동 실행"을 신뢰성 있게 보장할 방법이 없다는 점을 v3 설계에 명확히 반영해야 한다.

## 10. Windows 내부망 안정성 보강

- 전반적 정책(BAT ASCII-only, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, `errors="replace"`)은 합리적이며 v2에서 잘 지켜지고 있다.
- 보강점:
  1. **`python` 명령이 PATH에 없는 환경 대비책 부재.** 사내 PC에서 `py` launcher만 있거나 Anaconda 환경일 경우 BAT가 실패한다. `where python`으로 사전 체크 후 `py -3` fallback 추가 필요.
  2. **`agentops.py`의 `ROOT = Path.cwd()`가 OpenCode bash tool의 실제 cwd에 의존.** 더 안전하게는 `Path(__file__).resolve().parent.parent`(스크립트 자체 위치 기준)로 프로젝트 루트를 고정하는 게 cwd가 예상과 다를 때의 오동작을 막는다.
  3. **경로 공백/한글 디렉터리명 대비**는 BAT의 `"%~dp0..."` 인용은 되어 있으나, `agentops.py` 내부에서 `subprocess.run` 호출 시 인자를 리스트로 전달하고 있어(쉘 문자열 결합 아님) 이 부분은 안전하게 잘 되어 있다.

## 11. Portal automation plugin 설계 제안

- Chrome attach doctor는 현재처럼 `agent_ops` 공통(`doctor()` 함수)에 두는 게 맞다 — Chrome 9222 체크는 포털 전용 기능이 아니라 환경 진단의 일부이기 때문.
- **safe click classifier**는 반드시 코드 레벨로 구현(현재는 코드가 없는 dead policy 파일 상태). 권장 구조:
  - `portal_research/policies/click_gate.py`: 클릭 대상 텍스트/aria-label을 `DANGEROUS_ACTIONS.txt` 키워드와 매칭 → 매칭되면 자동 차단 + `BLOCKERS.md`에 기록 + 사용자 확인 필요 표시.
  - selector 저장 schema: `{"selector": "...", "label": "...", "page_url": "...", "risk": "safe|dangerous|unknown", "last_verified": "..."}` 형태의 JSONL.
  - screenshot/html snapshot: 위험 액션 직전/직후에만 저장(매 스텝 저장은 디스크 부담), 파일명에 task_id+timestamp 포함.
- OTP/비밀번호/쿠키/토큰 보호: 현재 시스템 프롬프트 차원의 금지만 있음 — v3에서는 Chrome DevTools Protocol 레벨에서 쿠키/storage 접근 API 호출 자체를 plugin 코드에서 차단(허용된 API 화이트리스트 방식)하는 게 더 안전.

## 12. v3 구현 우선순위

1. `tools:` → `permission:` 전면 전환 + `patch` → `apply_patch` 명칭 수정 (전체 agent .md 9개, 즉시 적용 가능, 리스크 거의 없음)
2. `/selfheal` command와 `agentops-failure-analyst` 권한 모순 해결 (분류/적용 단계 분리)
3. `run_until_stop`을 OpenCode bash tool에서 분리 — 외부 프로세스 전용으로 재설계, command 본문에서 직접 추천 문구 삭제
4. `REPEATED_FAILURE` 감지 로직 구현 (가장 작은 코드로 가장 큰 안전성 향상)
5. `DANGEROUS_ACTIONS.txt`를 실제로 읍는 코드 게이트 작성 (포털 plugin과 함께, 또는 임시로 agentops.py에 우선 연결)
6. `experimental.session.compacting` 플러그인으로 compact handoff 강제 주입
7. supervisor의 `edit` permission을 `deny`로 좁히고 repair agent로 수정 권한 단일화
8. Memory를 JSONL+Markdown 하이브리드로 전환, MEMORY_UPDATE_PLAN.md 2단계 구조 도입
9. 실제 task executor(Python LLM orchestrator) 설계 착수

## 13. 구체적 패치 지시사항

### `agent_ops/AGENTOPS_RULES.md`
- `patch` → `apply_patch`로 전체 치환 (2곳: tool 목록 나열, "write and patch are controlled by edit permission" 문장).

### `.opencode/agents/agentops-supervisor.md`
```yaml
---
description: Primary controller for durable continue-until-stop AgentOps workflow
mode: primary
permission:
  read: allow
  grep: allow
  glob: allow
  bash:
    "*": ask
    "python agent_ops/agentops.py *": allow
  edit: deny
  todowrite: allow
  question: deny
  task:
    "*": deny
    "agentops-*": allow
---
```
(edit을 deny로 좁히고, bash는 자체 CLI 호출만 화이트리스트 허용. 실제 파일 수정은 task로 agentops-repair에게 위임하도록 강제.)

### `.opencode/agents/agentops-doctor.md`, `agentops-failure-analyst.md`, `agentops-explorer.md`, `agentops-verifier.md`, `agentops-reporter.md`, `agentops-memory-curator.md`, `agentops-safety.md` (공통 패턴)
`tools:` 블록 전체 삭제 → `permission:` 블록으로 교체:
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
```
(agentops-repair만 `edit: allow`, `bash: allow`(또는 화이트리스트 확장)로 예외 처리)

### `.opencode/commands/selfheal.md`
```yaml
---
description: Analyze recent failure and prepare recovery plan, then delegate the fix
agent: agentops-failure-analyst
---

Execute `python agent_ops/agentops.py selfheal` to classify the latest failure and produce SELFHEAL_PLAN.md.
Read SELFHEAL_PLAN.md. Do not attempt to fix anything yourself (you are read-only).
Delegate the recommended actions to `agentops-repair` via the Task tool.
After repair, run `/verify`, then checkpoint and continue.
```

### `.opencode/commands/agentrun.md`
```yaml
---
description: Show how to run AgentOps continuously outside the OpenCode session
agent: agentops-supervisor
---

Do not run `run-until-stop` inside the OpenCode bash tool; it never returns and will block this session.

Instead, tell the user to run `RUN_AGENTOPS_CONTINUOUS.bat` in a separate CMD window, or schedule
`python agent_ops/agentops.py continue-once` via Windows Task Scheduler every N minutes.
```

### `agent_ops/agentops.py` — `classify_failure()` 함수에 추가
```python
def classify_failure(text: str) -> str:
    lower = text.lower()
    # ... 기존 로직 유지 ...
    return "UNKNOWN"

def classify_failure_with_history(text: str, recent: list) -> str:
    ftype = classify_failure(text)
    recent_types = [r.get("type") for r in recent[-3:] if isinstance(r, dict)]
    if recent_types.count(ftype) >= 2:
        return "REPEATED_FAILURE"
    return ftype
```
`log_failure()` 호출부에서 `tail_jsonl(LOGS / "failure_log.jsonl", 5)`를 먼저 읍고 `classify_failure_with_history`로 교체.

---

# 부록: Opus에게 별도 검증을 요청할 항목 (Sonnet이 확인 불가했던 부분)

1. `opencode.json`의 `agent` 필드와 `.opencode/agents/*.md`가 동일 이름을 정의했을 때 실제 OpenCode 런타임이 어떻게 병합/우선순위를 처리하는지 — 공식 문서에 명시 없음, 소스코드 레벨 확인이 필요할 수 있음.
2. OpenCode bash tool 자체에 타임아웃이 있는지(있다면 몇 초인지) — 있다면 `run-until-stop`이 OpenCode 안에서 돌아갈 때 타임아웃에 걸려 강제 종료될 뿐이라 "블로킹"보다는 "조용한 실패"가 될 수 있어 결론이 달라짐.
3. `instructions` 배열의 파일들이 compaction summary 생성 직후에도 다음 턴 시스템 프롬프트에 그대로 재주입되는지 — 공식 문서가 확정해주지 않음. 만약 재주입이 보장된다면 `COMPACT_HANDOFF.md`를 `instructions`에 넣는 게 오히려 더 신뢰성 높은 방법일 수 있어 9번 섹션의 권고가 바뀔 수 있음.
4. subagent Task 호출이 실제로 동시(parallel) 실행되는지, 순차 실행되는지 — 공식 문서 미확인, 동시성 가정 자체가 7번 섹션 권고를 좌우함.
