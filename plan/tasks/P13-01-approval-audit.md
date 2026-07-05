# P13-01 — approval(승인 게이트) + audit(감사 로그) 모듈

| 항목 | 값 |
|------|-----|
| 단계 | P13 (MASTER_PLAN §4 P13 작업 항목 2~3) |
| 담당 | codex |
| 선행 | 없음 |
| 환경 | ANY |
| 산출 규모 | 모듈 2개 (~200줄) + 테스트 ~15 checks |

## 목표
파괴적 작업이 확인 없이 실행되지 않게 하는 승인 게이트와, 모든 실행을 남기는
append-only 감사 로그를 만든다 (P13-02 work 명령의 토대).

## 작업 항목
1. `agent_ops/approval.py`:
   - `classify_risk(action_kind: str, target: str, workspace_root) -> str`:
     `safe`(workspace 내 읽기/신규 생성) / `caution`(workspace 내 기존 파일 수정) /
     `dangerous`(workspace 밖 쓰기, 삭제, 앱/어댑터 실행, 일정 삭제·변경). 규칙은 테이블 상수.
   - `request_approval(items: list, assume_yes: bool, input_fn=input) -> dict`:
     dangerous 항목 목록을 "무엇을 할지" 사람이 읽을 문장으로 출력 → y/n.
     `input_fn` 주입으로 테스트 가능하게. 반환 {"approved": bool, "mode": "interactive|auto|denied"}.
2. `agent_ops/audit.py`:
   - `record(event: dict)` → `%USERPROFILE%\OpenCodeLIG_USERDATA\audit\audit.jsonl` append
     (env `LIG_AUDIT_DIR` 오버라이드 — 테스트 격리용, lig_providers의 DIAG_DIR 패턴 참조).
   - 필드: ts, run_id, kind(tool/adapter/schedule), name, target(경로 basename만),
     risk, verdict(approved/denied/auto), detail(80자 제한). **파일 내용/secret 기록 금지.**
   - 기록 실패는 stderr 경고만 — 호출자 중단 금지.
3. `tool_dispatch.py`에 audit 훅 (dispatch 성공/실패 기록 — 기존 구조 침습 최소화,
   try/except로 감싸 audit 오류가 dispatch를 못 죽이게).
4. `tests/test_approval_audit.py`: risk 분류 표 검증(각 분류 최소 2 케이스),
   approve/deny/auto-yes 경로, audit jsonl 형식/append/secret-free, 훅 무해성.

## 검증 명령
```bat
py -3.11 tests\test_approval_audit.py
py -3.11 tests\test_tool_dispatch.py
(회귀 9개 전부)
```

## DoD
- [ ] dangerous가 y 없이 승인되지 않음 (거부 경로 테스트)
- [ ] audit.jsonl append-only + 내용/secret 미기록 (테스트 증명)
- [ ] audit 실패가 작업을 중단시키지 않음
- [ ] 기존 checks 무손상

## 금지
- assume_yes 기본값 True 금지.
- audit에 파일 전체 경로 대신 basename만 (개인 경로 노출 최소화) — task 문구 80자 제한 준수.
