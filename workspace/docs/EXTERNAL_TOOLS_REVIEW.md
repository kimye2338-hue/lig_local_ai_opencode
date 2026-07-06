# 외부 오픈소스 도입 검토 (2026-07-06)

사용자 제시 5개 저장소를 "오프라인 내부망에 완전 이식 가능 + 우리 기능에 유용" 기준으로
조사·판정했다. 조사 근거: 각 저장소 README/예제(1차 소스).

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

## ❌ 미채택 근거 보강

- **crawl4ai**: 표준 설치(`crawl4ai-setup`)가 브라우저 바이너리를 인터넷에서 받음 → air-gap 불가.
  CDP-to-기존Chrome 경로가 있으나 그건 우리 browser_cdp가 이미 함.
- **crawlee**: 본체 Node.js. Python 스택 통일을 깨고 별도 런타임 반입 부담. 브라우저 크롤링은
  결국 Playwright 필요 → 중복.
- **curl-impersonate**: JA3/TLS 핑거프린트 위장 도구. 봇탐지 있는 **공개 웹**용. 방화벽 안 사내
  포털을 실제 Chrome(CDP)로 자동화하면 핸드셰이크가 이미 진짜 Chrome이라 풀 문제가 없음.
  Windows 네이티브 바이너리도 없음.

## 원칙 (앞으로 외부도구 도입 시)

- **런타임에 인터넷 0**이면 채택 후보. 설치 시 인터넷이 필요해도 **오프라인 설치본
  (wheel/installer/브라우저 바이너리)을 반입해 깔 수 있으면 채택 가능**(사용자 방침 2026-07-06).
- "인터넷 문제"(반입으로 우회 가능)와 "플랫폼/설계 문제"(Windows 빌드 부재 등, 우회 불가)를 구분.
- 런타임에 클라우드 API 강제는 배제 — 로컬 게이트웨이/모델로 대체 가능할 때만.
- 채택 시 항상: 반입 절차 문서화 + 미반입 시 우아한 실패(조용한 실패 금지).
- 우리 기존 기능(browser_cdp/input_ingest/ocr_screen)과 겹치면 "대체"가 아니라 "갭 메우기" 우선.
