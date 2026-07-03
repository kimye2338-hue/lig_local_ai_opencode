# probe/ — 환경 실측 결과 (추측 대신 사실)

이 폴더는 **사용자가 실행한 probe 스크립트의 결과**를 모은다. 워커(Codex)와 리뷰어(Fable)는
환경에 대한 가정이 필요할 때 **이 폴더의 최신 결과를 우선 근거**로 삼는다 (추측 금지 —
`plan/PROTOCOL.md` 참조).

## 사용자 실행 방법 (실행만 하면 됨)

| 스크립트 | 어디서 | 무엇을 알아내나 |
|----------|--------|----------------|
| `workspace-template\launch\probe-env.bat` | 집 PC + **회사 PC** | 설치 앱(Office/HWP/SolidWorks/MATLAB/AutoCAD/Fluent/Chrome), Office 버전, **매크로 보안 정책(AccessVBOM/VBAWarnings — COM 자동화 가능 여부의 핵심)**, RAM/디스크 |
| `workspace-template\launch\probe-gateway.bat` | **회사 PC** (lig-api.env 작성 후) | 3개 라우트(EXAONE coding/chat, Qwen fallback) 도달성/지연, **OpenAI tools(function calling) 지원 여부**, 프롬프트 기반 tool-call 응답 원문 (파서 튜닝용) |

실행 → `launch\probe_results\`에 생성된 `probe_env_*.json/.md`, `probe_gateway_*.json`을
이 repo의 `probe/results/`에 커밋한다. (회사 PC는 깃허브 접근 불가 → 파일 반출 후 집에서 커밋)

## 안전 (업로드해도 되는 이유)

- gateway probe는 API key와 host를 자동 마스킹(`<MASKED>`/`<GATEWAY>`)하고,
  쓰기 직전 결과 전문에서 secret 잔존을 재검사해 실패 시 파일을 만들지 않는다 (exit 3).
- env probe는 컴퓨터 이름/사용자명/IP를 수집하지 않으며, 홈 경로는 `%USERPROFILE%`로 치환.
- 그래도 업로드 전 파일을 한 번 훑어보는 것을 권장.

## 결과 해석 (워커/리뷰어용)

- `AccessVBOM=1` → Excel 매크로 자동 주입(run_macro_file) 가능. `0/키 없음` → P15-02의
  manual_import 강등 경로가 기본. `policy_*` 키 존재 → 그룹 정책 강제(변경 불가) — 계획 조정.
- `openai_tools.tool_calls_present=true` → function calling 사용 가능 (lig_runtime에 반영).
  false/accepted=false → 프롬프트 기반 tool-call(현 파이프라인 기본)로 확정.
- `text_toolcall.raw_content` → toolcall_parser 보강의 실측 근거.

## results/

`probe/results/` 에 날짜별 파일 축적. 같은 PC에서 재실행하면 새 날짜 파일로 추가
(과거 파일 삭제하지 않음 — 변경 이력도 정보다).
