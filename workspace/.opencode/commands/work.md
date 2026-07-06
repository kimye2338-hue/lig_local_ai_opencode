---
description: 업무 지시 — agent_ops 런타임으로 산출물 생성 (real 모드)
agent: agent
subtask: false
---

사용자 업무 요청:
$ARGUMENTS

수행 절차:
1. 요청에 참고 파일 경로가 언급돼 있으면 그 경로를 --input 으로 붙인다.
2. 실행: `python agent_ops/agentops.py work --task "<요청>" --mode real [--input "<경로>"]`
3. 출력에서 산출물 경로(agent_ops/results/artifacts/<run_id>/)와 품질 검사 결과를
   찾아 사용자에게 한국어로 요약해 준다. LLM 내용 채움(enrichment) 상태도 전달.
4. 실패(비 0 종료)면 stderr 요지를 전하고 doctor 를 제안한다. 성공처럼 꾸미지 않는다.
5. 앱 실행(--execute)은 이 명령에서 하지 않는다 — 사용자가 원하면 무엇이 실행되는지
   설명하고 동의받은 뒤 별도로 `--execute --yes`를 붙여 재실행한다.
