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
