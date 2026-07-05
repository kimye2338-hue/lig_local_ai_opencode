---
description: Explain the 3 modes and the ASK/AUTO approval toggle
agent: agent
subtask: false
---

모드는 3개다 (Tab 으로 순환):

- build: 일반 모드 — 대화/코딩 기본.
- plan: 계획 모드 — 읽기/계획만, 수정 없음.
- agent: 에이전트 모드 — agent_ops 런타임과 서브에이전트를 적극 써서 업무를 끝까지 해결.

승인 정책은 모드와 별개다: `Shift+Tab` 이 ASK/AUTO 를 토글한다.
AUTO 에서는 승인창이 자동 승인(1회씩)된다 — "맡겨두면 알아서"는 agent 모드 + AUTO 조합.
AUTO 여도 command_guard 가 위험 명령을 차단하고, 명시적 deny 는 우회되지 않는다.
