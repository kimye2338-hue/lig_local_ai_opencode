# 외부 오픈소스 도입 검토 (2026-07-06)

사용자 제시 저장소(1차 5종 + 2차 4종)를 "오프라인 내부망에 이식 가능 + 우리 기능에 유용"
기준으로 조사·판정했다. 조사 근거: 각 저장소 README/예제(1차 소스).

> **채택 방침 (2026-07-06 사용자 확정):** 유용한데 **인터넷(런타임/설치 시 다운로드)
> 때문에만** 보류한 도구는, **오프라인 설치본(wheel/installer/바이너리)을 반입해 깔 수
> 있으면 채택 가능**하다. 단 "인터넷 문제"와 "플랫폼/설계 문제"를 구분한다 —
> Windows 네이티브 빌드 자체가 없는 것(curl-impersonate)은 여전히 블로커. 아래 판정은
> 이 방침을 반영해 갱신됨.

## 판정 요약

| 저장소 | 라이선스 | 판정 | 이유 |
|---|---|---|---|
| microsoft/markitdown | MIT | ✅ **채택(완료)** | PDF/DOCX/PPTX/HTML→Markdown. 순수 Python 코어+wheel extras, 완전 오프라인. 우리 갭 정확히 메움 |
| browser-use | MIT | ✅ **채택 승인(선택 설치)** | 블로커가 인터넷(Playwright)뿐 → 오프라인 반입 가능. 기존 Chrome CDP+로컬 LLM으로 동작. 자율 다단계 브라우저 작업에 유용 |
| unclecode/crawl4ai | Apache-2.0 | ⭕ **채택 가능(우선순위 낮음)** | Chromium은 오프라인 반입 가능(방침상 블로커 해소). 단 browser_cdp+markitdown과 기능 겹쳐 실익 낮음 |
| apify/crawlee | Apache-2.0 | ⭕ **채택 가능(비권장)** | Node 런타임 오프라인 설치는 가능하나 스택 이원화+기능 중복. 굳이면 crawlee-python |
| lwthiker/curl-impersonate | MIT | ❌ 미채택(플랫폼 블로커) | **인터넷 문제 아님** — Windows 네이티브 빌드 자체가 없음. 게다가 내부 포털엔 불필요(CDP=실제 Chrome→실제 TLS) |
| CursorTouch/Windows-Use | MIT | ✅ **채택 승인(선택 설치)** | 임의 Windows GUI 앱을 UI Automation으로 조작(비전 불필요). 로컬 LLM(게이트웨이) 연결. wheel 반입 오프라인. **COM/CDP 없는 앱의 갭을 메움** |
| davidondrej/skills | MIT | ⭕ **부분 참고** | 범용 Agent Skill 마크다운(순수 콘텐츠). Claude용 SKILL.md 형식 — 우리 .opencode/agent_ops 런타임엔 직접 안 맞음. 유용 패턴만 참고 |
| bergside/awesome-design-skills | MIT | ❌ 미채택 | 웹 UI 디자인 67종. 기계공학 오피스 비서와 무관 |
| rednote-machine-learning/RedKnot | Apache-2.0 | ❌ 미채택(플랫폼 블로커) | NVIDIA GPU 서버+CUDA+Linux 전제. Windows 클라이언트 대상 아님(사내 H100 **서빙 서버** 쪽 사안) |

## ✅ markitdown — 채택 완료

`agent_ops/doc_convert.py` + `input_ingest` 통합. 상세: `docs/DOC_CONVERT.md`.
이제 PDF/DOCX/PPTX/HTML 문서를 `--input` 으로 넣으면 오프라인 변환 후 분석한다.

## ⭕ browser-use — 선택 반입 (필요 시)

우리 `browser_cdp`(CDP 기반 클릭/입력/추출)로 대부분의 포털 자동화가 되므로 기본 번들엔
넣지 않는다. 더 자율적인 "LLM이 페이지 보고 스스로 여러 단계 진행" 이 필요하면 아래처럼
**오프라인으로** 붙일 수 있다(조사로 확인된 1차 소스 패턴):

1. 크롬을 디버그 포트로 실행: `launch\chrome-debug.bat` (이미 있음, 9222 포트).
2. wheel 오프라인 반입: 인터넷 PC에서 `pip download browser-use -d wheelhouse` → 회사 PC에서
   `pip install --no-index --find-links wheelhouse browser-use`.
   (CDP 연결 모드는 Playwright **브라우저 바이너리** 다운로드가 불필요 — 이미 뜬 Chrome 사용.)
3. 기존 Chrome에 CDP로 연결 + 로컬 LLM(우리 게이트웨이는 OpenAI 호환):
   ```python
   from browser_use import Agent, BrowserSession
   # LLM: 사내 게이트웨이(OpenAI 호환) 또는 ChatOllama 등 로컬 모델
   session = BrowserSession(cdp_url="http://localhost:9222")  # 이미 실행 중인 Chrome
   agent = Agent(task="사내 포털에서 …", llm=<로컬 OpenAI호환 LLM>, browser_session=session)
   # await agent.run()
   ```
- 주의: 일반(비-CDP) 모드는 Playwright가 Chromium을 인터넷에서 받으므로 **CDP 연결 모드만** 쓴다.
- LLM은 클라우드(ChatBrowserUse 기본값)를 쓰지 말고 사내 게이트웨이/로컬 모델로 지정한다.

## ✅ Windows-Use — 채택 승인 (선택 설치, `agent_ops/adapters/desktop_ui.py`)

우리 어댑터는 COM(Excel/HWP/Outlook/SolidWorks)·CDP(브라우저)·배치(AutoCAD/MATLAB/Fluent)로
앱을 다룬다. 그러나 **COM API가 없는 앱**(사내 데스크톱 포털 클라이언트, 레거시 유틸,
버튼만 있는 사내 프로그램)은 조작 수단이 없다. Windows-Use는 그 갭을 메운다:
Windows **UI Automation 접근성 트리**를 읽어 LLM이 "무엇을 클릭/입력할지" 정하고
PyAutoGUI로 실행(비전 모델 불필요, 선택적).

- 라이선스 MIT, Python 3.10+, Windows 전용, pip wheel 반입만으로 오프라인 설치.
- LLM은 클라우드 아닌 **사내 게이트웨이(OpenAI 호환)** 또는 로컬 모델로 지정.
- 반입: 인터넷 PC에서 `pip download windows-use -d wheelhouse` → 회사 PC에서
  `pip install --no-index --find-links wheelhouse windows-use`.
- 통합점: `agent_ops/adapters/desktop_ui.py` (감지+capabilities, 미설치 시 반입 안내).
  실제 앱 구동은 회사 PC 파일럿에서 Windows-Use API/호환성 검증 후 활성화(현재 available:False).
- 유의: Excel 그리드·SolidWorks/AutoCAD 3D 뷰포트가 UI Automation 트리에 잘 노출되는지는
  미검증 — 이런 앱은 기존 COM/배치 어댑터를 우선하고, Windows-Use는 **COM이 없는 앱**에 쓴다.

## ⭕ davidondrej/skills — 부분 참고

범용 워크플로우 스킬(연구/문서화/요약) 마크다운. 우리 런타임은 `.opencode/commands`+
`agent_ops` 레시피 구조라 SKILL.md 를 그대로 쓰진 않는다. `thinking-and-docs`(문서화·요약)
패턴 중 유용한 것을 우리 커맨드/에이전트 지침에 골라 반영하는 정도로 참고. MIT — 문구를
그대로 벤더링할 경우 원저작권+MIT 전문 동봉.

## ❌ 미채택 근거 보강

- **crawl4ai**: 표준 설치(`crawl4ai-setup`)가 브라우저 바이너리를 인터넷에서 받음 → air-gap 불가.
  CDP-to-기존Chrome 경로가 있으나 그건 우리 browser_cdp가 이미 함.
- **crawlee**: 본체 Node.js. Python 스택 통일을 깨고 별도 런타임 반입 부담. 브라우저 크롤링은
  결국 Playwright 필요 → 중복.
- **curl-impersonate**: JA3/TLS 핑거프린트 위장 도구. 봇탐지 있는 **공개 웹**용. 방화벽 안 사내
  포털을 실제 Chrome(CDP)로 자동화하면 핸드셰이크가 이미 진짜 Chrome이라 풀 문제가 없음.
  Windows 네이티브 바이너리도 없음.
- **RedKnot**: 모델이 아니라 SGLang 위 장문맥 추론 가속 레이어. NVIDIA 서버 GPU+CUDA+Linux
  전제 = 플랫폼 블로커(인터넷 문제 아님). 우리 Windows 클라이언트가 아니라 **사내 H100 LLM
  서빙 서버** 최적화에나 의미 — 그 서버 운영 주체가 별도로 검토할 사안.
- **awesome-design-skills**: 웹 UI 디자인 스타일 67종. 기계공학 오피스 자동화와 무관.

## 3차 검토 (2026-07-06, 14개 URL — skills/loops/design/도메인)

| 항목 | 판정 | 반영 |
|---|---|---|
| VoltAgent/awesome-design-md (MIT) | ✅ 원칙 채택 | 디자인 코퍼스 보강(4단 위계·굵기≤2·강조색 절제·8pt 배수·tabular 숫자) |
| refactoringenglish "design doc" | ✅ 원칙 참고 | 보고서 골격(목적→배경→범위→시나리오→다이어그램→일정). 원문 미복제, 재서술 |
| Korean Business Navigator | ✅ **재작성 채택** | `knowledge/domain/korean_business.md` — 품의/완곡표현/격식/톤. 라이선스 불명→우리말 재작성. 메일/회의록/보고서 작업에 주입 |
| Obsidian Smart Connections | ⭕ **선택 채택** | 로컬 임베딩 오프라인 가능. Obsidian 위키에 의미검색 추가. 수동 zip 설치 문서화(docs/OBSIDIAN_WIKI.md). 라이선스=소스공개 |
| Karpathy gist (LLM Wiki) | ℹ️ 이미 반영 | 우리 위키(consolidate/lint/recall)의 원천 개념. Query→발견→위키 재반영 루프는 향후 정련 여지 |
| forwardfuture/elorm "agent loops" | ℹ️ 이미 커버 | Independent Verifier/CI Watcher = 감시 패턴 → 우리 agent.md 감시 프로토콜 + `agentops watch`로 이미 구현. (사이트 SSL 오류로 원문 저신뢰, 재확인 권장) |
| mattpocock/emilkowalski/addyosmani/vercel skills | ⭕ 부분 참고/skip | 실행형 SKILL.md(코딩/웹 중심). 문서화/PRD 패턴만 아이디어 참고, 통째 도입 skip |
| getdesign.md / styles.refero / find-skills / gist | ❌ skip | 온라인 웹 UI 갤러리/검색 서비스. 문서/PPT와 무관하거나 오프라인 불가 |

## 4차 검토 (2026-07-06, harness/compression/browser-agent)

| 항목 | 라이선스 | 판정 | 이유/반영 |
|---|---|---|---|
| walkinglabs/learn-harness-engineering (ko) | 미명시(방법론) | ✅ **가이드 채택** | 하네스 설계 방법론(닫힌루프·상태·검증·관측성·종료). `docs/HARNESS_PRINCIPLES.md`로 우리 구성요소 매핑·점검 규칙화 |
| headroomlabs/headroom | Apache-2.0 | ⭕ **개념 참고(보류)** | 컨텍스트 압축 레이어. 아이디어 유용하나 Rust빌드+AVX2+모델 다운로드로 무겁고 우리 truncation과 부분중복. 향후 최적화 시 재검토 |
| microsoft/Webwright | MIT | ⭕ **패턴만 참고/skip** | 브라우저 code-as-action 에이전트. 로컬 게이트웨이 연동 미확인+Playwright+웹도메인(browser_cdp/browser-use로 커버). 루프 설계만 참고 |
| x.com 트윗 | — | ⚠️ 접근불가 | 로그인/결제 벽(HTTP 402). 내용 붙여주면 검토 |

## 5차 검토 (2026-07-06, Obsidian 마켓 / 아이콘)

| 항목 | 판정 | 반영 |
|---|---|---|
| community.obsidian.md 플러그인 | ✅ 추천 확대 | 오프라인 로컬 플러그인(Dataview/Templater/Excalidraw/Advanced Tables) 위키 문서에 추가. 수동 zip 설치 |
| xandemon/developer-icons | ❌ skip | React/npm 브랜드 로고셋(정적 SVG 불명확), 우리 도메인과 무관, **상표권 리스크**(브랜드 로고). 대신 HTML 리포트에 직접 그린 범용 상태 아이콘(합격/경고) 자체 추가 |

## 원칙 (앞으로 외부도구 도입 시)

- **런타임에 인터넷 0**이면 채택 후보. 설치 시 인터넷이 필요해도 **오프라인 설치본
  (wheel/installer/브라우저 바이너리)을 반입해 깔 수 있으면 채택 가능**(사용자 방침 2026-07-06).
- "인터넷 문제"(반입으로 우회 가능)와 "플랫폼/설계 문제"(Windows 빌드 부재 등, 우회 불가)를 구분.
- 런타임에 클라우드 API 강제는 배제 — 로컬 게이트웨이/모델로 대체 가능할 때만.
- 채택 시 항상: 반입 절차 문서화 + 미반입 시 우아한 실패(조용한 실패 금지).
- 우리 기존 기능(browser_cdp/input_ingest/ocr_screen)과 겹치면 "대체"가 아니라 "갭 메우기" 우선.
