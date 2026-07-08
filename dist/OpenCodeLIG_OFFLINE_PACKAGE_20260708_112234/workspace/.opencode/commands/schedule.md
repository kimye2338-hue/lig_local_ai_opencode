---
description: 일정 등록/조회 (자연어) — 예: /schedule 금요일 14시 보고서 마감
agent: agent
subtask: false
---

입력:
$ARGUMENTS

- 입력이 있으면: `python agent_ops/agentops.py schedule add "$ARGUMENTS"` 로 등록하고
  등록 결과(해석된 날짜)를 확인해 사용자에게 알려준다. 날짜 해석이 모호하다는 출력이
  나오면 추측하지 말고 사용자에게 되묻는다.
- 입력이 없으면: `python agent_ops/agentops.py schedule list --when week` 로 이번 주
  일정을 보여준다.
