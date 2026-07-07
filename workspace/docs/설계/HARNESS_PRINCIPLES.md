# 하네스 엔지니어링 원칙 (우리 런타임 설계 기준)

"하네스(harness)"는 LLM 주위의 루프·도구·제약·상태를 설계하는 것 — 우리 `agent_ops`가
바로 그것이다. walkinglabs "learn-harness-engineering"(한국어 방법론)의 핵심 원칙을
우리 구성요소에 매핑해, 설계가 이 원칙을 지키는지 점검한다. (코드 도입이 아니라 설계 가이드.)

| 하네스 원칙 | 우리 구현 | 상태 |
|---|---|---|
| **닫힌 루프(closed-loop)**: 실행→검증→수정 반복, 열린 채 방치 금지 | 에이전트 루프 + `agentops verify`/`doctor` + `agent.md` 감시 프로토콜 | 있음 |
| **상태 관리·컨텍스트 유지** | `state_manager`(RUN_STATE/CHECKPOINT, file_lock), 전역 기억/위키 recall 주입 | 있음 |
| **에이전트 동작 제약·검증** | `command_guard`(위험명령 차단), `safety`/`approval`, `verifier`(에이전트 권한 점검) | 있음 |
| **관측성(observability)** | `audit`(감사로그, 실패 가시화), `status`/`dashboard`, 진단 파일 | 있음 |
| **초기화 분리·종료조건** | `init`/`resume`, STOP 파일, orchestrator interval, `watch`(stale heartbeat 판정) | 있음 |
| **무한대기 방지(supervision)** | `agentops watch`(exit 0/3/4) + `agent.md` "서브에이전트 감시" 규칙 | 있음 |

## 점검 규칙 (앞으로 런타임을 바꿀 때)

- 새 장기작업을 추가하면 반드시 **하트비트 + 종료조건 + watch로 감지 가능**하게 한다.
- 위임(서브에이전트/서브프로세스)은 **완료조건과 실패보고를 명시**하고, 메인이 `watch`로
  진행을 폴링해 멈추면 개입한다(열어놓고 무한대기 금지).
- 상태를 바꾸는 작업은 원자적 쓰기 + 필요한 경우 `file_lock`으로 lost-update 방지.
- 실패는 조용히 삼키지 말고 audit/stderr로 남긴다(관측성).

## 참고

- headroom(컨텍스트 압축, Apache-2.0): 큰 도구출력/로그를 LLM 전에 줄이는 아이디어.
  우리는 주입 char 상한·truncation으로 이미 부분 대응. 향후 "긴 출력 요약 후 주입"
  최적화 시 개념 참고(무거운 Rust/모델 의존은 반입 부담 커서 보류).
- 상세 방법론 원문: walkinglabs learn-harness-engineering(ko). 코드 아님 — 가이드 참고용.
