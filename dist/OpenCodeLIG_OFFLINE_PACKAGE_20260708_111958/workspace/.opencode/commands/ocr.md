---
description: 화면 또는 이미지 OCR 읽기
agent: agent
subtask: false
---

입력:
$ARGUMENTS

- 이미지 경로가 있으면 `python agent_ops/agentops.py ocr --image "<경로>"`.
- 입력이 없으면 `python agent_ops/agentops.py ocr`.
- 실패하면 OCR 엔진 미반입인지, 스크린샷 권한 문제인지 구분해 `deps`와 함께 안내한다.
