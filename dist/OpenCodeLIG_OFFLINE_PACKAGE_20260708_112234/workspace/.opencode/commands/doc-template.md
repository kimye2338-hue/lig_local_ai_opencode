---
description: 시험성적서/품질보고서/주간보고/회의록 정형 문서 생성
agent: agent
subtask: false
---

입력:
$ARGUMENTS

`python agent_ops/agentops.py doc-template <종류> [--input <CSV/JSON>] [--html]` 를 실행한다.
종류가 없으면 지원 종류를 보여주고, 입력 데이터가 있으면 `--input`에 붙인다.
