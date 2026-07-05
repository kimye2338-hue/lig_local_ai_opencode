---
name: app-adapter
description: agent_ops/adapters/ 아래 앱 실행 모듈(COM/CLI 배치)을 만들 때의 안전/정직성 패턴. P12/P15/P16 계열 작업에서 사용.
---

# app-adapter

어댑터는 "앱이 없는 PC에서도 안전하고, 앱이 있는 PC에서도 원본을 못 건드리는" 모듈이다.

## Workflow

1. 의존성은 optional import: 부재 시 모든 API가
   `{"ok": False, "error": "<무엇이> 미설치 — dependencies.json '<항목>' 참조"}` 반환.
   import 실패로 모듈 로드가 죽으면 안 된다.
2. **원본 불가침을 API 표면으로 보장**: 원본을 여는 함수 자체를 만들지 않는다
   (`open_copy`만 존재). 저장은 사본/신규 파일로만, 자동 저장 금지.
3. 앱 프로세스는 try/finally로 정리 (Quit + COM 해제). 강제 예외 후 프로세스 잔류가
   없는지가 테스트 항목이다.
4. 실행형 액션은 `execute(action, options) -> dict` 단일 진입 — 미지 action은 예외가
   아니라 ok=False + 사용 가능 action 목록 반환.
5. registry 등록: `adapters/__init__.py`에 execute 연결하되 `available: False` 유지.
   True 전환은 실제 앱 실측 + `results/adapter_validation/` 로그 이후이며 **hard gate**(리뷰 필수).
6. 차단·미지원 상황은 실패가 아니라 **강등**: 예) VBProject 접근 차단 →
   `{"ok": False, "fallback": "manual_import", "guide": "Alt+F11 …"}`.

## Rules

- 테스트는 앱 부재에서 SKIP이 아니라 **안내 반환 경로를 검증**한다 (crash 0가 스펙).
- audit 기록(P13 이후)과 승인 게이트(dangerous)를 우회하는 실행 경로 금지.
- 앱 UI 텍스트(한글 메뉴명) 매칭 자동화 금지 — API/COM/CLI만.
