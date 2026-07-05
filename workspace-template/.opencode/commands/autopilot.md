---
description: Run one request proactively in agent mode
agent: agent
subtask: false
---

에이전트 모드로 이 요청을 끝까지 처리하라. (자동 승인이 필요하면 사용자에게
`Shift+Tab` 으로 PERM:AUTO 전환을 안내.)

User request:
$ARGUMENTS

Execute project-local work directly, but do not use heredoc/cat/long echo/python -c to create files. Use write/apply_patch/safe_file_writer. If an approval modal contains prose mixed with command text, reject it.
