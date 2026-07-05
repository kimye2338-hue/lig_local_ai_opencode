# P09-01 — LLM provider 프로필/env 완전 오버라이드

| 항목 | 값 |
|------|-----|
| 단계 | P9 (MASTER_PLAN §4 P9 작업 항목 1) |
| 담당 | codex |
| 선행 | 없음 |
| 환경 | ANY |
| 산출 규모 | 코드 ~120줄 + 테스트 ~8 checks |

## 목표
gateway 스펙(라우트 경로/모델명/타임아웃)이 바뀌어도 **코드 수정 없이 lig-api.env 편집만으로**
반영되게 하고, secret 없이 동작하는 로컬 개발 프로필(local_openai)을 추가한다.

## 먼저 읽기
- `workspace-template/agent_ops/lig_providers.py` 전체 (특히 `_ROUTE_DEFAULTS`, `build_providers`, `validate_config`)
- `workspace-template/tests/test_lig_providers.py` (기존 15 checks — 전부 유지)
- MASTER_PLAN §1.1(LLM 확정값), §4 P9

## 작업 항목
1. `lig_providers.py`:
   - 모델 오버라이드 env 키 추가: `LIG_MODEL_CODING` / `LIG_MODEL_CHAT` / `LIG_MODEL_FALLBACK`
     (없으면 기존 기본값 유지). `_ROUTE_DEFAULTS` 구조는 (route_env_key, route_default,
     model_env_key, model_default) 4-tuple로 확장.
   - `get_profile(env=None) -> str`: `LIG_PROVIDER_PROFILE` 읽기, 허용값
     `company_gateway`(기본)/`local_openai`. 그 외 값이면 company_gateway로 폴백하고
     validate 리포트에 `"profile_warning"` 기록.
   - local_openai 프로필: 3개 라우트 모두 `LIG_LOCAL_BASE_URL`(기본
     `http://127.0.0.1:11434/v1`) + `LIG_LOCAL_MODEL`(기본 `qwen2.5:7b-instruct`)을 사용.
     api_key 불필요 — `validate_config`는 이 프로필에서 `api_key_set` 없이도 `ready=True`.
   - `validate_config` 리포트에 `"profile"` 필드 추가. 기존 필드/시그니처 전부 유지.
2. `workspace-template/config/lig-api.env.example`: 신규 키 전부 주석과 함께 추가
   (실값 금지, 플레이스홀더만).
3. `tests/test_lig_providers.py`에 checks 추가 (기존 15개 무수정):
   - 라우트/모델 env 오버라이드가 build_providers에 반영
   - local_openai 프로필이 secret 없이 ready
   - 잘못된 프로필 값 → company_gateway 폴백 + 경고 필드
   - validate 리포트에 base_url/host 문자열이 포함되지 않음 (secret-free 유지)

## 검증 명령
```bat
py -3.11 tests\test_lig_providers.py
py -3.11 tests\test_lig_runtime.py
(회귀 9개 전부 — PROTOCOL §2)
```

## DoD
- [ ] 라우트/모델/타임아웃 변경이 env 편집만으로 반영됨을 테스트가 증명
- [ ] local_openai 프로필이 api_key 없이 ready=True
- [ ] validate_config 출력에 host/key 원문 미포함 (테스트로 증명)
- [ ] env.example에 신규 키 전부 문서화
- [ ] 기존 260 checks 무손상

## 금지 / 가드레일
- `build_providers` 반환 dict를 print/log 하는 코드 추가 금지 (host 포함 — 기존 주석 참조).
- 기존 함수 시그니처 변경 금지 (doctor/runtime이 사용 중).
- 실제 gateway 값 추측 삽입 금지 — 기본값은 기존 `_ROUTE_DEFAULTS` 것만.
