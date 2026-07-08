# OpenCodeLIG — 새 세션 진입점 (이 파일을 먼저 읽으세요)

이 폴더를 지정한 새 세션(Codex/Codex 등)이 **전체 프로그램을 빠르게 파악**하도록 정리한
안내다. 사용자용 사용법은 `workspace/docs/사용법/GUIDE.md` 하나면 되고, 이 문서는 개발/이어작업용.

## 1. 이게 뭔가

사내 오프라인(망분리) 윈도우 PC용 **한국어 AI 업무비서**. H100 서버의 로컬 LLM
(EXAONE-4.5-33B / Qwen3.6-27B)을 OpenAI 호환 게이트웨이로 쓰고, 실제 업무 소프트웨어
(Excel·HWP·SolidWorks·AutoCAD·MATLAB·Fluent·Outlook·브라우저)를 자동화하며, 배운 것을
Obsidian 위키 기억으로 남긴다. 패치된 OpenCode TUI + 파이썬 런타임(`agent_ops`) 구조.

## 2. 폴더 구조 (배포 패키지)

```
LIG_OPENCODE/
  payload/opencode.exe               패치된 OpenCode 본체(132MB, MIT)
  INSTALL_OFFLINE_LIG_OPENCODE.bat.txt   오프라인 설치기(.bat로 개명 후 실행)
  SHA256SUMS.txt                     무결성(installer가 payload 검증)
  workspace/                         프로그램 본체 → 설치 시 %USERPROFILE%\OpenCodeLIG\workspace
    agent_ops/                       파이썬 런타임(두뇌·도구·기억·어댑터). 진입점 agentops.py
      adapters/                      앱 제어(office/hwp/solidworks/…/ocr_screen/desktop_ui)
      knowledge/                     자동주입 근거 KB. apis(공식API 레시피)/design(문서·PPT)/
                                     domain(한국비즈)/skills(절차) + ★전공 교과서급 레퍼런스:
                                     domains(재료·구조·피로·진동·열유체·기계요소·공작법·CNC·치구·
                                     GD&T·유도탄설계·데이터·금속규격)/standards(MIL-STD-810H)/
                                     lifeskills(문서작성)/_moc(도메인 지도). knowledge_base.py가
                                     질문→희소용어 라우팅→관련 하위섹션만 주입(출처·수치경고 헤더).
      ui/hamster_overlay.py          데스크톱 상태 펫
    .opencode/                       OpenCode 커맨드·에이전트·플러그인. agent.md = 주 에이전트(레시피 표)
    launch/                          .bat 런처(항상 이걸로 실행 — chcp 65001 + PYTHONUTF8)
    config/lig-api.env.example       게이트웨이 설정(사내 실값 반영, 설치 시 secret으로 시드 → 무설정 연결)
    docs/                            문서(아래 3.)
    tests/                           테스트(스크립트식 + pytest)
    tools/                           오프라인 반입 바이너리 자리(Obsidian/OCR 등, 기본 미포함)
```

## 3. 어디부터 보나 (문서)

- **사용법 전체**: `workspace/docs/사용법/GUIDE.md` (설치·사용·기능·문제해결·반입)
- **장애 대응**: `workspace/docs/사용법/RUNBOOK.md` (증상→파일→대응)
- **전체 워크플로우/기억 효율 점검**: `workspace/docs/운영/WORKFLOW_AUDIT_20260707.md`
- **외부도구 도입 판정 이력**: `workspace/docs/운영/EXTERNAL_TOOLS_REVIEW.md`
- **제품 비전/전략**: `workspace/docs/archive/PRODUCT_MASTER_PLAN_FABLE5.md`, `MASTER_PLAN.md`
- **하네스 설계 원칙**: `workspace/docs/설계/HARNESS_PRINCIPLES.md`
- **기능별 상세**: DOC_CONVERT / OFFICE_WRITER / OCR_SCREEN / OBSIDIAN_WIKI / HAMSTER_OVERLAY

## 4. 불변 규칙 (반드시 지킬 것)

- **LLM 설정 불변**: `config/lig-api.env.example`의 게이트웨이 URL/키/라우트/모델명
  (EXAONE/Qwen)은 사용자 권한. 함부로 바꾸지 말 것.
- **USERDATA 불가침**: `%USERPROFILE%\OpenCodeLIG_USERDATA\`(기억/위키/일정)는 절대 삭제 금지.
- **.bat는 CRLF**: 모든 .bat/.bat.txt는 CRLF + `chcp 65001`(+python 호출 시 PYTHONUTF8). LF 금지.
- **오프라인 전제**: 런타임 네트워크 0. 바이너리·wheel은 `tools/`로 반입.
- **안전 가드 우회 금지**: command_guard/명시 deny는 어느 승인정책(ASK/AUTO/FULL)에서도 유지.

## 5. 확인/테스트 (개발 이어갈 때)

```cmd
cd workspace
python agent_ops\agentops.py doctor        # 상태 진단
python agent_ops\agentops.py deps          # 선택기능 반입 상태
python -m pytest tests\test_work_command.py -q
py -3.11 tests\test_tool_dispatch.py       # 스크립트식 테스트(개별 실행)
```
- 대부분 테스트는 `python tests\<파일>` 로 개별 실행(스크립트식). green 기준은 각 파일 마지막 줄.
- `test_ocd_profiles/test_patch_build/test_release_manifest/test_launch_bats`는 소스저장소의
  `release/` 를 요구 → **배포 패키지엔 없어 실패하는 게 정상**(코드 결함 아님).
- 실 LLM/Office 스모크(test_real_llm_smoke/test_office_live_smoke/test_capability_floor)는 스킵.

## 6. 핵심 능력 (자연어로 시키면 자동 선택 — agent.md 레시피 표)

산출물 생성(work), 진짜 Office 파일(office-doc/report-xlsx), 데이터 HTML 리포트(report-html),
정형문서(doc-template), 문서 읽기(markitdown), 웹 CDP + 화면 OCR(ocr), 앱 자동화(어댑터),
반복작업 record&replay(routine), 활동 타임라인(timeline), 무한대기 감시(watch),
기억·위키(remember/recall/book/wiki, 작업 자동적재 → Obsidian 정리). 작업 유형별로 공식API·
디자인·한국비즈니스·절차가 자동 주입된다. **공학 질문**(구조/진동/피로/열유체/기계요소/공작법/
CNC/치구/GD&T/유도탄/데이터/금속규격/810H)이면 전공 교과서급 레퍼런스 노트에서 관련 하위섹션이
자동 주입 — "교수처럼" 답하되 수치는 원문 확인을 명시한다(knowledge_base.py, `_SCHEMA.md` 규약).

## 7. 현재 상태

전 테스트 green(실코드 실패 0), 게이트웨이 무설정 연결 반영, 한글 인코딩 해결, docs 정리 완료.
레퍼런스 KB 15개 노트 교과서화 완료(라우팅 골든셋 42/42, `tests/test_knowledge_routing.py`).
이어서 작업할 땐: `workspace/` 에서 위 테스트로 baseline 확인 → 변경 → 회귀 확인 → 커밋.
