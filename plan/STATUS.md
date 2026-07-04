# STATUS — 작업 보드 (유일한 진행 상태 진실 소스)

- 워커: **위에서부터 첫 READY 작업 1개만** 잡는다. 본인 행의 [상태]/[보고서] 칸만 수정.
- APPROVED 전환은 Fable만. 선행이 전부 APPROVED 되면 Fable이 BLOCKED→READY로 바꾼다.
- 환경 태그: ANY(아무 PC) / LOCAL-LLM(Ollama 필요) / CHROME / EXCEL / INTERNET / COMPANY / HUMAN(사람 개입) / FABLE-ONLY

| ID | 제목 | 담당 | 선행 | 환경 | 상태 | 보고서 | 리뷰 |
|----|------|------|------|------|------|--------|------|
| P00-01 | 환경 probe 실행/업로드 (probe/README.md) | **human** | — | 집+회사 | APPROVED | probe/results/ r1~r3 | 잔여는 P00-03 이관 |
| P00-02 | OpenCode 공식 문서 연동 조사 | **fable** | — | INTERNET | APPROVED | docs/OPENCODE_INTEGRATION.md | (Fable 직접) |
| P00-03 | 회사 real-mode 실측 팩 (NEXT_ONSITE.md) | **human** | — | COMPANY | READY | | |
| P09-01 | LLM provider 프로필/env 완전 오버라이드 | codex | — | ANY | APPROVED | plan/reports/P09-01-r2.md | plan/reviews/P09-01-r2.md |
| P09-02 | 작업 유형→라우트 자동 선택 + 진단 | codex | P09-01 | ANY | APPROVED | plan/reports/P09-02-r1.md | plan/reviews/P09-02-r1.md |
| P09-03 | real-LLM 스모크 테스트 + doctor + 실측 | codex | P09-02 | LOCAL-LLM(옵션) | APPROVED | plan/reports/P09-03-r3.md | plan/reviews/P09-03-r3.md |
| P10-01 | git 히스토리 내부 hostname purge | fable | — | FABLE-ONLY | APPROVED | plan/reviews/P10-01-r1.md | plan/reviews/P10-01-r1.md |
| P11-A | lig_runtime native function calling(tools) 경로 | codex | P09-02 | ANY | APPROVED | plan/reports/P11-A-r1.md | plan/reviews/P11-A-r1.md |
| P11-01 | weak-model capability-floor 하네스 | codex | P09-03, P11-A | ANY | APPROVED | plan/reports/P11-01-r1.md | plan/reviews/P11-01-r1.md |
| P11-02 | floor 실측 + 파서/프롬프트 보강 | codex | P11-01 | LOCAL-LLM | APPROVED | plan/reports/P11-02-r1.md | plan/reviews/P11-02-r1.md |
| P12-01 | stdlib WebSocket 미니 클라이언트 | codex | — | ANY | APPROVED | plan/reports/P12-01-r1.md | plan/reviews/P12-01-r1.md |
| P12-02 | 브라우저 CDP 어댑터 + chrome-debug.bat | codex | P12-01 | ANY | APPROVED | plan/reports/P12-02-r1.md | plan/reviews/P12-02-r1.md |
| P12-03 | CDP 실측 + available 전환 | codex | P12-02 | CHROME | APPROVED | plan/reports/P12-03-r1.md | plan/reviews/P12-03-r1.md |
| P13-01 | approval(승인 게이트) + audit(감사 로그) 모듈 | codex | — | ANY | APPROVED | plan/reports/P13-01-r1.md | plan/reviews/P13-01-r1.md |
| P13-02 | `work` 오케스트레이터 subcommand E2E | codex | P13-01 | ANY | APPROVED | plan/reports/P13-02-r1.md | plan/reviews/P13-02-r1.md |
| P14-01 | schedule store + 결정적 날짜 파서 | codex | — | ANY | APPROVED | plan/reports/P14-01-r1.md | plan/reviews/P14-01-r1.md |
| P14-02 | schedule CLI + capability 등록 | codex | P14-01 | ANY | APPROVED | plan/reports/P14-02-r2.md | plan/reviews/P14-02-r2.md |
| P14-03 | 아침 브리핑 + 리마인더 BAT | codex | P14-02 | ANY | APPROVED | plan/reports/P14-03-r1.md | plan/reviews/P14-03-r1.md |
| P14-04 | 회의록(meeting_minutes) capability | codex | P14-02 | ANY | APPROVED | plan/reports/P14-04-r2.md | plan/reviews/P14-04-r2.md |
| P14-05 | 주간보고 초안(weekly_report) | codex | P13-01, P14-02 | ANY | APPROVED | plan/reports/P14-05-r2.md | plan/reviews/P14-05-r2.md |
| P15-01 | Office 2016 호환 quality 규칙 | codex | — | ANY | APPROVED | plan/reports/P15-01-r1.md | plan/reviews/P15-01-r1.md |
| P15-02 | excel_com 어댑터 (사본 정책) | codex | P15-01, P13-01 | ANY | APPROVED | plan/reports/P15-02-r2.md | plan/reviews/P15-02-r2.md |
| P15-03 | outlook_com 어댑터 (일정/메일 read) | codex | P15-02, P14-02 | ANY | APPROVED | plan/reports/P15-03-r2.md | plan/reviews/P15-03-r2.md |
| P15-04 | word/ppt 변환 action + 집 Excel 실측 | codex | P15-02 | EXCEL | APPROVED | plan/reports/P15-04-r1.md | plan/reviews/P15-04-r1.md |
| P16-01 | matlab_automation capability + .m 생성기 | codex | P15-01 | ANY | APPROVED | plan/reports/P16-01-r2.md | plan/reviews/P16-01-r2.md |
| P16-02 | matlab -batch / AutoCAD accoreconsole 어댑터 | codex | P16-01 | ANY | APPROVED | plan/reports/P16-02-r3.md | plan/reviews/P16-02-r3.md |
| P16-03 | simulation_automation (Fluent journal) + fluent_batch | codex | P16-01 | ANY | APPROVED | plan/reports/P16-03-r2.md | plan/reviews/P16-03-r2.md |
| P16-04 | hwp_com + solidworks_com 어댑터 | codex | P15-02 | ANY | APPROVED | plan/reports/P16-04-r1.md | plan/reviews/P16-04-r1.md |
| P17-01 | xlsx 입력 ingest (openpyxl optional) | codex | — | ANY | APPROVED | plan/reports/P17-01-r1.md | plan/reviews/P17-01-r1.md |
| P17-02 | 의존성 prefetch + SHA256 확정 | fable | P16-04 | INTERNET | APPROVED (파일럿 wheel 8종 resolved; llama/whisper/ffmpeg는 deferred=파일럿 불필요) | plan/reports/P17-02-r1.md | (Fable 직접) |
| P17-03 | 반입 번들 build + setup.bat + 체크리스트 | fable | P17-02 | ANY | APPROVED (파일럿 번들 = source + wheel 8종, 완전 빌드 가능) | plan/reports/P17-03-r1.md | (Fable 직접) |
| P17-04 | 오프라인 설치 리허설 (네트워크 차단) | human+codex | P17-03 | HUMAN | READY(사전점검 자동화 완료 — 사람 air-gap 실행 대기) | docs/OFFLINE_REHEARSAL.md | |
| P18-01 | secret 스캔 pre-commit 스크립트 | codex | — | ANY | APPROVED | plan/reports/P18-01-r1.md | plan/reviews/P18-01-r1.md |
| P18-02 | RUNBOOK + audit 순환 + doctor 운영 섹션 | fable | P13-01 | ANY | APPROVED | plan/reports/P18-02-r2.md | plan/reviews/P18-02-r2.md |
| P19-01 | 회사 파일럿 체크리스트/기록 양식 준비 | codex | P14-03, P15-02, P16-02 | ANY | APPROVED | plan/reports/P19-01-r1.md | plan/reviews/P19-01-r1.md |
| P19-02 | 회사 파일럿 12종 실측 | human+fable | P19-01, P17-04 | COMPANY+HUMAN | BLOCKED | | |
| P20-01 | 음성 입력 구현 (whisper.cpp) | codex | P19-02 | ANY | BLOCKED | | |

## 이력 (상태 변경 시 한 줄씩 추가 — 최신이 위)

- 2026-07-04 **P17-02/P17-03 파일럿 스코프로 종결 (Fable 직접, 사용자 확인)**: 사용자 지적("회사는 오프라인 내부망 — GitHub 어차피 불가") + 코드 근거(`lig_providers.py`: 기본 프로필 `company_gateway`가 **사내 게이트웨이로 LLM 서빙**, `local_openai`는 dev/집 대체 경로)로 판정. **차단됐던 GitHub 바이너리 3종(llama.cpp/whisper.cpp/ffmpeg)은 파일럿에 불필요** → `dependencies.json` status `PENDING_HOME_PREFETCH`→**`deferred`**(로컬서빙/음성 전용, 해당 프로필 채택 시에만 집 PC prefetch). llm-gguf/asr-model도 동일 후순위. **파일럿 번들 실필요 = office/COM wheel 8종(전부 resolved) → 집 PC 다운로드 0**. test에 deferred 검증(가짜 해시 금지·사유 명시)+wheel-all-resolved 파일럿 스코프 체크 추가 → **`ALL 66 CHECKS PASSED`**. **결과: P17-02/P17-03 사용자 결정 대기 해소, 파일럿 반입 경로 완전 자립.** 음성(P20)·로컬서빙 도입 시 3종은 그때 집 PC에서 채우면 build_bundle이 자동 포함(코드 변경 불필요).

- 2026-07-04 **P17-04 사전점검 자동화 (Fable 직접)**: 리허설의 클라우드 가능 절반 구현 → `release/rehearsal_check.py`(stdlib) + `docs/OFFLINE_REHEARSAL.md`. **rehearsal_check**: ① build_bundle 유효 zip 실측 ② setup.bat 오프라인 안전 하드검사(`--no-index`만·network fetch/ExecutionPolicy Bypass 없음) ③ runtime-network **advisory 감사** — agent_ops `*.py`의 아웃바운드 지점 16곳을 file:line으로 나열, localhost/env=OK·나머지=REVIEW로 분류(air-gap 캡처 감시 목록). **실측 `ALL 82 PRE-FLIGHT CHECKS PASSED`**. **OFFLINE_REHEARSAL.md**: 0(자동 사전점검)→1(번들)→2(네트워크 차단)→3(설치+트래픽 캡처)→4(복구+기록) 절차, **P00-02 telemetry 갭을 3절 pktmon/netstat 캡처로 종결**하도록 연결. 남은 것은 **사람 air-gap 실행**(어댑터 차단은 기계 불가) → BLOCKED 해제 READY. 코드 변경은 release/·docs/만(하드게이트 무관).

- 2026-07-04 **P00-02 APPROVED (Fable 직접)**: OpenCode 공식 문서 4항목 조사 완료 → `docs/OPENCODE_INTEGRATION.md`. **① provider**: `@ai-sdk/openai-compatible` + `{env:LIG_API_KEY}` 치환(비밀 미하드코딩) `[확인됨]`. **② 확장점**: OpenCode 플러그인 hook은 자체 프로세스 내부용, **외부 에이전트 런타임 오케스트레이션 확장점 없음** → **agent_ops 병행 CLI 노선 확정** `[확인됨]`. **③ 오프라인**: autoupdate/share/mdns 차단 `[확인됨]`, **telemetry 필드는 문서에 없음 → P17-04 네트워크 캡처로 실측 이관**. **④ permission**: TUI tool 게이트(allow/ask/deny, last-match-wins)와 agent_ops 하드 게이트는 **직교 — 둘 다 유지** `[확인됨]`. DoD 충족(항목별 출처+확인/추정 표기, 통합 권고 1개). 코드 변경 없음.

- 2026-07-04 **P17-03 부분완료 (Fable 직접)**: build_bundle.py(stdlib zip+MANIFEST_SHA256, secret 반입 거부) + setup.bat(오프라인 `pip --no-index`+단계별 실패처리) + BRING_IN_CHECKLIST.md 구현. test_release_manifest에 build 검증 추가 → `ALL 62 CHECKS PASSED`(295 소스 zip 실측). 완전 번들은 P17-02 잔여 3종 채운 뒤 재빌드. 23개 중 20 exit 0. reports/P17-03-r1.md.

- 2026-07-04 **P17-02 부분완료 (Fable 직접)**: wheel 8종 pip 실측 SHA256 + 모델 3파일 HF LFS pointer 공식 SHA256 = **11/14 resolved**. `dependencies.json:prefetch_files` + `verify_prefetch.py`(stdlib) + `test_release_manifest.py`(54 checks, no-network) + `.gitignore release/prefetch/` 커밋. E2E: wheel 8종 prefetch/에 넣고 verify → 전부 해시 일치 OK. **잔여 3종**(llama.cpp/whisper.cpp/ffmpeg GitHub 릴리스): 클라우드 **proxy allowlist가 GitHub 릴리스 차단** → codex도 불가, **집/개발 PC에서 다운로드+certutil로 확정** 필요(해시 날조 금지). 전체 23개 중 20개 exit 0. 상세: reports/P17-02-r1.md. **사용자 결정 요청**: 3종을 집 PC에서 받을지/회사 기설치로 대체할지. P17-03은 3종 resolved 후 완전 번들.

- 2026-07-04 **Fable 직접 구현 개시**(사용자 지시: 남은 작업은 Codex 대신 Fable). **P18-02 r2 APPROVED**(runbook 필드를 코드 루트 기준으로 수정, relocated data root에서 `runbook: True` 실측, 회귀 check 추가 → approval_audit 21 checks — reports/P18-02-r2.md, reviews/P18-02-r2.md). 재검증: 22개 중 19개 exit 0. 다음 Fable 직접: **P17-02(의존성 prefetch+SHA256, INTERNET)**.

- 2026-07-04 Fable 리뷰 19차(3건): **P16-04 APPROVED**(hwp/solidworks available=False·부재안전·HWP 신규파일·SW 사본+무저장+manual_import·subprocess 우려 없음, 46 static 통과 — reviews/P16-04-r1.md)→**P17-02 READY**(INTERNET). **P19-01 APPROVED**(gateway-smoke.bat validate 재사용+exit2·PILOT_RECORD 12행·PILOT_DAY1 실파일 링크, BAT는 Windows 전용이라 로직 정독+워커 mock 대조 — reviews/P19-01-r1.md). **P18-02 CHANGES-REQUESTED**(소규모 1건: doctor `runbook` 필드가 데이터 ROOT 기준이라 relocated install에서 shipped RUNBOOK을 false 오보고 — P15-03과 동류 CODE_ROOT 계열. audit 회전·operations 6필드·secret-free·RUNBOOK 7행은 실측 정상. 되는 방법=`parents[1]` 코드 루트, 리뷰어 검증 — reviews/P18-02-r1.md). 재검증: 22개 중 19개 exit 0(bench 213, office 46 static, approval 20). 피드백: shipped 아티팩트=코드 루트, 사용자 데이터=데이터 루트 원칙. Codex 다음: **P18-02 r2 → P17-02(INTERNET)**.

- 2026-07-04 P19-01 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P19-01-r1.md. PILOT_DAY1/PILOT_RECORD/gateway-smoke.bat 추가, 12종 업무 명령+성공 기준 사전 기입, gateway-smoke 미설정 exit 2 및 전체 22개 테스트 파일 통과.
- 2026-07-04 P19-01 IN-PROGRESS (Codex). 시작 HEAD: 72137a4. 회사 파일럿 day1 문서/기록 양식/gateway smoke BAT 작업 시작.
- 2026-07-04 P18-02 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P18-02-r1.md. RUNBOOK 7개 운영 증상 표, audit 회전(.bak) 및 doctor operations 섹션 추가. approval/audit 20 checks/doctor manual smoke/전체 22개 테스트 파일 통과.
- 2026-07-04 P18-02 IN-PROGRESS (Codex). 시작 HEAD: 65a801d. RUNBOOK + audit 순환 + doctor 운영 섹션 작업 시작.

- 2026-07-04 P16-04 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P16-04-r1.md. hwp_com md_to_hwp 신규 파일 변환 adapter + solidworks_com 사본 문서 run_macro adapter 추가, office adapters 42 checks/capability bench 213 checks/전체 22개 테스트 파일 통과.

- 2026-07-04 P16-04 IN-PROGRESS (Codex). 시작 HEAD: 513641b. hwp_com + solidworks_com 어댑터 작업 시작.

- 2026-07-04 Fable 리뷰 18차: **P16-03 r2 APPROVED**(bare `해석`/`journal` 제거+도메인어(cfd/fea) 채택, 리뷰 설계 NEGATIVE_CORPUS 10문장 메타 체크 그대로 회귀화. 실측: 누출 **0/10**, 양성 4건 유지, bench 213 — reviews/P16-03-r2.md). 재검증: 22개 중 19개 exit 0, Windows 전용 3개만 RED. **키워드 오라우팅 계열이 클래스 단위로 봉쇄됨**(이후 재발은 리뷰 없이 bench 차단). Codex 다음: **P16-04 → P18-02 → P19-01**.

- 2026-07-04 P16-03 r2 AWAITING-REVIEW (Codex). 보고서: plan/reports/P16-03-r2.md. simulation_automation keywords에서 bare `해석`/`journal` 제거, everyday negative corpus 10문장 추가. capability bench 213 checks/batch adapters 37 checks/전체 22개 테스트 파일 통과.

- 2026-07-04 P16-03 r2 IN-PROGRESS (Codex). reviews/P16-03-r1.md 필수 수정(simulation keyword bare `해석`/`journal` 제거 + everyday negative corpus) 반영 시작.

- 2026-07-04 **Fable 5 종합 점검** (사용자 요청): 건강 — 테스트 19/22 exit 0(Windows 전용 3개 제외 전부 green), secret scan 통과, 의존성 그래프 정합, 보드 26 APPROVED/4 READY/1 CHANGES-REQ/5 BLOCKED. **결함 패턴 정량화**(리뷰 17차): 키워드 오라우팅 4회(최다)·추출 오값 2회·테스트 이식성 2회·subprocess 루트 1회 — 전부 1~3라운드 수렴, 리뷰 제시 수정코드 채택률 100%. **개선 3건**: ① 일상어 NEGATIVE_CORPUS 메타 체크 설계+실측(기존 수정 8문장 ok/현 누출 2문장만 LEAK — 이빨 확인)→P16-03 r2 요구로 영구화, 이후 키워드 재발은 리뷰 없이 bench가 차단. ② self-review 스킬에 반복 결함 체크리스트 4종 추가(워커 제출 전 자가 차단). ③ 파일럿까지 남은 경로 확정: **P16-03 r2 → P16-04 → P18-02 → P19-01**(codex, ANY) → P17-02(INTERNET)→P17-03→P17-04(HUMAN)→P19-02(COMPANY) + P00-02(fable)/P00-03(human)/Windows baseline(NEXT_ONSITE). 판정: **순항** — 코어/비서/어댑터 축 완성, 남은 것은 ANY 4건+반입 체인+실측.

- 2026-07-04 Fable 리뷰 17차: **P16-03 r1 CHANGES-REQUESTED**(키워드 `해석`(일상어)+`journal` 광범위 매칭 → `이 데이터 해석해줘`·`회의 내용 해석`·`journal 정리` 등이 fluent_journal/ansys_script 스퓨리어스 생성. `.m`/`minutes`/`weekly`에 이은 4번째지만 `해석`은 일상어라 영향 최대. **task 스펙이 그 키워드를 지정한 결함이라 task도 Fable 정정**. 되는 방법=도메인어만(ansys/fluent/시뮬레이션/메카니컬/…+cfd/fea)+negative check, 리뷰어 실측 — reviews/P16-03-r1.md). 확인: fluent_journal/ansys_script 골격·공학책임 경고 quality 강제·fluent available=False·부재안내·테스트 POSIX 이식성(36 checks) 전부 정상. 재검증: 22개 중 19개 exit 0(bench 203, Windows 전용 3개만 RED). 피드백: 한국어 일상어 키워드가 영어보다 위험. Codex 다음: **P16-03 r2 → P18-02 → P16-04**.

- 2026-07-04 P16-03 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P16-03-r1.md. simulation_automation capability + fluent_journal/ansys_script artifact kind + fluent_batch adapter 추가, batch adapters 37 checks/capability bench 203 checks/전체 22개 테스트 파일 통과. hard gate: artifact kind 추가로 리뷰 전 auto-advance 중단.

- 2026-07-04 P16-03 IN-PROGRESS (Codex). 시작 HEAD: 351706a. simulation_automation Fluent journal + fluent_batch 작업 시작.

- 2026-07-04 Fable 리뷰 16차: **P16-02 r3 APPROVED**(리뷰 검증 octal escape `\377\376E\000…` 그대로 채택. 실측: test_batch_adapters POSIX `ALL 23 CHECKS PASSED`, hard-gate artifact-kind check가 이제 리뷰 플랫폼서 실행·통과). 재검증: **22개 중 19개 exit 0**(RED는 Windows 전용 3개뿐, batch_adapters GREEN 복귀). 선행 해제: **P19-01 READY**(P14-03·P15-02·P16-02 전부 APPROVED). 피드백: fake-exe 패턴(POSIX octal+hard-gate check 앞으로)을 P16-03/04 템플릿으로. Codex 다음: **P18-02 → P16-03 → P16-04 → P19-01**.

- 2026-07-04 P16-02 r3 AWAITING-REVIEW (Codex). 보고서: plan/reports/P16-02-r3.md. POSIX fake exit-53 stdout emit을 dash 호환 octal escape로 변경, batch adapters 24 checks/capability bench 193 checks/전체 22개 테스트 파일 통과.

- 2026-07-04 P16-02 r3 IN-PROGRESS (Codex). reviews/P16-02-r2.md 필수 수정(exit-53 POSIX fake stdout octal escape) 반영 시작.

- 2026-07-04 Fable 리뷰 15차: **P16-02 r2 CHANGES-REQUESTED**(진척 큼: `_write_fake_exe` .sh/.cmd 분기·copy 불변·utf16 stdout nt가드 통과. 잔여 1곳: exit-53 fake의 POSIX unix_body가 `printf '\xNN'`인데 dash가 `\x` 미해석→리터럴 출력→log_tail 깨져 `ErrorStatus=53` check 실패, 파일 여전히 POSIX RED. 어댑터는 정상(ok False·exit 53·returncode 53). 되는 방법=octal `\NNN`(리뷰어 실측: ff fe 45 00…→`ErrorStatus=53`) 또는 log 내용만 nt가드 — reviews/P16-02-r2.md). 재검증: 22개 중 18개 exit 0. 피드백: 셸 printf `\x`는 비이식적, octal `\NNN` 쓸 것. Codex 다음: **P16-02 r3 → P18-02 → P16-03/04**.

- 2026-07-04 P16-02 r2 AWAITING-REVIEW (Codex). 보고서: plan/reports/P16-02-r2.md. test_batch_adapters fake exe를 Windows .cmd / POSIX .sh+chmod 분기로 수정하고 UTF-16LE 내용 assertion은 nt 가드 처리. batch adapters 24 checks/capability bench 193 checks/capability floor 11 checks/전체 22개 테스트 파일 통과.

- 2026-07-04 P16-02 r2 IN-PROGRESS (Codex). reviews/P16-02-r1.md 필수 수정(fake exe POSIX 이식성 + UTF-16 assertion nt 가드) 반영 시작.

- 2026-07-04 정책: **pip 설치 허용**(사용자 승인). PROTOCOL §3.4 개정 — 개발/집/리뷰 PC에서 필요한 라이브러리를 `pip install`로 자유롭게 설치해 SKIP 대신 실경로 검증. 가드레일: dependencies.json 등록 필수(회사는 오프라인=prefetch wheel로만 반입), 코어는 stdlib-only 유지, 어댑터/ingest는 optional-import 부재 안내 유지. 리뷰 환경에 openpyxl 설치 → bench 191→**193**(워커와 동일 분기, 이전 리뷰들의 191/193 불일치 해소). pywin32는 리눅스 배포판 없음 → COM 어댑터는 리뷰 env에서 항상 부재 경로(불가피).

- 2026-07-04 Fable 리뷰 14차: **P15-04 r1 APPROVED**(office available=False 유지=hard gate, home_smoke 정직 표기, 신규파일 정책 memo_2.docx·excel 라우팅 보존 실측. 집 Excel *live* 왕복은 리뷰 env에 Excel 없어 독립재현 불가—home_smoke로 정직 스코프, Office 2016은 P19 — reviews/P15-04-r1.md). **P16-02 r1 CHANGES-REQUESTED**(테스트 이식성만: fake exe가 `.cmd`라 POSIX 하드 실패→artifact-kind hard-gate check가 리뷰 플랫폼서 실행 불가. 어댑터/artifact 실체는 리눅스 개별 실측 전부 통과: 부재안내·DWG사본 원본불변·UTF-16·exit53·autocad_script 생성/품질/QSAVE차단·available=False. 되는 방법=`.sh`/`.cmd` 분기+UTF-16 assertion만 nt가드+hard-gate check를 앞으로, 리뷰어 조각 검증 — reviews/P16-02-r1.md). 재검증: 22개 중 18개 exit 0(batch_adapters+Windows 전용 3개 RED). 피드백: OS 전용 블록 뒤에 hard-gate check 두지 말 것. Codex 다음: **P16-02 r2 → P18-02 → P16-03/04**.

- 2026-07-04 P16-02 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P16-02-r1.md. matlab_batch -batch adapter + autocad_batch accoreconsole 사본 DWG adapter + autocad_script artifact kind/quality 추가, batch adapters 24 checks/capability bench 193 checks/전체 22개 테스트 파일 통과. hard gate: artifact kind 추가로 리뷰 전 auto-advance 중단.

- 2026-07-04 P16-02 IN-PROGRESS (Codex). 시작 HEAD: 8cc7d91. matlab -batch / AutoCAD accoreconsole subprocess 어댑터 작업 시작.

- 2026-07-04 P15-04 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P15-04-r1.md. office_convert md_to_docx/spec_to_pptx 추가, 집 Excel 사본 왕복/원본 해시 불변/Word·PPT 파일 열림/프로세스 정리 실측, office adapters 29 checks/capability bench 193 checks/office live smoke 16 checks/전체 21개 테스트 파일 통과.

- 2026-07-04 P15-04 IN-PROGRESS (Codex). 시작 HEAD: 2f9c3ee. Excel/Word/PowerPoint ProgID 확인 후 Office 변환 action + 집 Excel 실측 작업 시작.

- 2026-07-04 Fable 리뷰 13차: **P15-03 r2 APPROVED**(리뷰 검증 코드 `CODE_ROOT`(parents[2]) cwd+PYTHONPATH 그대로 채택. 실측: 이전 RED 조건 AGENTOPS_ROOT=데이터폴더에서 read_calendar/inbox/sync 3개 다 정상 안내로 복구, office_adapters GREEN 26 checks). 재검증: 20개 중 17개 exit 0, Windows 전용 3개만 RED(diff 무접촉). 피드백: subprocess 격리 어댑터(P16-02 등)에 동일 교훈 적용. 신규 READY 없음. Codex 다음: **P18-02 → P16-02 → P16-03/04 → P15-04**.

- 2026-07-04 P15-03 r2 AWAITING-REVIEW (Codex). 보고서: plan/reports/P15-03-r2.md. outlook_com subprocess cwd/PYTHONPATH를 CODE_ROOT로 고정, office adapters 22 checks/schedule store 69 checks/capability bench 193 checks/전체 20개 테스트 파일 통과.

- 2026-07-04 P15-03 r2 IN-PROGRESS (Codex). reviews/P15-03-r1.md 필수 수정(subprocess cwd/PYTHONPATH 코드 루트 고정) 반영 시작.

- 2026-07-04 Fable 리뷰 12차: **P15-03 r1 CHANGES-REQUESTED**(실측 버그: `_run_child`가 자식을 `cwd=str(ROOT)`=데이터 루트에서 띄워 `-m agent_ops...` import 실패→"no JSON"으로 read_calendar/inbox/sync 전부 깨짐. AGENTOPS_ROOT를 데이터폴더로 두면 실사용에서도 발생. `test_office_adapters.py`가 AGENTOPS_ROOT=tmp라 리뷰 env에서 RED 재현. 되는 방법=CODE_ROOT(parents[2])를 cwd+PYTHONPATH로, 리뷰어 검증 — reviews/P15-03-r1.md). 확인: GetActiveObject 전용·서브프로세스 격리·sync 중복방지(1/0)·send fail-closed dangerous·비노출·available=False 전부 실측 정상. 재검증: 20개 중 16개 exit 0(office_adapters 버그+Windows 전용 3개만 RED, bench 191/schedule 69). 피드백: 격리 subprocess는 부모 sys.path 미상속 — 코드루트를 cwd+PYTHONPATH로 명시. Codex 다음: **P15-03 r2 → P18-02 → P16-02**.

- 2026-07-04 P15-03 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P15-03-r1.md. outlook_com active-instance-only read adapter + schedule sync-outlook CLI 추가, office adapters 22 checks/schedule store 69 checks/capability bench 193 checks/전체 20개 테스트 파일 통과.

- 2026-07-04 P15-03 IN-PROGRESS (Codex). 시작 HEAD: 0b0c7b6. Outlook COM 어댑터 read/sync/inbox/dangerous send 분류 작업 시작.

- 2026-07-04 Fable 리뷰 11차: **P14-05 r2 APPROVED**(리뷰 검증 코드 `weekly`→`weekly report` + biweekly negative check 그대로 채택. 실측: biweekly·this week 차단, 양성 4건 유지 — reviews/P14-05-r2.md). 재검증: 20개 중 17개 exit 0(bench 191=193−openpyxl 2), Windows 전용 3개 diff 무접촉. P14-05는 리프 — 신규 READY 없음. Codex 다음 READY: P18-02, P15-03/04, P16-02~04. **P14 시리즈(01~05) 전부 APPROVED.**

- 2026-07-04 P14-05 r2 AWAITING-REVIEW (Codex). 보고서: plan/reports/P14-05-r2.md. weekly bare keyword를 weekly report로 경계화하고 biweekly negative bench 추가, capability bench 193 checks/secretary 37 checks/전체 20개 테스트 파일 통과.

- 2026-07-04 P14-05 r2 IN-PROGRESS (Codex). reviews/P14-05-r1.md 필수 수정(weekly bare keyword 경계화 + biweekly negative bench) 반영 시작.

- 2026-07-04 Fable 리뷰 10차: **P14-05 r1 CHANGES-REQUESTED**(영어 키워드 `weekly` bare substring이 `biweekly 회의 잡아줘` 오라우팅 — `.m`/`minutes`에 이은 3번째 동류, hard gate라 동일 기준 적용. 되는 방법=`weekly`→`weekly report` 경계화+negative check, 리뷰어 실측 검증 — reviews/P14-05-r1.md). 확인: 3개 원천(audit/schedule/artifacts) 반영·기간 필터·초안 TODO E2E 정상, audit `task` 필드 실스키마 일치. 재검증: 20개 중 17개 exit 0(bench 190=192−openpyxl 2), Windows 전용 3개 diff 무접촉. 피드백: bare 영어 키워드 self-check 습관화. Codex 다음: **P14-05 r2 → P18-02 → P15-03 → P16-02**.

- 2026-07-04 **P10-01 APPROVED (Fable 실행)**: 내부 gateway hostname을 git-filter-repo로 전 히스토리 치환(194 커밋 재작성). 백업 미러 2벌 후 **전 16개 브랜치(main·rebuild/ 포함) force-push** → 재클론 검증 **브랜치·main·활성 PR #8 전부 hostname 0회**, 원커밋 67e0028·be6e7d1 소멸. **잔여**: 원커밋 be9f981이 닫힌 PR #1/#2/#4의 `refs/pull/*` 서버 스냅샷에만 도달 가능(클라이언트 재작성 불가 — read-only ref). 완전 제거는 소유자의 닫힌 PR 삭제 또는 서버 gc 필요(플랫폼 측, 세션 밖). 전 브랜치 재작성으로 **모든 열린 세션은 재클론/hard-reset 필요**. 상세: reviews/P10-01-r1.md. 로컬 rebuild/는 재작성본으로 동기화 완료.

- 2026-07-04 P14-05 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P14-05-r1.md. weekly_report capability + agentops weekly 초안 생성 추가, secretary 37 checks/capability bench 192 checks/전체 20개 테스트 파일 통과.

- 2026-07-04 Fable 전체 점검 (사용자 요청): 보드 37건(APPROVED 21/READY 10/BLOCKED 6) 의존성 그래프 **정합**(잘못 열린 READY 0, BLOCKED 6건 모두 선행 미충족 확인). 현재 트리 **secret scan 통과**(누출 0 — 내부 hostname은 git *history*에만 존재=P10-01 범위). 조치: NEXT_ONSITE에 **Windows 회귀 전수 baseline** 항목 신설(리뷰가 리눅스라 agent_cli/encoding_paths/probes 3개를 독립 재현 못 함 — 파일럿 전 1회 Windows 전수 필요). 미해결 스레드 3건 명시 → ① **P10-01 hostname purge**: FABLE-ONLY·READY·보안, 그러나 history rewrite+force push라 **열린 PR #8에 영향** → 사용자 go 신호 후 실행(현재 미실행). ② **P11-02 floor 66.7%**: 약모델(7B) 천장 데이터일 뿐, 회사는 강모델+native tools 확정이라 파일럿 blocker 아님, 파서 보강은 NEXT_ONSITE 실측 입력으로 추적. ③ Windows baseline(위 조치로 편입). 신규 AWAITING-REVIEW 없음, 코드 변경 없음(문서/보드만).

- 2026-07-04 Fable 리뷰 9차: **P14-04 r2 APPROVED**(리뷰가 검증 제시한 `_extract_owner`+`meeting minutes` 경계화를 워커가 그대로 채택, negative/정확성 bench 2개 회귀화. 실측: minutes 시간표현 2건 라우팅 차단+양성 3건 유지, 회의록 담당=`김대리`·`| 7월 |` 없음 — reviews/P14-04-r2.md). 권고: todo `까지` 접두 잔여 1줄 정리(검증 코드 제시, 승인 무관). 재검증: 19개 중 17개 exit 0(bench 184=186−openpyxl 2), Windows 전용 3개 diff 무접촉. 현재 AWAITING-REVIEW 없음. Codex 다음 READY: P18-02, P14-05, P15-03/04, P16-02~04.

- 2026-07-04 리뷰 프로세스 개정 (사용자 피드백 반영, Fable): 리뷰는 "안 되는 것"만 잡지 말고 **되는 방법(검증된 수정 코드)+피드백+작업계획 수정내용**을 항상 포함한다. review-template.md에 3개 섹션 신설, delegate-to-codex 스킬에 규칙 5 추가. P14-04-r1 소급 보강(검증된 `_extract_owner`/키워드 경계화 코드 + 피드백 + P14-04 task "리뷰 반영" 절).

- 2026-07-04 Fable 리뷰 8차: **P14-03 r1 APPROVED**(briefing E2E 실측 — 일정/마감 OVERDUE/액션아이템 대기필터·출처/audit 전일요약 정확, reminder BAT y-only 게이트 — reviews/P14-03-r1.md). **P14-04 r1 CHANGES-REQUESTED**(① 영어 키워드 `minutes` bare substring이 `5 minutes 후에 알려줘` 오라우팅→회의록 스퓨리어스 생성, P16-01 `.m`과 동류 ② `_meeting_actions` owner 추출이 `김대리 담당: 7월…` 패턴에서 날짜 `7월`을 담당으로 채움=그럴듯한 오값, bench substring만 봐서 누락 — reviews/P14-04-r1.md). 재검증: 19개 중 16개 exit 0(+secretary 20, bench 182=184−openpyxl 2), Windows 전용 3개 diff 무접촉. Codex 다음: **P14-04 r2 → P18-02 → 신규 READY들**.

- 2026-07-04 Fable 리뷰 7차: **P16-01 r2 APPROVED**(키워드 `.m`→`.m 스크립트`/`.m 파일` 경계화, `.md`/`.m` 7개 케이스 실측으로 오라우팅 재발 없음 + 양성 라우팅 유지, negative check 2개 회귀화 — reviews/P16-01-r2.md) → P16-02/P16-03 READY. 재검증: 19개 중 16개 exit 0(bench 171=173−openpyxl 2), Windows 전용 3개 diff 무접촉. 현재 AWAITING-REVIEW 없음. Codex 다음 READY: P18-02, P14-03~05, P15-03/04, P16-02~04.

- 2026-07-04 Fable 배치 리뷰 6차: **P14-02 r2 APPROVED**(제목 훼손·기한 오탐 필수 2건 CLI 실측 해결 재현) → P14-03/P14-04/P14-05 READY. **P15-02 r2 APPROVED**(옵션 없는 close audit 기록 실측 확인) → P15-03/P15-04(EXCEL)/P16-04 READY. **P11-02 r1 APPROVED**(리포트 경로 mock/real 분리 P11-01 요구대로 반영, 프롬프트 2193B≤2.3KB — 단 floor 66.7%로 90% 목표 미달은 미해결 갭으로 이월, 재작업 아님). **P16-01 r1 CHANGES-REQUESTED**(키워드 `.m`이 `.md` substring 오라우팅 → 문서 요청이 matlab_script 스퓨리어스 생성, hard gate — reviews/P16-01-r1.md). 재검증: 19개 중 16개 exit 0, schedule/excel/matlab 실동작 재현, Windows 전용 3개 diff 무접촉. Codex 다음: **P16-01 r2 → P18-02 → (신규 READY들)**.

- 2026-07-04 P16-01 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P16-01-r1.md. matlab_automation capability + matlab_script 생성/품질/입력 반영 추가, 전체 19개 테스트 파일 exit 0.

- 2026-07-04 P16-01 IN-PROGRESS (Codex). 시작 HEAD: 4629876.

- 2026-07-04 P11-02 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P11-02-r1.md. floor report 경로 분리, 약모델 프롬프트 보강, qwen2.5:7b-instruct 최종 20/30(66.7%) 및 전체 19개 테스트 파일 exit 0.

- 2026-07-04 P11-02 IN-PROGRESS (Codex). 시작 HEAD: 8713266.

- 2026-07-04 P15-02 r2 AWAITING-REVIEW (Codex). 보고서: plan/reports/P15-02-r2.md. close action audit 누락 필수 수정 반영, 전체 19개 테스트 파일 exit 0.

- 2026-07-04 P15-02 r2 IN-PROGRESS (Codex). reviews/P15-02-r1.md 필수 수정 반영 시작. 시작 HEAD: b9b8363.

- 2026-07-04 P14-02 r2 AWAITING-REVIEW (Codex). 보고서: plan/reports/P14-02-r2.md. 한 글자 요일/제목 훼손 필수 수정 반영, 전체 19개 테스트 파일 exit 0.

- 2026-07-04 P14-02 r2 IN-PROGRESS (Codex). reviews/P14-02-r1.md 필수 수정 반영 시작. 시작 HEAD: 413e714.

- 2026-07-03 Fable 배치 리뷰 5차: **P11-01 APPROVED**(시나리오 10종 task 원문 일치, mock 자가검증 7 checks + SKIP 재현) → **P11-02 READY**. **P14-02 CHANGES-REQUESTED**(한 글자 요일 오탐 2건 실증: 제목 훼손 "금형→형"·"검토→검" + parse_due 오탐 "언제까지인지 모르는 일"→일요일 등록 — reviews/P14-02-r1.md). **P15-02 CHANGES-REQUESTED**(옵션 없는 close가 audit 미기록 — 1건, 소규모 — reviews/P15-02-r1.md). 재검증: 19개 테스트 파일 중 16개 exit 0 + schedule/excel CLI·어댑터 실동작 재현, Windows 전용 3개는 diff 무접촉 확인. Codex 다음 순서: **P14-02 r2 → P15-02 r2 → P11-02(LOCAL-LLM) → P16-01 → P18-02**.

- 2026-07-03 P15-02 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P15-02-r1.md. excel_com copy-only adapter 추가, pywin32 부재 안전 실패와 VBProject manual_import fallback 검증, 전체 19개 테스트 파일 exit 0.

- 2026-07-03 P15-02 IN-PROGRESS (Codex). 시작 HEAD: 7e4e4fd.

- 2026-07-03 P14-02 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P14-02-r1.md. schedule CLI/capability 등록, 전체 18개 테스트 파일 exit 0.

- 2026-07-03 P14-02 IN-PROGRESS (Codex). 시작 HEAD: da85e82.

- 2026-07-03 P11-01 r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P11-01-r1.md. capability floor 하네스 추가, qwen2.5:7b-instruct 10종x3회 성공률 21/30(70.0%) 및 전체 18개 테스트 파일 exit 0.

- 2026-07-03 P11-01 IN-PROGRESS (Codex). 시작 HEAD: 6d8a35f.

- 2026-07-03 Fable 배치 리뷰 4차: **P09-03 r3 APPROVED**(Ollama qwen2.5:7b real smoke 3종 리뷰 환경에서 독립 재현 — 12 checks 실통과, `_chat_completions_url` 정규화는 회사 probe URL 형식과 정합 확인 = 회사 real-mode 잠재 404 버그 동시 수정), **P11-A r1 APPROVED**(id 자체발급/N/A 정규화/tool_call_mode 진단 델타 5종 전부 확인, payload 캡처 테스트로 id 대응 실검증). 전체 17개 테스트 파일 exit 0 재현. **P11-01 → READY** (선행 P09-03·P11-A 충족). Codex 다음 권고 순서: **P11-01 → P14-02 → P15-02 → P16-01 → P18-02**. 보드 정정: P09-03 행 보고서 링크 r2→r3 (Codex 갱신 누락분).

- 2026-07-03 P11-A r1 AWAITING-REVIEW (Codex). 보고서: plan/reports/P11-A-r1.md. native tool-call id/tool_call_id 대응 + tool_call_mode 진단, 전체 10개 회귀 통과.

- 2026-07-03 P11-A IN-PROGRESS (Codex). 시작 HEAD: 084366c.

- 2026-07-03 계획 정비·약모델 대비 (설계 Fable): 워커 모델 교체(GPT-5→5.4 mini) 대비로 READY task 지시서를 실코드 기준으로 구체화 — **P11-A 전면 재작성**(이미 구현된 기능 표 명시, 남은 델타=id/tool_call_id 발급+tool_call_mode 진단, 코드 블록 제공), P15-02(실증 COM 시퀀스+execute 계약 표), P14-02(CLI 계약), P16-01(.m 골격), P18-02(RUNBOOK 7행 표+회전 코드), P15-03(GetActiveObject+자식 프로세스 격리 패턴), P16-02(UTF-16LE 디코드+exit 53 처리). worker-loop에 규칙 2개 추가: 지시서 코드 그대로 사용/이미 구현됨 재구현 금지, auto-advance 연속 3개 한도. READY 대기열 불변: P11-A → P14-02 → P15-02 → P16-01 → P18-02.
- 2026-07-03 company_check v2 시나리오 실측 (사용자): **① LLM native tool 왕복 E2E 성공(최종 답변이 파일 내용 정확 반영)** + ② Excel 매크로 주입·실행 + ③ MATLAB 계산 + ④ HWP 생성·저장 성공. ⑤ Outlook(새 인스턴스 hang→GetActiveObject로 지침 반영) ⑥ AutoCAD(/i 필요·UTF-16 출력, 지침 반영) 원인 특정. P11-A/P15-02/P15-03/P16-02 task와 MASTER_PLAN 리스크 갱신. 결과: probe/results/company_check_20260703_r2_scenarios.md.
- 2026-07-03 P09-03 r2 AWAITING-REVIEW (Codex). 보고서: plan/reports/P09-03-r2.md. unknown-tool 시나리오 복원, 서버 off SKIP 및 전체 17 테스트 파일 447 checks/1 skip 통과.
- 2026-07-03 P09-03 r2 IN-PROGRESS (Codex). reviews/P09-03-r1.md 필수 수정 반영 시작. 시작 HEAD: 61b724f.
- 2026-07-03 Fable 배치 리뷰 3차 (리뷰 세션): P12-03 **APPROVED** (리뷰 환경 Chromium headless CDP로 4 actions 독립 재현 성공), P09-03 **CHANGES-REQUESTED** (시나리오③ unknown-tool 복원 + r2는 실행 증거 필수 — reviews/P09-03-r1.md). 재검증: 전 17 테스트 파일 중 14개 405 checks + smoke SKIP 통과(리눅스 리뷰 환경), Windows 전용 3개(agent_cli/encoding_paths/probes)는 두 diff 무접촉 확인으로 대체. P11-01 BLOCKED 유지.
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
