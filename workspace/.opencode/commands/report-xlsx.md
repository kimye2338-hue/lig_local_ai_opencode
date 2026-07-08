---
description: CSV/TSV 데이터를 진짜 .xlsx 파일로 생성
agent: agent
subtask: false
---

입력:
$ARGUMENTS

`python agent_ops/agentops.py report-xlsx --input "<CSV/TSV 경로>"` 를 실행한다.
생성된 xlsx 경로와 Office 의존성 상태를 함께 알려준다.
