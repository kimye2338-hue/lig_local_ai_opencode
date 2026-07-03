# P18-02 — RUNBOOK + audit 순환 + doctor 운영 섹션

| 항목 | 값 |
|------|-----|
| 단계 | P18 (MASTER_PLAN §4 P18) |
| 담당 | codex |
| 선행 | P13-01 (APPROVED) |
| 환경 | ANY |
| 산출 규모 | RUNBOOK.md + audit 회전 ~15줄 + doctor 섹션 + 테스트 확장 |

## 목표
운영 문서(RUNBOOK)와 최소 운영 코드(audit 회전, doctor operations)를 만든다.
RUNBOOK의 모든 항목은 **이미 존재하는 진단 파일**과 연결한다 — 새 진단 체계 발명 금지.

## 작업 항목

### 1. `workspace-template/docs/RUNBOOK.md`

아래 7행을 표로 정리한다 (내용은 이 표 그대로 시작하고, 각 행에 확인 명령을 코드로 병기.
경로 표기는 diagnostics = `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\` 기준 —
실제 경로 상수는 `agent_ops/core.py` 확인 후 그에 맞춘다):

| 증상 | 먼저 볼 진단 파일 | 대응 |
|------|-------------------|------|
| LLM 무응답/timeout | diagnostics `runtime-last.json`의 `fallback_trigger`/`trail` | lig-api.env 라우트 3줄(`/gateway/` 접두 — 실측: 누락 시 404) 확인 → `agentops.py doctor` → 필요 시 `launch\probe-gateway.bat` |
| tool-call 반복 실패 | `tool-dispatch-history.jsonl` + `agent-loop-last.json`(outcome=tool_loop_cutoff) | task 문구를 단순화해 재시도, `--mode mock`으로 파이프라인 자체는 정상인지 분리 확인 |
| 콘솔/파일 한글 깨짐 | (진단 파일 없음 — 증상 즉시 식별) | 반드시 `launch\*.bat` 경유 실행 (chcp 65001+PYTHONUTF8=1 보장). 직접 `py` 실행이 원인 |
| 어댑터 행/앱 프로세스 잔류 | `audit.jsonl` 마지막 기록 (어느 앱·어느 파일에서 멈췄나) | 작업관리자에서 EXCEL.EXE 등 종료 → 원본이 아닌 `사본_*` 파일만 쓰였는지 확인 → 재시도 |
| 일정 파일 손상 | schedule 저장 폴더의 `.bak` | `.bak`을 원본 이름으로 복사해 복구 (P14-01 백업 규약) |
| gateway 설정 오류 | `agentops.py doctor` 출력의 gateway/providers 섹션 | env 파일 키 이름·라우트 접두 확인, presence flag만 보고 실값은 노출 금지 |
| 디스크 부족 | `results/` 폴더 크기 | 오래된 `results/artifacts/<run_id>/` 정리. audit는 자동 회전(.bak)이므로 삭제 불필요 |

문서 머리에 "증상 → 파일 → 대응, 3분 안에 1차 조치" 원칙 1문단.

### 2. `audit.py` 회전 (append 전 검사)

```python
_MAX_BYTES = int(os.environ.get("LIG_AUDIT_MAX_BYTES", str(10 * 1024 * 1024)))
```

`record(...)`의 append 직전에: 대상 파일이 존재하고 크기 ≥ `_MAX_BYTES`이면
`audit_<YYYYMMDD_HHMMSS>.jsonl.bak`으로 rename 후 새 파일에 기록. rename 실패는
삼켜서 기록 자체는 계속(진단이 본작업을 깨지 않는 기존 원칙). env는 **record 호출 시점**에
읽어도 됨(테스트에서 작은 값 강제 가능하게).

### 3. `doctor.py`에 `operations` 섹션 (필드 고정)

`audit_file`(경로), `audit_size_bytes`, `audit_last_ts`(마지막 레코드 timestamp 또는 ""),
`audit_rotated`(`audit_*.jsonl.bak` 개수), `schedule_items`(store 항목 수, store 없으면 0),
`runbook`(RUNBOOK.md 존재 여부 bool), `last_work_report`(results/reports/work_*.md 최신
경로 또는 ""). 전부 secret-free.

### 4. `tests/test_approval_audit.py` 확장

`LIG_AUDIT_MAX_BYTES=200` env로 강제 → 레코드 여러 건 기록 → `.bak` 생성 + 새 파일에
이어서 기록됨을 check (tmp 격리). doctor operations는 manual smoke로 출력 첨부.

## 검증 명령
```bat
py -3.11 tests\test_approval_audit.py
py -3.11 ..\agent_ops\agentops.py doctor    (operations 섹션 눈 확인 — 출력 보고서 첨부)
(회귀 전체 — PROTOCOL §2)
```

## DoD
- [ ] RUNBOOK 7개 증상, 전부 실제 진단 파일 경로·실제 명령과 연결 (발명 금지)
- [ ] audit 회전 테스트 통과 (.bak 생성 + 신규 파일 계속 기록)
- [ ] doctor operations manual smoke 출력 첨부
- [ ] 기존 checks 무손상

## 금지
- 새 진단 파일/로그 체계 추가 금지 — 기존 파일 연결만.
- audit 레코드 스키마 변경 금지 (회전만 추가).
