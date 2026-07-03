# company_check v2 — 업무 시나리오 실동작 결과 (2026-07-03 17:24, 회사 PC, sanitized)

## 시나리오 판정: 4/6 성공, 실패 2건 원인 특정

| # | 시나리오 | 결과 | 근거/의미 |
|---|----------|------|-----------|
| ① | **LLM native tool 왕복** | ✅ | EXAONE tool_calls 요청 → read_file 실행 → 결과 반환 → **최종 답변이 "시험 항목B 13.9 불합격"을 정확히 추출**. finish_reason=tool_calls, id="N/A"(자체발급 필요 재확인). **real 업무 자동화 회로의 직접 실증** — P11-A 왕복 프로토콜(assistant.tool_calls 메시지 + role:"tool" 반환)이 이 형식 그대로 동작함 |
| ② | Excel 매크로 주입+실행 | ✅ | VBComponents.Add→AddFromString→xl.Run→A1=42. **P15-02 자동주입 실증 완료** |
| ③ | MATLAB -batch 계산 | ✅ | mean=12.50 max=13.90, 21.6s (기동 포함) |
| ④ | HWP 문서 생성+저장 | ✅ | InsertText+SaveAs 성공 (HWP 10.0.0.14727) |
| ⑤ | Outlook 폴더 read | ❌ | **timeout 40s** — COM 접속 자체는 성공(16.0.0.5507)했으나 GetNamespace/GetDefaultFolder에서 대기. 추정: DispatchEx 새 인스턴스가 프로필 선택/보안 프롬프트 대기. **P15-03 지침: GetActiveObject(실행 중 Outlook) 우선, 미실행 시 안내 반환** |
| ⑥ | AutoCAD accoreconsole | ❌ | exit 53 "ERROR: ErrorStatus=53" (5.6s — **구동 자체는 됨**). 원인: `/i <시작 도면>` 없이 빈 세션에서 SAVEAS 시도한 스크립트 설계. **P16-02 지침: 템플릿/사본 dwg를 /i로 지정 필수, 출력은 UTF-16LE 디코딩** |

## 기타

- gateway 재확인: 3라우트 200 (87~121ms), function calling/스트리밍/think_on 동일.
  512토큰 7.1s (이전 3.7s — 서버 부하 변동, 실용 범위).
- OpenCode: 여전히 구 런처 (PURE/플러그인차단 env 전부 False, opencode.json 없음)
  → **새 아티팩트 재설치가 남은 유일한 조치** (기동 시간 판정 포함).

## 상태 어휘 갱신

- LLM tool 왕복 / Excel 자동주입 / MATLAB batch / HWP 생성: **company validated (1회 실증)**
  — 어댑터 코드로의 정식 편입과 반복 검증은 해당 task(P11-A/P15-02/P16-02/P16-04)에서.
- Outlook read / AutoCAD batch: 접근법 수정 필요 (원인 특정됨, 차단 아님).
