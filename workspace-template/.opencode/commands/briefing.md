---
description: 아침 브리핑 (오늘/이번주 일정, 마감, 액션아이템, 어제 요약)
agent: agentops-supervisor
subtask: false
---

실행: `python agent_ops/agentops.py briefing`
결과 파일(agent_ops/results/reports/briefing_*.md) 내용을 한국어로 간단히 요약해 주고,
일정이 비어 있다는 안내가 나오면 `/schedule <일정>` 등록이나 Outlook 동기화를 권한다.
