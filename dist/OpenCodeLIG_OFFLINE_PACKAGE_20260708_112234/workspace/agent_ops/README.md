# agent_ops — 비서 런타임

비서의 두뇌·도구·기억·어댑터가 있는 파이썬 런타임. 진입점은 `agentops.py`.
**사용법은 `../docs/사용법/GUIDE.md`**, 장애 대응은 `../docs/사용법/RUNBOOK.md` 참고. 여기는 개발자용 요약.

## 구성 한눈에

- **핵심 흐름**: `tool_dispatch.py`(에이전트 루프·20개 도구), `lig_runtime.py`/`lig_providers.py`
  (게이트웨이 LLM·폴백), `command_guard.py`/`safety.py`/`approval.py`(안전·승인)
- **기억/위키**: `memory_manager.py`(전역 기억·자동 적재·규칙 보호), `wiki_manager.py`(증류·별칭·
  모순후보·백링크), `knowledge_book.py`(HTML 지식책), `wiki_vault.py`(Obsidian vault)
- **근거 주입**: `api_reference.py`(공식 API), `design_guidance.py`(문서/PPT 디자인),
  `domain_context.py`(한국 비즈니스) → 생성 시 맞는 근거만 주입
- **산출물**: `artifact_generators.py`(문서/슬라이드/매크로 초안), `office_writer.py`(진짜
  xlsx/docx/pptx), `html_report.py`(표+차트 HTML), `doc_convert.py`(문서→Markdown, markitdown)
- **자동화**: `routines.py`(record & replay), `activity_timeline.py`, `orchestrator.py`,
  `state_manager.py`(상태·하트비트), `schedule_store.py`/`secretary.py`(일정·비서)
- **어댑터**(`adapters/`): office/hwp/solidworks/autocad/matlab/fluent/outlook/browser_cdp/
  ocr_screen/desktop_ui — 앱 제어·화면 OCR·문서 변환

## 첫 실행 점검

```cmd
python agent_ops\agentops.py init
python agent_ops\agentops.py doctor
python agent_ops\agentops.py verify
```

## 자주 쓰는 명령 (자세히는 GUIDE §6, agent.md 레시피)

- 업무: `work --task "..." [--input 파일]` / 웹: `agent --mode real --task "..."`
- 산출: `report-xlsx --input x.csv` / `office-doc --kind pptx --spec s.json` / `report-html --input x.csv`
- 기억: `remember "..."` / `recall <키워드>` / `book --open` / `wiki`
- 감시·자동화: `watch` / `timeline` / `routine save|list|run`
- 무인 오케스트레이터: `launch\RUN_AGENTOPS_ORCHESTRATOR.bat.txt`를 `.bat`으로 바꿔 실행(병렬판도 동일)

## 불변 규칙

- LLM 설정(게이트웨이/키/라우트/모델명)과 `USERDATA` 기억은 절대 건드리지 않는다.
- 안전 가드(위험 명령 차단·명시 deny)는 어느 승인 정책에서도 우회되지 않는다.
