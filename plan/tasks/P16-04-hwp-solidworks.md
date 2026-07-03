# P16-04 — hwp_com + solidworks_com 어댑터

| 항목 | 값 |
|------|-----|
| 단계 | P16 (MASTER_PLAN §4 P16 작업 항목 4~5) |
| 담당 | codex |
| 선행 | P15-02 (optional-import/사본/정리 패턴 재사용) |
| 환경 | ANY (앱 부재 SKIP — 실측은 회사 P19) |

## 목표
HWP 2019 변환과 SolidWorks 2022 매크로 실행 어댑터 (코드+모의 검증까지).

## 작업 항목
1. `agent_ops/adapters/hwp_com.py`:
   - `md_to_hwp(md_path, out_path)`: HwpFrame COM(`HWPFrame.HwpObject`) —
     보안 모듈 등록 확인(RegisterModule) → 신규 문서 → 제목/본문 텍스트 유입
     (heading은 글자 크기/굵기 수준) → `사본 아닌 신규 파일`로 저장. optional import 패턴.
   - HWP 2019 API 범위만 사용, 실패 시 안내 반환 + 프로세스 정리.
2. `agent_ops/adapters/solidworks_com.py`:
   - `run_macro(doc_path, bas_path)`: 문서 **사본 복사** → SldWorks.Application 접속
     (실행 중 인스턴스 우선, 없으면 기동) → 사본 열기 → `RunMacro2`(swb 변환 필요 시
     안내 강등: .bas는 SolidWorks에서 직접 실행 불가하면 "매크로 편집기에서 import 안내"
     반환) → **자동 저장 금지** (변경 확인은 사용자) → 닫기/정리.
   - SolidWorks 2022 한글판 전제 — 문서 타입/한글 UI 의존 로직 금지 (API만).
3. `adapters/__init__.py` hwp/solidworks 항목에 execute 연결 (available=False 유지).
4. `tests/test_office_adapters.py` 확장: 두 어댑터 부재 SKIP/안내, 사본·신규 파일 정책
   API 표면 검사, 미지 action 거부.

## DoD
- [ ] 앱 부재 crash 0 + 안내 반환
- [ ] SolidWorks 자동 저장 없음 / HWP는 신규 파일만 생성 (원본 불가침)
- [ ] available=False + app validation pending 유지
- [ ] 기존 checks 무손상

## 금지
- .bas→.swp 자동 변환을 됐다고 가정 금지 — 안 되면 강등 안내가 정답.
- 한글 UI 텍스트(메뉴명) 매칭 자동화 금지 (버전/언어 취약).
