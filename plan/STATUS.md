# STATUS — 작업 보드 (유일한 진행 상태 진실 소스)

- 워커: **위에서부터 첫 READY 작업 1개만** 잡는다. 본인 행의 [상태]/[보고서] 칸만 수정.
- APPROVED 전환은 Fable만. 선행이 전부 APPROVED 되면 Fable이 BLOCKED→READY로 바꾼다.
- 환경 태그: ANY(아무 PC) / LOCAL-LLM(Ollama 필요) / CHROME / EXCEL / INTERNET / COMPANY / HUMAN(사람 개입) / FABLE-ONLY

| ID | 제목 | 담당 | 선행 | 환경 | 상태 | 보고서 | 리뷰 |
|----|------|------|------|------|------|--------|------|
| P00-01 | 환경 probe 실행/업로드 (probe/README.md) | **human** | — | 집+회사 | APPROVED | probe/results/ r1~r3 | 잔여는 P00-03 이관 |
| P00-02 | OpenCode 공식 문서 연동 조사 | **fable** | — | INTERNET | READY(부분 진행) | | |
| P00-03 | 회사 real-mode 실측 팩 (NEXT_ONSITE.md) | **human** | — | COMPANY | READY | | |
| P09-01 | LLM provider 프로필/env 완전 오버라이드 | codex | — | ANY | APPROVED | plan/reports/P09-01-r2.md | plan/reviews/P09-01-r2.md |
| P09-02 | 작업 유형→라우트 자동 선택 + 진단 | codex | P09-01 | ANY | APPROVED | plan/reports/P09-02-r1.md | plan/reviews/P09-02-r1.md |
| P09-03 | real-LLM 스모크 테스트 + doctor + 실측 | codex | P09-02 | LOCAL-LLM(옵션) | AWAITING-REVIEW | plan/reports/P09-03-r1.md | |
| P10-01 | git 히스토리 내부 hostname purge | fable | — | FABLE-ONLY | READY | | |
| P11-A | lig_runtime native function calling(tools) 경로 | codex | P09-02 | ANY | READY | | |
| P11-01 | weak-model capability-floor 하네스 | codex | P09-03, P11-A | ANY | BLOCKED | | |
| P11-02 | floor 실측 + 파서/프롬프트 보강 | codex | P11-01 | LOCAL-LLM | BLOCKED | | |
| P12-01 | stdlib WebSocket 미니 클라이언트 | codex | — | ANY | APPROVED | plan/reports/P12-01-r1.md | plan/reviews/P12-01-r1.md |
| P12-02 | 브라우저 CDP 어댑터 + chrome-debug.bat | codex | P12-01 | ANY | APPROVED | plan/reports/P12-02-r1.md | plan/reviews/P12-02-r1.md |
| P12-03 | CDP 실측 + available 전환 | codex | P12-02 | CHROME | AWAITING-REVIEW | plan/reports/P12-03-r1.md | |
| P13-01 | approval(승인 게이트) + audit(감사 로그) 모듈 | codex | — | ANY | APPROVED | plan/reports/P13-01-r1.md | plan/reviews/P13-01-r1.md |
| P13-02 | `work` 오케스트레이터 subcommand E2E | codex | P13-01 | ANY | APPROVED | plan/reports/P13-02-r1.md | plan/reviews/P13-02-r1.md |
| P14-01 | schedule store + 결정적 날짜 파서 | codex | — | ANY | APPROVED | plan/reports/P14-01-r1.md | plan/reviews/P14-01-r1.md |
| P14-02 | schedule CLI + capability 등록 | codex | P14-01 | ANY | READY | | |
| P14-03 | 아침 브리핑 + 리마인더 BAT | codex | P14-02 | ANY | BLOCKED | | |
| P14-04 | 회의록(meeting_minutes) capability | codex | P14-02 | ANY | BLOCKED | | |
| P14-05 | 주간보고 초안(weekly_report) | codex | P13-01, P14-02 | ANY | BLOCKED | | |
| P15-01 | Office 2016 호환 quality 규칙 | codex | — | ANY | APPROVED | plan/reports/P15-01-r1.md | plan/reviews/P15-01-r1.md |
| P15-02 | excel_com 어댑터 (사본 정책) | codex | P15-01, P13-01 | ANY | READY | | |
| P15-03 | outlook_com 어댑터 (일정/메일 read) | codex | P15-02, P14-02 | ANY | BLOCKED | | |
| P15-04 | word/ppt 변환 action + 집 Excel 실측 | codex | P15-02 | EXCEL | BLOCKED | | |
| P16-01 | matlab_automation capability + .m 생성기 | codex | P15-01 | ANY | READY | | |
| P16-02 | matlab -batch / AutoCAD accoreconsole 어댑터 | codex | P16-01 | ANY | BLOCKED | | |
| P16-03 | simulation_automation (Fluent journal) + fluent_batch | codex | P16-01 | ANY | BLOCKED | | |
| P16-04 | hwp_com + solidworks_com 어댑터 | codex | P15-02 | ANY | BLOCKED | | |
| P17-01 | xlsx 입력 ingest (openpyxl optional) | codex | — | ANY | APPROVED | plan/reports/P17-01-r1.md | plan/reviews/P17-01-r1.md |
| P17-02 | 의존성 prefetch + SHA256 확정 | codex | P16-04 | INTERNET | BLOCKED | | |
| P17-03 | 반입 번들 build + setup.bat + 체크리스트 | codex | P17-02 | ANY | BLOCKED | | |
| P17-04 | 오프라인 설치 리허설 (네트워크 차단) | human+codex | P17-03 | HUMAN | BLOCKED | | |
| P18-01 | secret 스캔 pre-commit 스크립트 | codex | — | ANY | APPROVED | plan/reports/P18-01-r1.md | plan/reviews/P18-01-r1.md |
| P18-02 | RUNBOOK + audit 순환 + doctor 운영 섹션 | codex | P13-01 | ANY | READY | | |
| P19-01 | 회사 파일럿 체크리스트/기록 양식 준비 | codex | P14-03, P15-02, P16-02 | ANY | BLOCKED | | |
| P19-02 | 회사 파일럿 12종 실측 | human+fable | P19-01, P17-04 | COMPANY+HUMAN | BLOCKED | | |
| P20-01 | 음성 입력 구현 (whisper.cpp) | codex | P19-02 | ANY | BLOCKED | | |

## 이력 (상태 변경 시 한 줄씩 추가 — 최신이 위)

- 2026-07-03 company_check 종합 실측 (사용자): gateway **native function calling 완전 지원**(tool_calls 반환) + 전 앱 COM/MATLAB/Chrome 실동작 성공 + Excel VBProject 접근 가능. Fable: 리스크 5종 해소, **P11-A(native tools 경로) 신설·READY**, P11-01은 P11-A 선행 추가, MASTER_PLAN 리스크 갱신. 결과 probe/results/company_check_20260703.md.
- 2026-07-03 P12-03 AWAITING-REVIEW (Codex). 보고서: plan/reports/P12-03-r1.md. Chrome CDP live 4 actions + 전체 17 테스트 파일 447 checks/1 skip 통과.

- 2026-07-03 P12-03 IN-PROGRESS (Codex). 시작 HEAD: 34cc6ad.

- 2026-07-03 계획 고도화 (Fable): gateway 3라우트 200(연결 company validated) 반영 — P00-01 APPROVED(잔여→P00-03 신설), NEXT_ONSITE.md 상시 방문 목록 신설, P11에 function-calling A/B 경로 반영, P16-02 accoreconsole 확정, P17-02 pywin32 기설치 반영.

- 2026-07-03 P09-03 IN-PROGRESS (Codex). 시작 HEAD: 0e66194.
- 2026-07-03 Fable 배치 리뷰 2차: 7건 전부 APPROVED (P09-02, P12-02, P13-02, P14-01, P15-01, P17-01, P18-01) — 전 16 테스트 파일 440 checks 재검증, deviation 0. 신규 READY: P09-03, P12-03, P14-02, P15-02, P16-01, P18-02.

- 2026-07-03 P18-01 AWAITING-REVIEW (Codex). 보고서: plan/reports/P18-01-r1.md. secret scan 포함 전체 16파일 440 checks 통과.
- 2026-07-03 P18-01 IN-PROGRESS (Codex). 시작 HEAD: 3e51d5a.
- 2026-07-03 P17-01 AWAITING-REVIEW (Codex). 보고서: plan/reports/P17-01-r1.md. optional xlsx ingest 포함 전체 15파일 431 checks 통과.
- 2026-07-03 P17-01 IN-PROGRESS (Codex). 시작 HEAD: 88b87ba.
- 2026-07-03 P15-01 AWAITING-REVIEW (Codex). 보고서: plan/reports/P15-01-r1.md. Office 2016 quality 규칙 포함 전체 15파일 427 checks 통과.
- 2026-07-03 P15-01 IN-PROGRESS (Codex). 시작 HEAD: 8baf6ca.
- 2026-07-03 P14-01 AWAITING-REVIEW (Codex). 보고서: plan/reports/P14-01-r1.md. 신규 schedule store 테스트 포함 전체 15파일 421 checks 통과.
- 2026-07-03 P14-01 IN-PROGRESS (Codex). 시작 HEAD: e3021a0.
- 2026-07-03 P13-02 AWAITING-REVIEW (Codex). 보고서: plan/reports/P13-02-r1.md. 신규 work command 테스트 포함 전체 14파일 368 checks 통과.
- 2026-07-03 P13-02 IN-PROGRESS (Codex). 시작 HEAD: c61e0db.
- 2026-07-03 P12-02 AWAITING-REVIEW (Codex). 보고서: plan/reports/P12-02-r1.md. 신규 browser adapter 테스트 포함 전체 13파일 통과.
- 2026-07-03 P12-02 IN-PROGRESS (Codex). 시작 HEAD: d0e0b56.
- 2026-07-03 P09-02 AWAITING-REVIEW (Codex). 보고서: plan/reports/P09-02-r1.md. 전체 12파일 339 checks 통과.
- 2026-07-03 P09-02 IN-PROGRESS (Codex). 시작 HEAD: e8ea04e.
- 2026-07-03 Fable 리뷰: P09-01 r2 APPROVED (셸 오버라이드 검증, 20 checks) → P09-02 READY. 보고서 템플릿에 "1.5 사용자 체감 변화" 선택 섹션 정식화.
- 2026-07-03 P09-01 r2 AWAITING-REVIEW (Codex). 보고서: plan/reports/P09-01-r2.md. env shell override 필수 수정 반영.
- 2026-07-03 P09-01 r2 IN-PROGRESS (Codex). reviews/P09-01-r1.md 필수 수정 반영 시작. 시작 HEAD: 965e9fb.
- 2026-07-03 Fable 배치 리뷰: P12-01/P13-01 APPROVED → P12-02/P13-02 READY. P09-01 CHANGES-REQUESTED (os.environ 프로필 오버라이드 — reviews/P09-01-r1.md). 전 테스트 12파일 329 checks 재검증.
- 2026-07-03 P13-01 AWAITING-REVIEW (Codex). 보고서: plan/reports/P13-01-r1.md.
- 2026-07-03 P13-01 IN-PROGRESS (Codex). 시작 HEAD: b7d8441.
- 2026-07-03 P12-01 AWAITING-REVIEW (Codex). 보고서: plan/reports/P12-01-r1.md.
- 2026-07-03 P12-01 IN-PROGRESS (Codex). 시작 HEAD: 142f437.
- 2026-07-03 P09-01 AWAITING-REVIEW (Codex). 보고서: plan/reports/P09-01-r1.md.
- 2026-07-03 P09-01 IN-PROGRESS (Codex). 시작 HEAD: ce412af.
- 2026-07-03 보드 생성 (Fable). READY: P09-01, P10-01, P12-01, P13-01, P14-01, P15-01, P17-01, P18-01
