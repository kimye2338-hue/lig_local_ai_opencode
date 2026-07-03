# P00-02 — OpenCode 공식 문서 기준 연동 조사

| 항목 | 값 |
|------|-----|
| 단계 | P0 (조사 — 코드 변경 없음) |
| 담당 | **fable** (웹 접근 필요 — 워커 착수 금지) |
| 선행 | 없음 |
| 환경 | INTERNET |

## 목표
이 repo가 패키징하는 OpenCode(패치된 TUI)와 agent_ops의 관계를 공식 문서/소스 기준으로
확정 문서화한다 — 워커가 OpenCode 동작을 추측하지 않게.

## 조사 항목
1. 고정 커밋(`afff74eb`) 기준 OpenCode의 provider 설정 형식 (OpenAI 호환 endpoint 등록 방법)
2. OpenCode의 tool/plugin 확장점 — agent_ops를 OpenCode에서 호출 가능한지, 아니면
   별도 CLI 병행이 맞는지 (현 노선: 병행)
3. 오프라인 환경 제약 (telemetry, 업데이트 체크 등 차단 필요 항목)
4. permission 패치와 agent_ops 승인 게이트의 관계 정리

## 산출물
`docs/OPENCODE_INTEGRATION.md` — 출처(문서 URL/커밋) 명시, "확인됨 vs 추정" 구분 표기.

## 진행 기록 (2026-07-03, Fable)
- 항목 3 부분 완료: 공식 문서에서 `autoupdate:false` 확정 → 오프라인 패키지의
  workspace opencode.json + 런처 env 강화로 반영됨 (커밋 3d7dca9). 기동 시간 개선
  판정은 P00-03 실측 대기. 나머지 항목(provider 등록/확장점/TUI↔agent_ops)은 미착수.

## DoD
- [ ] 4개 항목 각각 출처 있는 결론 또는 "공식 문서에 없음 — 실측 필요" 표기
- [ ] agent_ops와의 통합 방식 권고 1개 확정
