# OpenCodeLIG 전면 품질/UX 검토 (Opus 시니어 아키텍트 리뷰)

> 대상: `OPUS_REVIEW_OPENCODE_LIG_TOOLCALL_PACKAGE.zip` + 현재 리포지토리
> (`patches/`, `workspace-template/`, `docs/`).
> 성격: 단순 코드리뷰가 아니라 "매일 쓰고 싶은 수준"을 목표로 한 시스템 품질 검토.
> 판정: **아직 "완료"가 아니다.** 근본 원인 중 하나(tool-call 변환)는 패키지에
> 실물 코드가 없어 검증이 불가능하며, 인코딩/레이아웃/메모리는 런처 한 곳에서
> 함께 터진다. 아래 F(추가 파일)와 G(로드맵)를 반드시 함께 볼 것.

---

## A. 제품 사용성 총평

지금 상태가 실망스러운 이유는 "각 증상을 개별 땜빵으로 처리했는데, 정작 증상들이
공유하는 공통 지점(런처, guard, tool-call 파이프라인, 표시 정책)이 손대지지
않았기 때문"이다. 즉 v2~v5 패치는 대부분 **운영·지침·문서 레이어**를 두껍게
만들었고, 사용자가 실제로 부딪히는 **런타임 경로**는 거의 그대로다.

- 인코딩·레이아웃·메모리 리셋은 서로 다른 문제처럼 보이지만, **생성되는
  `RUN_OPENCODE_LIG.bat` 런처 한 곳**이 세 문제를 동시에 만든다(B/C 참조).
- "AUTO인데 멈춘다"의 진짜 원인은 permission이 아니라 **permission이 아닌 정지**
  (question tool, command guard throw, tool-call 파싱 실패, 모델 자기중단)이다.
  현재 AUTO 패치는 `permission.asked`만 자동승인하므로 이들을 못 푼다.
- "코드/로그 도배", "quiet 정책"은 전부 `.md` 지침일 뿐 **코드로 강제되지 않는다.**
  모델이 지침을 안 지키면 그대로 새어 나온다.

**실사용 판정: 현재 "제한적 사용 가능, 일상 사용 불가".**
permission 토글·spinner·safe_file_writer 같은 기반은 견고하지만, tool-call 실패와
런처 결함이 남아 있는 한 "조용히 알아서 일하는 도구" 경험은 나오지 않는다.
아래 C(1~2일)만 적용해도 체감은 크게 좋아지고, D+F까지 가야 "매일 쓸 수준"이 된다.

### 가장 큰 root cause 5개

1. **tool-call bridge/proxy 실물이 패키지에 없음.** `invalid [tool=:]`,
   `bash JSON parsing failed`, `올바른 JSON 형식...`, question JSON 노출은 전부
   *LIG 모델 출력 → OpenCode tool_call 변환* 지점에서 발생한다. 그 코드는 회사 PC의
   proxy/provider adapter에만 있고 ZIP에 없다 → **원인 검증 불가, F에서 파일 요청.**
2. **생성 런처가 콘솔/환경을 설정하지 않음.** `RUN_OPENCODE_LIG.bat`은
   `chcp`(UTF-8), 창 크기, `OPENCODE_*`/USERDATA 환경변수를 전혀 세팅하지 않는다
   → P1(외계어)·P5(레이아웃)·P7(메모리 리셋) 공통 뿌리.
3. **command-guard.ts가 throw로 긴 영어 에러를 채팅에 뿌리고 `python -c`를 전면
   차단.** tool-call이 실패해 모델이 bash heredoc로 파일을 쓰려 하면 guard가 막고,
   그 막은 메시지가 그대로 화면을 도배한다 → P2 멈춤·P4 도배를 증폭.
4. **AUTO가 permission 이벤트만 처리.** question/guard/parse-fail/자기중단은
   permission이 아니어서 AUTO로 안 풀린다 → "AUTO인데 멈춤"의 정체.
5. **메모리가 파일시스템에만 있고 모델 컨텍스트로 자동 주입되지 않음.** 세션마다
   모델은 과거를 "안 읽으면 모른다" → 디스크에 남아 있어도 "리셋된 것처럼" 느껴짐.

---

## B. 문제별 원인–해결 매트릭스

| # | 사용자 증상 | 기술적 원인 | v2~v5로 해결된 부분 | 아직 남은 부분 | 필요한 수정 | 우선순위 |
|---|---|---|---|---|---|---|
| P1 | 외계어/한글 깨짐 | 생성 런처에 `chcp 65001` 없음 → CP949 콘솔에서 UTF-8 TUI가 mojibake. (BAT 본문은 이미 ASCII-only라 안전) | 배치 파일 영어화(ASCII 0줄 확인), Python측 `PYTHONUTF8/IOENCODING` | **opencode.exe를 띄우는 콘솔의 코드페이지** 미설정 | 런처에 `chcp 65001` + UTF-8 폰트 안내, TUI stdout UTF-8 확인 | **P0** |
| P2 | AUTO인데 계속 멈춤 | AUTO는 `permission.asked`만 auto-reply. question/guard-throw/parse-fail/자기중단은 미처리 | AUTO=`reply:"once"` 자동승인(설계 양호), ASK/AUTO badge | 비-permission 정지 4종 | AUTO-HIGH-TRUST(질문 fallback·guard soft-block·heartbeat) | **P0** |
| P3 | 파일생성 JSON 오류, `tool=:`, question JSON 노출 | LIG 모델↔OpenCode tool-call 변환 실패. **실물 proxy/adapter가 ZIP에 없음** | (없음 — 지침 레이어만) | 전량 | tool-call broker: whitelist+schema검증+내부 repair+sanitizer+question fallback | **P0(파일 필요)** |
| P4 | 코드/로그가 화면 도배 | quiet 정책이 `.md` 지침일 뿐 코드 강제 없음. guard throw 문구도 유출 | `/quiet` 등 지침 추가 | 실제 출력 압축 미구현 | 출력 compressor(플러그인)·guard soft-block·code-dump 억제 | **P1** |
| P5 | 창이 꽉 안 참 | 런처가 창 최대화/크기 미설정. TUI resize 자체는 OpenTUI가 처리 | (없음) | 런처 레벨 창 제어 | `start /max` 실행 + Windows Terminal 프로필 권장 | **P1** |
| P6 | `Unknown component type spinner` 크래시 | OpenTUI reconciler에 `spinner` renderable 미등록 | **해결됨**: `spinner.tsx`·`footer.subagent`·`footer.view` 3곳 `<spinner>` 제거, `opentui-spinner/solid` import 제거 | 빌드 바이너리 잔존 여부만 확인 필요 | 빌드 산출물 grep 검증(회귀 방지) | **P2** |
| P7 | 패치 후 기억 리셋 | 런처가 USERDATA로 config/state를 안 가리킴 + 메모리가 모델 컨텍스트에 자동 주입 안 됨 | v2가 USERDATA 폴더 생성, memory_manager가 파일로 영속 | **주입 경로**·런처 env 배선 | 세션시작 memory loader(플러그인) + 런처 `OPENCODE_*` env | **P1** |

---

## C. 즉시 적용 가능한 개선안 (1~2일, 코드 위험 낮음)

### C1. 런처 재작성 — P1·P5·P7을 한 번에 (최고 ROI)
현재 생성물:
```bat
@echo off
set "OCODE_EXE=%USERPROFILE%\OpenCodeLIG\bin\opencode.exe"
set "AGENTOPS_HOME=%USERPROFILE%\OpenCodeLIG\workspace"
cd /d "%AGENTOPS_HOME%"
"%OCODE_EXE%" %*
```
권장 생성물(전부 ASCII, 한글 출력 없음):
```bat
@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "OCODE_EXE=%USERPROFILE%\OpenCodeLIG\bin\opencode.exe"
set "AGENTOPS_HOME=%USERPROFILE%\OpenCodeLIG\workspace"
rem persistent user data so patch/reinstall keeps memory + settings
set "OPENCODE_CONFIG=%USERPROFILE%\OpenCodeLIG_USERDATA\opencode_config"
set "XDG_DATA_HOME=%USERPROFILE%\OpenCodeLIG_USERDATA\opencode_data"
set "XDG_STATE_HOME=%USERPROFILE%\OpenCodeLIG_USERDATA\opencode_state"
set "XDG_CACHE_HOME=%USERPROFILE%\OpenCodeLIG_USERDATA\opencode_cache"
cd /d "%AGENTOPS_HOME%"
start "" /max cmd /c ""%OCODE_EXE%" %*"
```
> 주의: 실제 OPENCODE_* 환경변수 이름은 설치된 opencode 버전 기준으로 확정해야 함
> (`opencode --help`/docs). XDG 계열은 Windows 빌드가 따르는지 확인 후 채택.
> `chcp 65001`은 **자식 opencode 콘솔에만** 적용되므로 기존 사내 프로그램과 충돌하지
> 않는다(전역 변경 아님). 폰트가 D2Coding/Consolas 등 유니코드 지원이어야 박스문자·
> 한글이 정상 표시된다 → 설치 문서에 1줄 명시.

### C2. 인코딩 표준 정책 (확정 권고)
- **BAT 본문은 영어(ASCII)만.** 이미 준수 중(비-ASCII 0줄) → 규칙으로 고정.
- 한글 설명은 별도 `.md`로 분리(현행 유지).
- `chcp 65001`은 **런처/자식 콘솔 한정**으로만 사용(전역 강제 금지).
- Python 실행 시 `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`(이미 적용됨).
- **모든 로그 파일은 UTF-8(무BOM) 고정.** safe_file_writer/에이전트 로그 이미 준수.
- 경로에 한글/공백이 있어도 안전하도록 BAT 변수는 항상 큰따옴표로 감싼다(현행 유지).

### C3. command-guard soft-block (P2·P4 즉시 완화)
`throw`(긴 영어 문구가 채팅 유출) → **구조화된 짧은 차단 결과**로 바꾸고,
`python -c`는 *스테이징 파일 경유*는 허용. (D3에 패치)

### C4. quiet/표시 정책을 "요약 우선" 기본값으로
`autopilot`/`supervisor` 에이전트 프롬프트에 "파일 생성 시 전체 코드 덤프 금지,
경로+변경요약만 보고"를 **강한 기본 규칙**으로 승격(현재는 산발적 지침).
단, 이는 임시방편이며 진짜 해결은 D5 출력 compressor.

### C5. diagnostics 경로 정리
진단/캡처 산출물은 `OpenCodeLIG_USERDATA\diagnostics`로만 보내고, 채팅에는
**경로 + 3줄 요약**만 노출(runbook 정책을 코드/명령 기본값으로 반영).

---

## D. 코드 레벨 필수 개선안

### D1. tool-call broker/adapter (P3의 본체 — proxy 측, 파일 필요)
LIG 내부 API가 native OpenAI `tool_calls`를 신뢰성 있게 못 내보낸다는 전제로,
proxy에 아래 파이프라인을 넣는다(파싱은 `temperature=0`):
```
model_raw
  └─ 1) extract tool intent (JSON block / <tool_call> / functions.x(...))
  └─ 2) name whitelist   → {bash,edit,write,read,grep,glob,apply_patch,
                            question,todowrite,webfetch,websearch,skill}
        · 구두점-only(':') / python / terminal / run_command 등은 매핑 또는 거부
  └─ 3) per-tool JSON schema validate (bash.command:str, write.path+content ...)
  └─ 4) 실패 시 내부 repair 1회 (사용자에게 절대 노출 안 함)
  └─ 5) 그래도 실패 → 간결한 한국어 텍스트로 fallback (raw JSON 표시 금지)
  └─ 6) 실패 원인/횟수는 USERDATA\diagnostics\toolcall_failures.jsonl 로만 기록
```
- **whitelist**: 실행 전 이름 검증, 별칭은 의도적으로만 매핑.
- **final answer sanitizer**: `question` 스키마 배열/`header/options/multiple/custom`/
  `functions.bash({...})`/`<tool_call>`가 최종답변에 있으면 제거·치환.
- **question fallback**: question tool 호출 불가 시 → 한국어 자연문 1~3개 질문만.
- **file write fallback**: write/edit 변환 실패 시 `safe_file_writer.py` 경유로
  스테이징→검증→원자적 저장(이미 있는 자산 재사용).

### D2. permission AUTO-HIGH-TRUST 모드 (P2)
현행 `permission.tsx`의 auto-reply(`createEffect`)는 유지하되, 정지 4종을 구분 처리:
```
if mode == auto:
  permission.asked        → reply "once"                (현행 유지)
  question(clarification)  → 안전 기본값 자동선택 or 자동 skip + 로그   (신규)
  command-guard soft-block → 자동 대체경로(safe_file_writer) 시도       (신규)
  toolcall parse-fail      → 내부 repair 1회 후 재시도                 (신규, D1과 연동)
NEVER auto:
  explicit core deny / external_directory / 파괴적 명령(rm -rf, format ...)
```
+ **heartbeat/checkpoint**: N초 무진전이면 마지막 계획(RESUME_PLAN/CHECKPOINT)에서
자동 재개. 이미 `queue_manager.py`/`compaction-handoff.ts` 골격이 있으니 이를
"진짜 멈춤 감지 → 자동 재시도" 루프로 승격.

### D3. command-guard.ts: throw → soft-block (P2·P4)
```ts
// 반환형: 차단 사유를 채팅에 뿌리지 말고, 대체 행동을 지시하는 짧은 신호로.
"tool.execute.before": async (input, output) => {
  if (input?.tool !== "bash") return
  const cmd = String(output?.args?.command ?? "")
  const reasons = reasonsFor(cmd)
  if (!reasons.length) return
  // 파괴적 패턴만 hard-block(throw). 나머지(heredoc/echo/python -c)는
  // 조용히 write/apply_patch/safe_file_writer로 우회하도록 힌트만 남긴다.
  if (isDestructive(reasons)) throw new Error("BLOCKED: destructive shell pattern")
  output.args.command = ""   // no-op 처리
  output.__redirect = "use write/apply_patch or safe_file_writer.py"  // 내부용
}
```
+ `python -c`는 *임시 스테이징 파일로만* 허용(전면차단 완화). 긴 영어 문구가
사용자 채팅에 노출되지 않게 하는 것이 핵심.

### D4. memory loader (P7)
세션 시작 시 **모델 컨텍스트에 실제 주입**되도록 이벤트 플러그인 추가:
```ts
// session start / first message 훅에서
const recall = run("python agent_ops/agentops.py recall --limit 6")
output.context.push("## Durable memory (auto-injected)\n" + recall)
```
`memory_manager.recall()`/`format_recall_for_prompt()`는 이미 구현되어 있음 →
"파일 존재"에서 "컨텍스트 주입"으로 마지막 1마일만 연결하면 됨.
런처의 `OPENCODE_CONFIG`/USERDATA env(C1)와 합쳐야 재설치 후에도 유지된다.

### D5. command output compressor (P4)
tool 실행 결과가 임계(예: 200줄/8KB) 초과 시 자동으로 head/tail + "전체는
diagnostics\<id>.log 참조"로 접기. pip list/tree/grep 대량 덤프에 특히 적용.
플러그인 `tool.execute.after`에서 output.text를 요약본으로 교체.

### D6. spinner 최종 제거 검증 (P6)
소스 3곳은 제거 확인됨. **배포 바이너리에 잔존 없는지** 빌드 산출물에서
`spinner`/`<spinner>`/`opentui-spinner` 문자열 grep을 CI 검증 단계로 추가.
`prompt/index.tsx`에는 직접 spinner 경로 없음(패치가 건드리지 않았고 shared
Spinner만 사용). 회귀 방지 룰은 AGENTS.md에 이미 명시됨.

### D7. TUI layout resize
OpenTUI는 `useTerminalDimensions`로 resize를 이미 처리 → 대부분은 **런처 창
최대화(C1)**로 해결. 남는 여백/미충전은 fixed width/padding 유무를 세션·프롬프트
패널에서 점검(별도 소스 필요, 우선순위 낮음).

---

## E. 혁신적 구조 개선안 (사용감을 크게 바꾸는 설계)

목표는 "화면엔 상태/최종답변/필요한 입력만, 상세는 파일로, 작업은 큐로 계속".

| 안 | 구현난이도 | 예상효과 | 위험 | 추천 |
|---|---|---|---|---|
| ① 현 TUI 계속 패치 | 낮음 | 중 | 낮음 | 병행(단기) |
| ② **proxy-level tool-call broker**(D1) | 중 | **높음** | 중(파일 필요) | **강력추천** |
| ③ headless runner + 로그필터 wrapper | 중 | 높음 | 중 | 추천(2주차) |
| ④ LIG Agent Workbench 경량 GUI(웹/Tkinter) | 높음 | 매우높음 | 높음 | 조건부(장기) |
| ⑤ job queue/checkpoint/heartbeat 장시간 실행 | 중 | 높음 | 중 | 추천(뼈대 존재) |
| ⑥ 화면=요약, 상세=파일 표시 분리 | 중 | 높음 | 낮음 | 추천 |

**Opus 권고 = ②+⑥+⑤ 조합(1주 MVP).** ④ 풀 GUI는 매력적이지만 망분리 Windows
유지비가 크므로, 먼저 ③ headless+wrapper로 "조용한 실행 + 요약 표시 + 상세는
파일" 경험을 만들고, 성공하면 그 wrapper에 얇은 웹 UI(로컬 http)를 얹어 ④로
진화시키는 경로가 현실적이다. 핵심 통찰: **사용자가 원하는 건 TUI 미화가 아니라
"모델이 알아서 일하고 결과만 조용히 보고하는 채널"** 이고, 그건 ② broker(신뢰성)
+ ⑥ 표시분리(조용함) + ⑤ 큐(멈춤 없음)로 달성된다. TUI/GUI는 그 다음 문제다.

---

## F. 추가로 반드시 받아야 할 파일 (ZIP만으론 P3 검증 불가)

패키지에는 **LIG 모델↔OpenCode tool-call 변환 코드가 없다.** `llm_client.py`는
agent_ops 오케스트레이션용 별도 클라이언트일 뿐, TUI가 쓰는 provider 경로가 아니다.
아래 중 **존재하는 것 최소 세트**를 요청한다(회사 PC에서 파일명만 확인해 첨부):

1. `lig_toolcall_proxy*.py` / `lig_proxy*.py` / `proxy.py` / `server.py`
   (LIG API 앞단 OpenAI-호환 proxy — **가장 중요**)
2. `openai_compat*.py` / `harmony*.py` / `tool_router.py` / `toolcall_adapter.py`
   / `provider_adapter.py`
3. 설치된 opencode의 **provider 설정**(`opencode.json`/`config`의 provider·model·
   baseURL 부분 — 키/시크릿은 지우고)
4. 최근 `DIAG_OPENCODE_LIG.bat` 리포트 1개
5. `CAPTURE_OPENCODE_LIG_SESSION.bat`가 남긴 **`올바른 JSON 형식` / `tool=:`가 찍힌
   실제 세션 로그** 20~40줄
6. 회사 PC의 `chcp` 결과 1줄, 그리고 opencode를 **cmd/Windows Terminal 중 무엇으로
   어떻게 실행**하는지

> 위 1~2가 없으면 "tool-call 문제 해결"을 확언할 수 없다. 있으면 정확한 삽입 위치와
> unified diff까지 제시 가능.

---

## G. 구현 로드맵

**1단계 — 오늘 바로(안정화, 저위험)**
- C1 런처 재작성(chcp/UTF-8/USERDATA env/`start /max`) → P1·P5·P7 즉시 완화
- C3 guard soft-block(throw 제거) → P4 채팅 유출 차단
- C2 인코딩 정책 문서화, C5 diagnostics 경로 고정
- D6 spinner 바이너리 grep 검증을 CI에 추가

**2단계 — 이번 주(core/proxy)**
- F의 proxy 파일 확보 → D1 tool-call broker(whitelist/schema/repair/sanitizer/
  question fallback/file-write fallback) 구현 → **P3 본해결**
- D2 AUTO-HIGH-TRUST + heartbeat, D4 memory loader 주입, D5 출력 compressor

**3단계 — 장기(UX 혁신)**
- E안 ②+⑥+⑤로 headless+wrapper "조용한 실행 채널" MVP
- 성공 시 로컬 웹 기반 LIG Agent Workbench로 진화(④)

---

## H. 테스트 계획 (회사 PC에서 검증)

각 항목은 pass/fail 이분 판정으로 기록.
- **인코딩**: 한글 프롬프트 입력/출력, 박스문자·[PERM] 배지 정상 표시(외계어 0).
- **권한**: Shift+Tab로 ASK↔AUTO 토글·배지 변화, `/permission status|ask|auto|cycle`.
- **AUTO 연속**: 다단계 작업에서 permission·question·guard·parse-fail 각각에서
  멈추지 않고 진행(각 케이스 개별 시나리오).
- **파일생성**: write/edit로 JSON 오류 없이 생성, 실패 시 safe_file_writer fallback.
- **question fallback**: question tool 미지원 상황에서 raw JSON 대신 한국어 질문.
- **로그 압축**: pip list/대량 grep이 요약+파일경로로만 표시.
- **코드 노출 방지**: 파일 생성 시 전체 코드 덤프 없이 경로+요약만.
- **창 resize/전체화면**: 최대화 실행 + 창 조절 시 레이아웃이 꽉 참.
- **spinner**: 장시간 작업/서브에이전트에서 크래시 0(`Unknown component type` 없음).
- **memory 유지**: 재설치/패치 후 이전 선호가 새 세션 컨텍스트에 주입되어 반영.
- **diagnostics**: 실패 시 채팅엔 경로+요약, 상세는 USERDATA\diagnostics.

---

## I. Opus orchestration summary

1. Agent A(인벤토리): 102파일 트리·분류. runtime은 permission patch·agent_ops·
   플러그인 2개, 나머지는 문서/BAT임을 확정.
2. Agent B(인코딩): BAT 본문은 이미 ASCII-only(안전). 진짜 깨짐은 **생성 런처의
   chcp 부재**로 좁힘.
3. Agent C(AUTO): permission patch는 양호하나 AUTO가 `permission.asked`만 처리 →
   "멈춤"은 question/guard/parse-fail/자기중단이 정체임을 규명.
4. Agent D(tool-call): 실물 proxy가 ZIP에 없음을 확인 → 파일 요청 + broker 설계.
5. Agent E(UX): quiet가 지침일 뿐 코드 강제 없음 → compressor·guard soft-block 필요.
6. Agent F(레이아웃): 대부분 런처 최대화로 해결, TUI resize는 OpenTUI가 처리.
7. Agent G(spinner): 소스 3곳 제거 확인, 바이너리 grep만 잔여.
8. Agent H(구조): ②broker+⑥표시분리+⑤큐 조합을 1주 MVP로 권고.
9. **Opus 판단**: 근본은 "런처 한 곳 + tool-call proxy"이며, 전자는 오늘 고치고
   후자는 파일 확보가 선행. spinner/permission 기반은 이미 견고.
10. **"완료" 미선언**: P3는 proxy 파일과 Windows 실검증 전엔 확언 불가.
</content>
