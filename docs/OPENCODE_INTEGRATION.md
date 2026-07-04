# OpenCode ↔ agent_ops 연동 (공식 문서 기준)

> P00-02 조사 산출물. 이 repo가 패키징하는 **OpenCode(패치된 TUI)** 와 **agent_ops(병행 CLI 런타임)** 의
> 관계를 OpenCode 공식 문서 기준으로 확정한다. 워커는 OpenCode 동작을 추측하지 말고 이 문서를 근거로 쓴다.
>
> **표기 규칙**: 각 결론에 `[확인됨]`(공식 문서 근거) / `[추정]`(문서에 없음 — 실측 필요) 태그.
> 고정 커밋 기준: `afff74eb`. 문서 스냅샷: 2026-07-04.

## 출처

| # | 항목 | 출처 URL |
|---|------|----------|
| 1 | provider 설정 | https://opencode.ai/docs/providers/ , https://opencode.ai/docs/config/ |
| 2 | tool/plugin 확장점 | https://opencode.ai/docs/plugins/ |
| 3 | 오프라인 제약 | https://opencode.ai/docs/config/ |
| 4 | permission | https://opencode.ai/docs/permissions/ |

---

## 항목 1 — provider 설정 (OpenAI 호환 endpoint 등록)

**결론 `[확인됨]`**: OpenCode는 `opencode.json`의 `provider` 블록에서 `@ai-sdk/openai-compatible`
npm 패키지를 지정해 임의의 OpenAI 호환 게이트웨이를 등록한다. LIG 사내 게이트웨이는 이 방식으로 연결한다.

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "lig-gateway": {                          // provider ID — /connect 목록에 이 ID로 노출
      "npm": "@ai-sdk/openai-compatible",
      "name": "LIG Local Gateway",
      "options": {
        "baseURL": "http://<gateway-host>/gateway/v1",   // 실제 호스트는 lig-api.env, 커밋 금지
        "apiKey": "{env:LIG_API_KEY}"                    // 환경변수 치환 — 값은 커밋 금지
      },
      "models": {
        "qwen-local": {
          "name": "Qwen (local llama.cpp)",
          "limit": { "context": 200000, "output": 65536 }
        }
      }
    }
  }
}
```

- provider ID(`lig-gateway`)는 `/connect` 진입점 및 모델 선택 UI에 그대로 노출된다. `[확인됨]`
- `apiKey`/`baseURL`은 `{env:VAR}` 치환을 지원 → **비밀 값을 config에 하드코딩하지 않는다**. `[확인됨]`
- `models.<id>.limit.context`/`limit.output` 는 토큰 한도 표시용. 실제 게이트웨이 한도와 일치시켜야 함. `[추정]`
  (문서는 필드 존재만 명시; Qwen 로컬 한도는 P00-03 실측으로 확정)

**작업 반영**: workspace `opencode.json`은 위 스켈레톤을 쓰되 host/key는 `lig-api.env`에서 env로 주입.
번들/커밋에는 `{env:...}` placeholder만 남는다.

---

## 항목 2 — tool/plugin 확장점 (agent_ops 호출 가능 여부)

**결론 `[확인됨]`**: OpenCode 플러그인은 **자체 프로세스 내부 hook**만 제공한다. 외부 에이전트 런타임을
기동/위임하는 확장점은 공식 문서에 **없다**. 따라서 **agent_ops는 OpenCode 내부 플러그인으로 이식하지 않고
별도 CLI로 병행**하는 것이 맞다 (현 노선 확정).

문서화된 hook (플러그인이 가로챌 수 있는 지점):

| hook | 시점 | agent_ops 활용 |
|------|------|----------------|
| `tool.execute.before` / `.after` | 내장 tool 실행 전/후 | 감사 로깅 훅 지점 후보 `[추정]` |
| `permission.asked` / `permission.replied` | 권한 요청/응답 | agent_ops 승인 게이트와 연동 관찰 지점 `[추정]` |
| file / session / shell hooks | 파일·세션·셸 이벤트 | — |
| 커스텀 `tool()` 헬퍼 | 동명 tool로 내장 override | 필요 시 얇은 위임 tool 작성 가능 `[추정]` |

- 플러그인은 `opencode.json`의 npm 의존성 또는 `.opencode/plugins/`에 두고 **Bun이 자동 설치**한다. `[확인됨]`
- 플러그인은 `client` SDK 핸들을 받아 OpenCode 자체 API를 호출한다. `[확인됨]`
- **외부 프로세스(예: agent_ops CLI)를 OpenCode가 오케스트레이션하는 공식 경로는 문서에 없음**. `[확인됨]`
  → agent_ops는 TUI와 **병행 실행**(사용자/런처가 각각 기동)하며, 데이터 교환은 공유 파일시스템
  (`AGENTOPS_ROOT`, 산출물 폴더)과 `plan/` 보드로 한다.

**작업 반영(권고 근거)**: "OpenCode 안에서 agent_ops를 tool로 부른다"는 설계는 문서 근거가 없으므로 채택 금지.
얇은 커스텀 `tool()` 위임은 **선택적 편의**일 뿐 필수 아님 — P0 범위 밖.

---

## 항목 3 — 오프라인 환경 제약 (차단 대상)

**결론 `[부분 확인됨]`**: 자동 업데이트/공유/mDNS는 config로 끌 수 있으나, **telemetry on/off는 공식 문서에
필드가 없다** — air-gap 확정을 위해 소스/실측 확인이 필요하다.

| 설정 | 값 | 상태 | 근거 |
|------|-----|------|------|
| `autoupdate` | `false` (또는 `"notify"`) | `[확인됨]` | 업데이트 자동 다운로드 차단 |
| `share` | `"disabled"` | `[확인됨]` | 세션 공유 링크 생성 차단 |
| `server.mdns` | 비활성 | `[확인됨]` | 로컬 네트워크 광고 차단 |
| `cors` | 명시적 제한 | `[확인됨]` | 서버 모드 시 오리진 제한 |
| **telemetry / 사용량 전송** | — | **`[추정]` 문서에 없음 — 실측 필요** | 소스(`afff74eb`) grep + 네트워크 캡처로 확인 요망 |

```jsonc
{
  "autoupdate": false,
  "share": "disabled",
  "server": { "mdns": false }
}
```

**미해결 갭 (실측 필요)**: telemetry 엔드포인트 유무.
- 방법: 고정 커밋 소스에서 분석/텔레메트리 도메인 문자열 grep, 그리고 오프라인 기동 시 아웃바운드
  연결 캡처(P17-04 오프라인 리허설에 포함). 연결이 관측되면 hosts/방화벽 차단으로 보강.
- 이 갭이 닫히기 전에는 "완전 오프라인 안전"을 단정하지 말 것.

**작업 반영**: workspace `opencode.json`에 위 3필드 반영 완료(커밋 3d7dca9). telemetry 확인은 P17-04
오프라인 리허설 체크 항목으로 이관.

---

## 항목 4 — permission 패치 ↔ agent_ops 승인 게이트

**결론 `[확인됨]`**: OpenCode의 permission은 **TUI 내부 tool 실행**(read/edit/bash/webfetch 등)을
`allow`/`ask`/`deny`로 게이트한다. 이는 agent_ops의 **작업 승인 게이트(Fable APPROVED)** 와는
**서로 다른 층위**다 — 하나가 다른 하나를 대체하지 않는다. 두 게이트는 **직교(병행 방어선)**.

OpenCode permission 문서화 동작:

- 레벨: `allow` / `ask` / `deny`. `[확인됨]`
- 대상: read / edit / glob / bash / grep / webfetch / websearch / task / skill 등 내장 tool. `[확인됨]`
- 설정 예: `"permission": { "*": "ask", "bash": "allow", "edit": "deny" }`. `[확인됨]`
- **매칭 규칙: 마지막에 일치하는 규칙이 이긴다(last-matching-rule wins)**. `[확인됨]`
- `.env` 파일 읽기는 기본 차단. `[확인됨]`

**두 게이트의 관계**:

| 층위 | 무엇을 막나 | 누가 결정 |
|------|-------------|-----------|
| OpenCode permission | TUI가 즉시 실행하는 tool(셸/편집/네트워크) | 사용자(대화형 ask) + config |
| agent_ops 승인 게이트 | 어댑터 available=True, capability/artifact 추가, dependencies 변경, destructive git 등 하드 게이트 | **Fable APPROVED만** |

- 겹치지 않는다: OpenCode는 "지금 이 셸 명령을 실행할까"를, agent_ops는 "이 능력/변경을 시스템에
  편입할까"를 막는다. `[확인됨 — 설계상]`
- 권고: 회사 배포 시 OpenCode `permission` 기본을 보수적으로(`"*": "ask"`, `edit`/`bash`는
  파일럿 초기 `ask`) 두고, agent_ops 하드 게이트는 그대로 유지. 두 층 모두 켠다. `[추정 — 파일럿 정책]`

---

## 통합 방식 권고 (DoD: 1개 확정)

**agent_ops는 OpenCode의 플러그인/tool로 이식하지 않고 별도 CLI로 병행한다.**

근거:
1. OpenCode 플러그인 hook은 자체 프로세스 내부용이며 **외부 에이전트 런타임을 기동/오케스트레이션하는
   공식 확장점이 문서에 없다** (항목 2, `[확인됨]`).
2. 두 시스템의 승인 게이트가 **직교**하므로(항목 4), 하나에 종속시키면 방어선이 약해진다.
3. 데이터 교환은 공유 파일시스템(`AGENTOPS_ROOT`·산출물 폴더)과 `plan/` 보드로 충분 —
   프로세스 결합이 불필요하다.

즉 배포 형태: **OpenCode TUI(패치·오프라인 config) + agent_ops CLI**를 런처가 각각 기동, LLM은
공통 LIG 게이트웨이(항목 1) 공유. 얇은 커스텀 `tool()` 위임은 선택적 편의로만 열어둔다.

---

## 남은 실측 항목 (문서로 못 닫은 것)

| 항목 | 상태 | 이관처 |
|------|------|--------|
| telemetry 아웃바운드 유무 | 문서에 없음 | P17-04 오프라인 리허설(네트워크 캡처) |
| Qwen 로컬 모델 실제 context/output 한도 | 추정 | P00-03 실측 |
| OpenCode 기동 시간 개선 판정 | 추정 | P00-03 실측 |
