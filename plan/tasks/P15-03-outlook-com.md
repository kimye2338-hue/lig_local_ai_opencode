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
