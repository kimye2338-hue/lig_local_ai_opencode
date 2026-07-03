# P10-01 — git 히스토리 내부 hostname purge

| 항목 | 값 |
|------|-----|
| 단계 | P10 (MASTER_PLAN §4 P10) |
| 담당 | **fable (FABLE-ONLY — 워커 착수 금지)** |
| 선행 | 없음 |
| 환경 | FABLE-ONLY (force push 동반) |
| 승인 | 사용자 승인 확보됨 (2026-07-03) |

## 목표
공개 repo 히스토리(커밋 67e0028, be9f981 등)의 내부 gateway hostname을 제거한다.

## 작업 항목 (MASTER_PLAN §4 P10 절차 그대로 — 순서 엄수)
1. `git clone --mirror`로 repo 밖 전체 백업 → 백업 확인 전 다음 단계 금지.
2. `git filter-repo --replace-text replacements.txt` (hostname → `INTERNAL-GATEWAY-PLACEHOLDER`).
   replacements.txt는 커밋 금지, 사용 후 삭제.
3. `git log --all -S"<hostname 일부>"` 전수 0건 확인 → force push → 원격 재클론 재확인.
4. PR #8 본문/코멘트 육안 점검.
5. 완료 시 이후 모든 보고에서 "security cleanup pending" 제거 (done으로).

## DoD
- [ ] 히스토리 전수 검색 0건 (로컬+재클론)
- [ ] 백업 mirror 존재
- [ ] STATUS/보고 상태 어휘 갱신

## 금지
- 이 세션에 다른 코드 변경 섞기 금지 (순수 purge 세션).
- 워커(codex)는 이 작업을 절대 잡지 않는다.
