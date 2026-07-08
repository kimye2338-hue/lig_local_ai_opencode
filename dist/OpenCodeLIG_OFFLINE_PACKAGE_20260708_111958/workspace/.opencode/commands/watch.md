---
description: 장시간 작업 진행/멈춤 상태 확인
agent: agent
subtask: false
---

`python agent_ops/agentops.py watch` 를 실행한다.
종료코드 3이면 멈춤 의심이므로 `doctor`로 원인을 확인하고, 종료코드 4면 정지 요청 상태로 보고한다.
