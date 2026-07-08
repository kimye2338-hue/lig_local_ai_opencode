---
description: CSV/TSV 데이터를 표+차트 HTML 리포트로 생성
agent: agent
subtask: false
---

입력:
$ARGUMENTS

`python agent_ops/agentops.py report-html --input "<CSV/TSV 경로>"` 를 실행한다.
입력 파일이 없으면 먼저 데이터를 CSV로 저장한 뒤 실행하라고 안내한다.
