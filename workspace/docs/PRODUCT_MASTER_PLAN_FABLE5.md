# OpenCodeLIG — 통합 제품 마스터플랜 (Fable 5 종합, 2026-07-06)

> 이 문서는 사용자의 여러 요청 속에 숨은 "하나의 제품 상(像)"을 정의하고,
> 그것을 200% 수행하도록 만드는 전체 설계·실행 계획이다. 전략 문서는 이 파일,
> 실행 추적은 `docs/WORK_STATUS_20260706.md`.

---

## 0. 한 문장 제품 정의

> **사내 오프라인(망분리) 윈도우 PC에서, H100 로컬 LLM(EXAONE/Qwen)을 두뇌로,
> 실제 업무 소프트웨어(Excel·HWP·SolidWorks·AutoCAD·MATLAB·Fluent·Outlook·브라우저)를
> 손발로 부리고, 화면을 눈(OCR)으로 보고, 모든 배운 것을 Obsidian 위키 기억으로 남기며,
> 공식 API 근거로만 코드를 짜는 — 한국어 기계공학 엔지니어 전용 업무비서.**
> 데스크톱엔 상태를 표정으로 알려주는 귀여운 햄스터 펫이 상주한다.

"코딩 챗봇"이 아니라 **실제 업무를 대신 수행하고 증거와 함께 보고하는 자율 비서**.

---

## 1. 요청 → 제품 기능 매핑 (숨은 상 드러내기)

| 사용자가 말한 것 | 진짜 원하는 것 | 제품 기능 |
|---|---|---|
| "프로그램 검토·수정·개선" | 신뢰할 수 있는 견고한 코어 | 안전계층·인코딩·동시성 버그 제거(완료) |
| "API 정보 그대로 둬" | 재설정 없는 무중단 운영 | LLM 설정 불변 보존 |
| "햄스터 펫처럼, 귀엽게, 코덱스보다 자연스럽게" | 정서적 동반자 + 상태 가시성 | 스티커 애니 햄스터 오버레이 |
| "오프라인 OCR로 화면 파악" | 막혔을 때 스스로 눈으로 확인 | 스크린샷+OCR(한/영) 폴백 루프 |
| "공식 가이드 기반으로 코딩(하이쿠 조사)" | 환각 없는 진짜 동작하는 매크로 | 버전별 공식 API 로컬 코퍼스 + 근거참조 생성 |
| "GitHub 스타 많은 아이디어 차용" | 검증된 설계 패턴 수용 | 위키 커뮤니티 기법(별칭/모순/백링크) 등 |
| "옵시디언으로 위키 관리, 내 질문·메모리 관리" | 내가 직접 보고 고치는 기억 | 위키 = Obsidian vault, 질문/교훈 자동 적재 |
| "폴더 구조 명확히, 잡파일 정리, 기능 통일" | 이해·유지 가능한 단일 구조 | 폴더 재구조화 + 미사용 파일 제거 |

핵심 통찰: 이 요청들은 **"자율성(스스로 보고·기억·판단) + 근거성(공식 API·실제 실행)
+ 지속성(기억·오프라인) + 친밀성(펫·한국어·저마찰)"** 네 축을 가진 하나의 제품을 가리킨다.

---

## 2. 목표 아키텍처 (4개 층 + 기억)

```
┌────────────────────────────────────────────────────────────┐
│  대면층(Companion)   햄스터 펫 오버레이 · 한국어 메뉴/브리핑    │
├────────────────────────────────────────────────────────────┤
│  두뇌층(Brain)       LLM 런타임(EXAONE/Qwen) · 툴 디스패치       │
│                      · 공식 API 코퍼스 참조 · 안전/승인 가드     │
├────────────────────────────────────────────────────────────┤
│  감각층(Senses)      화면 OCR(한/영) · 입력 인제스트 · 브라우저   │
├────────────────────────────────────────────────────────────┤
│  손발층(Actuators)   Excel·HWP·SolidWorks·AutoCAD·MATLAB·       │
│                      Fluent·Outlook COM/배치 어댑터              │
├────────────────────────────────────────────────────────────┤
│  기억층(Memory)      Obsidian vault = LLM 위키 · 질문/교훈/규칙   │
│                      · USERDATA 절대 불가침                      │
└────────────────────────────────────────────────────────────┘
```

## 3. 목표 폴더 구조 (자명한 이름, 최소 개수)

설치 후 `%USERPROFILE%\OpenCodeLIG\` 기준. 원칙: **역할=폴더명**, 런타임 산출물은
USERDATA로 분리(프로그램 파일과 섞지 않음), 루트 잡파일 최소화.

```
OpenCodeLIG/
  bin/                  실행파일 (opencode.exe, ocd.bat, ai.bat)
  app/                  ← 기존 workspace/ 개편. 프로그램 본체
    core/               런타임(런타임/툴/안전/인코딩/상태)      ← agent_ops 핵심
    senses/             ocr_screen · input_ingest · browser
    actuators/          office/cad/mail 어댑터 (기존 adapters/)
    companion/          hamster 펫 (기존 ui/)
    knowledge/          공식 API 코퍼스(apis/*.md) — 생성근거
    interface/          .opencode 커맨드/에이전트/플러그인
    launch/             .bat 런처 (한 곳으로)
    docs/               문서
    tests/              테스트
  USERDATA/  (= 기존 OpenCodeLIG_USERDATA, 불가침)
    memory/             전역 기억
    wiki/               ← Obsidian vault (질문·교훈·규칙·API메모)
    state/ diagnostics/ secrets/
  tools/                옵시디언 오프라인 설치본 등 반입 바이너리
```
> 주의: 재구조화는 INSTALL 스크립트·SHA256SUMS·테스트 경로(parents[N])·빌드 워크플로우를
> 동시에 갱신해야 하며, 전 테스트 재검증 후 단일 커밋으로 진행. 세션한도 리스크 때문에
> **다른 안전작업 완료 후 마지막 단계**로 실행한다.

## 4. 실행 단계 (Phase)

- **P1 코어 하드닝** — 완료(커밋 b787b2d).
- **P2 기억·위키(Obsidian)** — 위키 커뮤니티기능 병합 + wiki 디렉터리를 Obsidian vault로
  (`.obsidian/` 설정 시드, `[[백링크]]` 호환), 질문/교훈 자동 적재. Obsidian 설치본은
  `tools/`에 반입 안내 + 원클릭 "위키 열기" 런처.
- **P3 감각(OCR)** — `senses/ocr_screen.py`: mss/PIL 스크린샷 → 플러거블 OCR
  (RapidOCR-onnx 우선, tesseract kor+eng 대안). 브라우저 막힘 시 자동 폴백. 툴 등록.
- **P4 근거(공식 API 코퍼스)** — Haiku 리서치로 사용자 소프트웨어 버전별 공식 API/명령
  수집(§5), `knowledge/apis/`에 구조화. 매크로 생성 시 system 컨텍스트로 주입 →
  환각 아닌 근거기반.
- **P5 손발 견고화** — solidworks/autocad/fluent/matlab/hwp/office_convert/browser_cdp
  프로세스 정리·타임아웃·트리킬 (WS-C 잔여).
- **P6 펫 완성** — 스티커 애니 렌더링 연결·자연스러운 상태전이.
- **P7 대청소·재구조화** — 미사용 파일 삭제, §3 구조 적용, 스크립트/체크섬/테스트 경로
  일괄 갱신, 전 테스트 green 단일 커밋.

## 5. 확정 소프트웨어 버전 (공식 API 코퍼스 대상, MASTER_PLAN §1.3 기준)
- MS Office 2016 (Excel/Word/PowerPoint/Outlook VBA object model)
- 한글 HWP (HwpAutomation/HAction API)
- SolidWorks (SolidWorks API, ISldWorks)
- AutoCAD (ActiveX Automation / accoreconsole script)
- MATLAB (-batch / script API)
- ANSYS Fluent (journal/TUI 명령)
→ 각 항목 공식 문서 URL·버전·핵심 객체/메서드·예제를 `knowledge/apis/<sw>.md`로.

## 6. 불변 규칙
- LLM 설정/키/라우트/모델명 불변. USERDATA(기억) 절대 불가침.
- 파괴적 구조변경은 git 백업 + 전 테스트 green 후에만.
- 오프라인 전제: 런타임에 네트워크 0. 바이너리는 반입(tools/)로 해결.
