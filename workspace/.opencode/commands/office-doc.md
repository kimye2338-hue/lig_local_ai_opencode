---
description: JSON 스펙에서 docx/pptx 생성
agent: agent
subtask: false
---

입력:
$ARGUMENTS

docx 또는 pptx 종류와 spec JSON 경로를 확인한 뒤
`python agent_ops/agentops.py office-doc --kind <docx|pptx> --spec "<spec.json>"` 를 실행한다.
스펙이 없으면 필요한 JSON 구조를 간단히 제시하고 먼저 파일을 만들게 한다.
