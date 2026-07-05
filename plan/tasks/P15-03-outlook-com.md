# P15-03 — outlook_com 어댑터 (일정/메일 read)

| 항목 | 값 |
|------|-----|
| 단계 | P15 (MASTER_PLAN §4 P15 작업 항목 3) |
| 담당 | codex |
| 선행 | P15-02, P14-02 |
| 환경 | ANY (코드+SKIP. Outlook 실측은 회사 — P19) |

## 목표
비서 기능의 회사 연결점: Outlook 2016에서 일정을 읽어 schedule_store와 동기화하고,
받은편지함을 mail_report 파이프라인 입력으로 잇는다. **발송은 dangerous.**

## 리뷰 반영 (r1→r2) — reviews/P15-03-r1.md 필수 수정 1건 (r2 단일 진실 소스)

1. **자식 subprocess가 데이터 루트가 아닌 코드 루트에서 import되게** (`outlook_com.py:_run_child`):
   `core.ROOT`은 `AGENTOPS_ROOT`(데이터 루트)라 코드 패키지가 없을 수 있음 → `cwd=str(ROOT)`
   로 자식을 띄우면 `-m agent_ops...` import 실패 → "no JSON"으로 read_calendar/inbox/sync가
   전부 깨짐. 수정: 모듈 상단에 `CODE_ROOT = Path(__file__).resolve().parents[2]` 정의 후
   `_run_child`에서 `cwd=str(CODE_ROOT)` + `env["PYTHONPATH"]=str(CODE_ROOT)+os.pathsep+...`.
   (reviews/P15-03-r1.md "되는 방법" 코드 그대로.) `test_office_adapters.py`는 이미
   `AGENTOPS_ROOT=tmp`(코드≠데이터)를 설정하므로, 수정 후 그 테스트가 패키지 전역 import
   불가 환경에서도 통과해야 한다.

> 나머지(GetActiveObject 전용/서브프로세스 격리/sync 중복방지/send fail-closed dangerous/
> available=False)는 r1에서 실측 확인됨 — 유지.

> **실측 반영 (2026-07-03, company_check ⑤)**: DispatchEx 새 인스턴스로
> GetNamespace→GetDefaultFolder 접근 시 **40s hang** (프로필/보안 프롬프트 대기 추정).
> COM 접속 자체는 성공(16.0.0.5507). **구현 지침: ① `win32com.client.GetActiveObject
> ("Outlook.Application")`로 실행 중 인스턴스에 붙는 것을 1차로, ② 미실행이면
> "Outlook을 먼저 실행하세요" 안내 반환 (새 인스턴스 기동 금지), ③ 모든 MAPI 호출을
> 짧은 타임아웃의 격리 서브프로세스로.**

## 구현 패턴 (이대로 — 실측 hang 회피의 핵심)

접속은 반드시 GetActiveObject 우선 (새 인스턴스 기동 = 실측 40s hang):

```python
try:
    app = win32com.client.GetActiveObject("Outlook.Application")
except Exception:
    return {"ok": False,
            "error": "Outlook이 실행 중이 아닙니다 — Outlook을 먼저 실행한 뒤 다시 시도하세요"}
```

MAPI 호출(read_calendar/read_inbox)은 COM에 타임아웃을 걸 수 없으므로 **자기 자신을
자식 프로세스로 실행**해 격리한다 — 모듈 하단에 CLI를 두고, execute()는 subprocess로만
MAPI에 접근:

```python
# outlook_com.py 하단
if __name__ == "__main__":
    # 사용: py -3.11 -m agent_ops.adapters.outlook_com --action read_calendar --days 7
    # 결과: stdout에 JSON 한 줄 (ensure_ascii=False), 실패 시 {"ok": false, ...} + exit 1
    ...

# execute() 내부 — 부모 쪽
r = subprocess.run([sys.executable, "-m", "agent_ops.adapters.outlook_com",
                    "--action", action, ...],
                   capture_output=True, timeout=30)
out = (r.stdout or b"").decode("utf-8", errors="replace")
# timeout 시: {"ok": False, "error": "Outlook 응답 없음(30s) — 보안 프롬프트가 떠 있는지 확인"}
```

자식 실행 시 `env`에 `PYTHONUTF8=1` 포함 (cp949 깨짐 방지 — 실측 교훈).

## 작업 항목
1. `agent_ops/adapters/outlook_com.py` (excel_com과 동일 optional-import 패턴):
   - `read_calendar(days=7)` → [{title, start, end}] — schedule_store 스키마로 변환하는
     `sync_to_schedule(items)` (중복 방지: 같은 title+due 존재 시 skip, source="outlook").
   - `read_inbox(limit=50)` → [{from, subject, body 앞 200자}] — 기존
     gen_mail_report inbox 형식과 동일 (received 순).
   - `send_mail(...)`: **구현하되 approval.classify_risk가 dangerous 반환하는지 확인** —
     work 경로에서 승인 없이는 절대 호출 안 됨. 기본 노출 안 함(옵션 플래그).
2. schedule CLI에 `sync-outlook` subcommand (Outlook 부재 시 안내 exit 2).
3. `tests/test_office_adapters.py` 확장: 부재 SKIP, sync 중복 방지 로직(mock 데이터로),
   inbox→classify_mail 파이프 정합, send가 dangerous 분류.

## DoD
- [ ] read 계열 + sync 중복 방지 (mock 검증)
- [ ] send_mail은 dangerous + 기본 비노출
- [ ] Outlook 부재 SKIP, 기존 checks 무손상
- [ ] 상태 표기: "static reviewed; Outlook 2016 실측은 company/app validation pending"

## 금지
- 자동 발송 경로 기본 활성화 금지. 메일 body 전문을 audit/진단에 기록 금지.
