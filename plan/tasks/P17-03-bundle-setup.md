# P17-03 — 반입 번들 build + setup.bat + 체크리스트

| 항목 | 값 |
|------|-----|
| 단계 | P17 (MASTER_PLAN §4 P17 작업 항목 3) |
| 담당 | codex |
| 선행 | P17-02 |
| 환경 | ANY |

## 목표
반입 zip 하나로 회사 PC 전체 설치가 끝나게 한다.

## 작업 항목
1. `release/build_bundle.py` (stdlib): repo(workspace-template+plan+docs) +
   release/prefetch/* → `OpenCodeLIG_BUNDLE_<날짜>.zip` + 내부 `MANIFEST_SHA256.txt`
   (전 파일 해시). 진행 출력 + 최종 크기 보고.
2. `release/setup.bat` (인코딩 규약): ① py -3.11 존재 확인(없으면 python 설치 안내 후 exit)
   ② `pip install --no-index --find-links prefetch\ pywin32 openpyxl python-pptx`
   ③ workspace 배치(%USERPROFILE%\OpenCodeLIG) ④ USERDATA 폴더 생성
   ⑤ `py -3.11 agent_ops\agentops.py doctor` 실행 ⑥ 요약 출력 (성공/실패 항목).
   각 단계 실패 시 원인과 다음 행동 안내 후 exit (조용한 실패 금지).
3. `docs/BRING_IN_CHECKLIST.md`: 반입 전(빌드/해시 확인/매체 복사) → 반입 →
   설치(setup.bat) → 확인(doctor 항목별 기대값) → lig-api.env 작성 안내(커밋 금지 경고).
4. `tests/test_release_manifest.py` 확장: build_bundle을 tmp로 실행해 zip 구조/매니페스트
   검증 (prefetch 없으면 더미 파일로 구조만 — 그 사실 출력).

## DoD
- [ ] zip 생성+매니페스트 검증 테스트 통과
- [ ] setup.bat 각 단계 실패 처리 존재 (코드 리뷰 가능 수준으로 명확)
- [ ] 체크리스트 문서화
- [ ] 기존 checks 무손상

## 금지
- setup.bat에서 인터넷 접근(pip 기본 인덱스 포함) 금지 — --no-index 강제.
- PowerShell -ExecutionPolicy Bypass 사용 금지 (AGENTS.md 기존 제약).
