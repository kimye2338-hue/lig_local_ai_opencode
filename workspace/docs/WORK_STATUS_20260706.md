# 작업 현황 및 남은 계획 (2026-07-06, Fable 세션)

git 백업: `01e5e4f`(수정 전) → `b787b2d`(1차 수정 커밋). 문제 시 복원 가능.

## 절대 불변
- API 설정값(lig-api.env.example, llm_config.example.json), env 키, gateway 라우트,
  모델명(EXAONE/Qwen)은 **절대 변경/삭제 금지** (사용자 명시 지시).

## 완료 (커밋 b787b2d, 전 테스트 green)
- WS-A 안전계층: command_guard denylist 강화(구분자 우회 차단, Windows 파괴명령 20종 추가),
  TS 플러그인 parity, audit 실패 가시화, verifier broad-allow 탐지.
- WS-B 코어/입력: CP949 폴백 디코드(decode_file_bytes), xlsx 비밀마스킹, lig_runtime fallback
  재시도 리셋, OneDrive rglob 조기중단, truncated 플래그, safe_write 롤백, _pid_alive 정밀매칭.
- WS-D 메모리/일정: schedule_store file_lock+due-date 가드, knowledge_book 인코딩,
  state_manager 락, hamster pet_asset_dir/load_pet_images.
- 부분: excel_com 고아프로세스, RUN_AGENTOPS 6개 런처, _pyw.bat CRLF.

## 테스트 베이스라인 메모
- 환경적 실패(오프라인 패키지에 release/ 없음 — 소스저장소 전용, 코드결함 아님):
  test_ocd_profiles, test_patch_build, test_release_manifest, test_launch_bats(release/setup.bat 참조).
- 의도적 스킵: test_capability_floor(실LLM), test_real_llm_smoke, test_office_live_smoke.
- test_batch_adapters autocad utf16le 실패는 동시부하 flake였음 — 단독실행 시 통과.

## 남은 작업 (우선순위)
1. [진행] 패치zip 위키 커뮤니티기능 병합: aliases.json 별칭확장, 모순후보 탐지, 백링크,
   반복확인 강화신호, knowledge_book 모순배너, agentops 매일 위키 lint.
   근거 소스: rohitg00 LLM Wiki, green-dalii/obsidian-llm-wiki, Karpathy. (= GitHub 아이디어 차용)
   파일: wiki_manager.py, knowledge_book.py, agentops.py, tests/test_wiki_manager.py.
2. [진행] 귀여운 햄스터 펫: 스티커 PNG(assets/hamster_pet 애니 프레임) 실제 렌더링 연결,
   OpenCodeLIG와 자연스럽게 연동, 표정/상태 반영. 이미 RUN_OPENCODE_LIG.bat가 숨김 실행.
3. [설계+구현] 오프라인 OCR(한/영): 화면 스크린샷 → OCR 어댑터. 백엔드 플러거블
   (tesseract kor+eng / RapidOCR onnx 중 존재하는 것 사용, 없으면 안내). 브라우저 막힘 시
   스크린샷 OCR 폴백. 엔진 바이너리는 오프라인 반입 필요 — prefetch/문서로 안내.
   신규: agent_ops/adapters/ocr_screen.py, tool 등록, dependencies 프리페치 항목.
4. [연구→코퍼스] 공식 API 가이드 코퍼스: 사용자 소프트웨어(Office2016 VBA, HWP, SolidWorks,
   AutoCAD, MATLAB, ANSYS Fluent) 버전별 공식 API/명령을 조사해 로컬 참조자료로 번들.
   "하이쿠 시켜서" 조사 → agent_ops/knowledge/apis/*.md 코퍼스 + 매크로 생성 시 참조.
   목적: 매크로/코드 생성 시 환각 아닌 공식근거 기반.
5. [잔여] 어댑터 나머지(solidworks/autocad/fluent/matlab/hwp/office_convert/browser_cdp 견고화),
   스크립트 잔여(INSTALL stray `\` 제거, test_launch_bats glob, 문서).

## 주의
- 공유 계정 세션한도 발생 중(오후 9:10 리셋). 에이전트 대량 스폰 지양, 자주 커밋.
