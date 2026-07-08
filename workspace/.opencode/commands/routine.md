---
description: 반복 작업 저장/조회/재생
agent: agent
subtask: false
---

입력:
$ARGUMENTS

- 입력이 `list` 이거나 비어 있으면 `python agent_ops/agentops.py routine list`.
- `save <이름>`이면 `python agent_ops/agentops.py routine save "<이름>"`.
- `run <이름>`이면 `python agent_ops/agentops.py routine run "<이름>"`.
- `import <프리셋.json>`이면 `python agent_ops/agentops.py routine import "<프리셋.json>"`.
재생 후 성공/실패를 반드시 확인해 사용자에게 알려준다.
