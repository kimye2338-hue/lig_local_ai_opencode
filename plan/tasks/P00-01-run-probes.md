# P00-01 — 환경 probe 실행 및 결과 업로드

| 항목 | 값 |
|------|-----|
| 단계 | P0 (선행 실측 — 모든 단계의 시행착오 제거) |
| 담당 | **human (사용자)** — 실행만 하면 됨 |
| 선행 | 없음 |
| 환경 | 집 PC + 회사 PC |

## 목표
워커가 추측으로 작업하지 않도록, 환경 사실을 실측 파일로 확보한다.

## 절차 (사용자)
1. **집 PC**: `workspace-template\launch\probe-env.bat` 더블클릭 → 생성 파일 2개를
   repo `probe/results/`에 커밋.
2. **회사 PC** (가능해지는 시점에):
   - `probe-env.bat` 실행 → 파일 반출 → 집에서 커밋
   - `%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env` 작성 후
     `probe-gateway.bat` 실행 → JSON 반출 → 커밋
     (host/key는 자동 마스킹됨 — 업로드 전 한 번 훑어보기 권장)

## 결과가 해소하는 미지수
- 회사 매크로 보안 정책(AccessVBOM/VBAWarnings) → P15 경로 확정
- gateway의 function calling 지원 여부 + tool-call 응답 원문 → P9/P11 파서 방향 확정
- 설치 앱/경로 실측 → P16 어댑터 exe 탐색 확정

## DoD
- [ ] probe/results/에 집 PC env 결과 존재
- [ ] (회사 접근 가능 시) 회사 env + gateway 결과 존재
