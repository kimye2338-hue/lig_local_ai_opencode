# P18-02 — RUNBOOK + audit 순환 + doctor 운영 섹션

| 항목 | 값 |
|------|-----|
| 단계 | P18 (MASTER_PLAN §4 P18) |
| 담당 | codex |
| 선행 | P13-01 |
| 환경 | ANY |

## 작업 항목
1. `workspace-template/docs/RUNBOOK.md` — 증상별 대응 (각 항목: 증상 → 확인할 진단 파일
   경로 → 대응 명령): LLM 무응답/timeout, tool-call 반복 실패, 인코딩 깨짐, 어댑터 행
   (앱 프로세스 잔류), 일정 파일 손상(.bak 복구), gateway 설정 오류(validate 안내),
   디스크 부족. 전부 **기존 진단 파일**(runtime-last/tool-dispatch-history/agent-loop-last/
   work-context-last/audit.jsonl)과 연결.
2. `audit.py`에 순환: audit.jsonl > 10MB 시 `audit_<날짜>.jsonl.bak`으로 회전 (append 전 검사).
3. `doctor.py`에 `operations` 섹션: audit 파일 크기/최근 기록 시각, schedule 항목 수,
   runbook 경로, 최근 work 보고서 경로.
4. `tests/test_approval_audit.py` 확장: 회전 로직 (작은 임계값 env로 강제).

## DoD
- [ ] RUNBOOK 7개 증상 이상, 전부 실제 파일 경로 연결
- [ ] audit 회전 테스트 통과
- [ ] doctor operations manual smoke 출력 첨부
- [ ] 기존 checks 무손상
