---
description: Show or control OpenCodeLIG automatic self-improvement
agent: agent
subtask: false
---

# /self-improve

자가개선 루프는 기본적으로 자동 작동합니다. 이 명령은 상태 확인/끄기/켜기/보고서용입니다.

```bash
python agent_ops/agentops.py self-improve $ARGUMENTS
```

예:

```bash
python agent_ops/agentops.py self-improve status
python agent_ops/agentops.py self-improve off
python agent_ops/agentops.py self-improve on
python agent_ops/agentops.py self-improve report
```
