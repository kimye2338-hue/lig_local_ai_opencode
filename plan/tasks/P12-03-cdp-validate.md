# P12-03 — CDP 실측 + available 전환

| 항목 | 값 |
|------|-----|
| 단계 | P12 |
| 담당 | codex |
| 선행 | P12-02 |
| 환경 | **CHROME 필수** (로컬에 Chrome 설치 + 실행 권한) |

## 목표
실제 Chrome으로 3개 action(open_url/get_title/extract_text)+screenshot을 실측하고,
성공 시에만 browser adapter를 available=True로 전환한다.

## 작업 항목
1. `launch\chrome-debug.bat` 실행 → `py -3.11 tests\test_browser_adapter.py` 실측 통과.
2. 실측 결과(추출 텍스트 파일, 스크린샷 경로)를 `agent_ops/results/adapter_validation/browser_<날짜>.md`로 기록.
3. `adapters/__init__.py` browser: `available: True` + `"validated": "local Chrome CDP, <YYYY-MM-DD>"`,
   pending 문구는 "사내 시스템 로그인은 company validation pending"만 남김.
4. `test_capability_bench.py`의 "no adapter claims availability without app validation" check가
   browser의 available=True를 허용하도록 **검증 근거 필드가 있으면 통과**로 조건 갱신
   (다른 어댑터는 여전히 False 강제). check 문구도 실태에 맞게 갱신.

## DoD
- [ ] 실측 3 action + screenshot 성공 증빙 (adapter_validation 파일)
- [ ] available=True + validated 날짜 기록
- [ ] bench check 갱신 후 전체 통과
- [ ] Chrome 미존재 환경이면: 착수하지 말고 STATUS에 사유 코멘트 후 다음 READY로 (보고서에 명시)

## 금지
- 실측 없이 available=True 전환 금지.
- 기본 프로필 사용 금지.
