# skill_context_compaction — 컨텍스트 압축 인수인계

## 언제
대화가 길어져 압축(compaction)이 임박했거나, 긴 작업 중간에 세션을 넘겨야 할 때.
(이 환경은 32k 컨텍스트로 작다 — 이르다 싶을 때 미리 해라.)

## 절차
1. `checkpoints/CHECKPOINT_TEMPLATE.md` 양식으로
   `checkpoints/CHECKPOINT_LATEST.md`를 write 도구로 덮어쓴다. 특히:
   - **미해결 이슈**: 증상 + 정확한 오류 문구 (err_ 참조번호 포함).
   - **다음 행동**: 복사해서 바로 실행 가능한 명령/파일 경로.
2. 새 지속 사실은 `memory/MEMORY.md`에 추가.
3. 압축 후 첫 응답에서는 CHECKPOINT_LATEST.md를 먼저 read하고 이어간다.

## 원칙
- 인수인계에 로그 원문·파일 본문을 넣지 않는다. 경로만.
- "무엇을 했나"보다 "**다음에 무엇을 하나**"를 정확히 남기는 것이 우선.
