# OpenCodeLIG 품질/UX 검토 v2 — 공식문서 재검증 + 실적용 산출물

> v1(`docs/OPUS_UX_QUALITY_REVIEW.md`)의 진단을 **OpenCode 공식문서로 재검증**하고,
> "설명"이 아니라 **바로 적용 가능한 파일/패치/명령/테스트**로 확장한 판이다.
> 이 판이 최신이며 v1을 대체한다.
>
> **판정: 아직 "완료" 아님.** P3(tool-call 변환)는 회사 PC의 proxy/provider 파일
> (§G)과 Windows 실검증 전에는 확언 불가. 나머지는 이 PR의 산출물로 즉시 개선된다.

동봉 산출물(이 PR에 포함):
- `workspace-template/RUN_OPENCODE_LIG.bat.txt` — 인코딩/창/USERDATA 하드닝 런처(H1)
- `workspace-template/.opencode/plugins/command-guard.ts` — soft-block 재작성(H2)
- `workspace-template/COLLECT_LIG_PROXY_FILES.bat.txt` — 누락 파일 수집기(H3)
- `workspace-template/agent_ops/config/opencode.permission.example.json` — AUTO-HIGH-TRUST 네이티브 권한 프로파일
- 본 문서(H4 30분 체크리스트 · I PR계획 · J 테스트계획 포함)

---

## A. 제품 사용성 총평

증상 7개는 서로 다른 버그가 아니라 **공통 지점 2곳**에서 갈라져 나온다.

- **생성 런처 `RUN_OPENCODE_LIG.bat`** 한 곳이 `chcp`(UTF-8)·창 크기·`OPENCODE/XDG`
  환경변수를 전혀 세팅하지 않아 → 인코딩(P1)·레이아웃(P5)·메모리리셋(P7)을 동시 유발.
- **LIG 모델↔OpenCode tool-call 변환 계층**이 패키지에 없어 → `tool=:`,
  `JSON parsing failed`, `올바른 JSON 형식`, question JSON 노출(P3) 전부 미해결.

그 위에 **command-guard.ts가 긴 영어 에러를 throw로 채팅에 쏟고** 정상 shell
파일쓰기(echo/heredoc/`python -c`)까지 막아, tool-call이 불안정한 상황에서 에이전트가
쓸 수 있는 유일한 fallback을 차단 → AUTO 멈춤(P2)·도배(P4)를 증폭했다.

**실사용 판정: "제한적 사용 가능, 일상 사용 불가".** permission 토글·spinner 제거·
safe_file_writer 같은 기반은 견고하나, tool-call 변환과 런처 결함이 남는 한 "조용히
알아서" 경험은 안 나온다. **이 PR의 H1/H2 + AUTO-HIGH-TRUST 권한 프로파일**만으로
P1/P5/P7과 P2/P4의 상당 부분이 오늘 개선되고, §G 파일 확보 후 P3까지 닫으면 "매일
쓸 수준"에 도달한다.

### root cause 5개
1. 런처가 콘솔/환경 미설정(P1·P5·P7 공통근).
2. tool-call 변환 proxy 부재(P3, 파일 필요).
3. command-guard가 throw로 유출 + 정상 shell-write 차단(P2·P4 증폭).
4. AUTO가 `permission.asked`만 처리 — question/guard/parse-fail/자기중단은 미포함.
5. 메모리가 파일로만 존재하고 모델 컨텍스트에 자동 주입 경로 없음(P7).

---

## B. 현재 모델/provider/tool-call 구조 확인 (+ 공식문서 대조)

**관측된 모델/모드**: `Auto · [기본] EXAONE 코딩/파일/터미널`.
내부 API 후보: `exaone_think_on/off`, `textgen`, `gpt-oss-120b-medium`.
LIG 내부 API는 OpenAI-compatible을 흉내내지만 **native `tool_calls` 지원이 불완전**할
수 있다(사용자 제보).

**공식문서 대조 결과(재검증 완료):**

| 항목 | 공식문서 사실 | OpenCodeLIG 현행 | 판정 |
|---|---|---|---|
| custom provider | `provider.<id>.npm = "@ai-sdk/openai-compatible"` + `options.baseURL` + `models` | 설정 파일 미동봉 | **확인 불가 → §G 요청** |
| `--auto` | **네이티브 플래그**. "명시적으로 deny되지 않은 permission 요청을 자동승인". TUI 커맨드팔레트 "Enable auto-approve"도 있음 | 커스텀 Shift+Tab 토글 패치로 재구현 | 패치는 UX 가치 있음. **런처에 `--auto` 기본 적용**으로 보강(H1) |
| built-in tools | `bash, edit, write, read, grep, glob, lsp, apply_patch, skill, todowrite, webfetch, websearch, question` | taxonomy와 일치 | OK |
| `write`/`apply_patch` 권한 | **`edit` permission이 관장** | 별도 취급 | 권한 프로파일에 반영 |
| `question` | **built-in이며 permission으로 게이팅 가능**(header/질문/options) | 스키마가 채팅에 새는 중 | **`question:"ask"`(기본)/`"deny"`(고신뢰)로 제어 가능** |
| `webfetch` | 항상 시도(내부망이면 실패) | — | 예시3에서 "내부망 접근불가" 처리 |
| `websearch` | **OpenCode provider 또는 `OPENCODE_ENABLE_EXA=1`에서만** | 내부망엔 사실상 불가 | 권한 allow해도 미동작 가능 — 예시에서 명시 |
| native tool_calls 미지원 모델 | **공식 fallback 문서 없음** | LIG 모델이 여기 해당 가능성 | **proxy-level broker 필요(E/§G)** |

**결론**: OpenCode는 tool-call을 AI-SDK openai-compatible 경로로 모델에 위임한다.
EXAONE/gpt-oss가 규격 `tool_calls`를 못 내보내면 SDK가 malformed 응답을 받고
OpenCode가 `invalid [tool=...]`로 표면화한다. **해결은 proxy에서 tool-call을
정규화(broker)** 하는 것이며, 이는 prompt 튜닝으로 못 고친다.

---

## C. 문제별 원인–해결 매트릭스

| # | 사용자 증상 | 기술적 원인 | v5까지 해결 | 남은 부분 | 필요한 수정 | 우선순위 |
|---|---|---|---|---|---|---|
| P1 | 외계어/한글깨짐 | 런처에 `chcp 65001` 없음(CP949 콘솔에 UTF-8 TUI) | BAT 본문 ASCII화, Python IO enc | opencode 콘솔 코드페이지 | **H1 런처**(chcp+폰트안내) | **P0** |
| P2 | AUTO인데 멈춤 | AUTO=permission만 처리; question/guard/parse-fail/자기중단 미포함 | AUTO reply once, badge | 비-permission 정지 4종 | `--auto`+네이티브 권한 프로파일+guard soft-block+question 제어+heartbeat | **P0** |
| P3 | 파일생성 JSON오류/`tool=:`/question JSON | LIG↔OpenCode tool-call 변환 실패, **proxy 부재** | (지침만) | 전량 | **broker**(whitelist/schema/repair/sanitizer/fallback) | **P0(파일필요)** |
| P4 | 코드/로그 도배 | quiet가 지침일 뿐 코드강제 없음; guard throw 유출 | `/quiet` 지침 | 출력 압축 미구현 | **H2 soft-block**+출력 compressor 플러그인 | **P1** |
| P5 | 창 안 참 | 런처가 창 최대화 미설정 | — | 런처 레벨 | **H1**(`start /max`)+Terminal 권장 | **P1** |
| P6 | spinner crash | OpenTUI에 spinner renderable 미등록 | **해결**(3곳 제거) | 바이너리 잔존검증 | 빌드 grep을 CI에 추가 | **P2** |
| P7 | 기억 리셋 | 런처가 USERDATA 미지정 + 메모리 미주입 | USERDATA 폴더/영속 | env 배선·주입경로 | **H1 env**+세션시작 memory loader(E) | **P1** |

---

## D. 즉시 적용 가능한 개선안 (1~2일, 대부분 이 PR에 포함)

- **H1 런처 재작성** — `chcp 65001`(자식 콘솔 한정), `PYTHONUTF8/IOENCODING`,
  `OPENCODE_CONFIG`+`XDG_*` → USERDATA, `start /max`, `--auto` 기본. **P1·P5·P7 즉시 완화.**
  → `workspace-template/RUN_OPENCODE_LIG.bat.txt` (오프라인 설치 생성부도 동일 패턴으로
  교체 필요 — §I PR#7).
- **인코딩 표준(확정 권고):** BAT 본문 ASCII-only(현행 준수), 한글은 `.md`로 분리,
  `chcp 65001`은 런처/자식 한정(전역 금지), Python `PYTHONUTF8=1`, 로그는 UTF-8(무BOM)
  고정, 실행은 **Windows Terminal 권장**(cmd.exe legacy 콘솔은 UTF-8 렌더 품질이 낮음).
- **AUTO-HIGH-TRUST 권한 프로파일** — `opencode.permission.example.json`을
  USERDATA에 두고 `--auto`와 함께 사용. 안전 도구=allow, 파괴/외부전송=deny/ask.
  **파괴 명령 차단을 플러그인 throw가 아니라 네이티브 권한으로 이동**(공식 지원).
- **H2 guard soft-block** — throw 메시지 1줄화, 정상 shell-write 허용 → 도배·멈춤 완화.
- **quiet 기본값 승격** — autopilot/supervisor 프롬프트에 "파일 생성 시 전체 코드 덤프
  금지, 경로+요약만" 강한 기본 규칙(임시). 진짜 해결은 E 출력 compressor.
- **diagnostics 경로 고정** — 채팅엔 경로+3줄 요약, 상세는 USERDATA\diagnostics.

---

## E. 코드 레벨 필수 개선안

### E1. tool-call broker (P3 본체 — proxy 측, §G 파일 필요)
LIG API 앞단(또는 OpenCode provider와 LIG 사이)에 정규화 계층:
```
model_raw
 └ 1) intent 추출: JSON블록 / <tool_call> / functions.x(...) / 자연어의도
 └ 2) name whitelist  → {bash,edit,write,read,grep,glob,apply_patch,
                         question,todowrite,webfetch,websearch,skill,lsp}
      · ':' 구두점-only, python/terminal/run_command 등은 매핑 또는 거부
 └ 3) per-tool JSON schema 검증 (bash.command:str / write.filePath+content 등)
 └ 4) 실패 시 내부 repair 1회 (temperature=0, 사용자에게 절대 미노출)
 └ 5) 그래도 실패 → 간결한 한국어 텍스트 fallback (raw JSON 표시 금지)
 └ 6) 실패 원인/횟수 → USERDATA\diagnostics\toolcall_failures.jsonl 만 기록
```
+ **final answer sanitizer**: 최종답변에 `header/options/multiple/custom`·
`functions.bash({...})`·`<tool_call>`·JSON배열 있으면 제거/치환.
+ **question fallback**: question tool 미변환 시 → 한국어 자연문 1~3개 질문만.
+ **file write fallback**: write/edit 변환 실패 시 `safe_file_writer.py` 경유.

### E2. permission AUTO-HIGH-TRUST (P2) — 네이티브 우선
- **런처 `--auto`** 로 permission 자동승인(공식). 파괴/외부전송은 프로파일 deny/ask.
- **question 제어**: 기본 `"ask"`. 최대 자율이 필요하면 `"question":"deny"`로 두면
  모델이 중간질문 대신 가정으로 진행(위험 낮은 작업에 한해). 두 프로파일 제공 권장.
- **heartbeat/checkpoint**: N초 무진전 시 `RESUME_PLAN/CHECKPOINT`에서 자동 재개
  (`queue_manager.py`+`compaction-handoff.ts` 골격 승격).
- **절대 자동화 금지**: 명시적 core `deny`, `external_directory`, `doom_loop`,
  파괴 명령, 비밀정보/외부전송.

### E3. command-guard soft-block (H2, 이 PR 반영)
throw 1줄화 + corruption/파괴/malformed만 차단, 정상 shell-write는 통과. 파괴 1차
방어는 네이티브 권한으로 이관.

### E4. memory loader (P7)
세션 시작 훅에서 실제 컨텍스트 주입:
```ts
// session start 훅
const recall = run("python agent_ops/agentops.py recall --limit 6")
output.context.push("## Durable memory (auto-injected)\n" + recall)
```
`recall()`/`format_recall_for_prompt()`는 이미 존재 → "파일 존재"→"컨텍스트 주입"
마지막 1마일만 연결. H1의 USERDATA env와 합쳐야 재설치 후에도 유지.

### E5. command output compressor (P4)
`tool.execute.after`에서 output이 임계(200줄/8KB) 초과 시 head/tail+"전체는
diagnostics\<id>.log" 로 접기. pip list/tree/grep 대량 덤프 대상.

### E6. spinner final removal (P6)
소스 3곳 제거 확인. **빌드 산출물에 `spinner`/`<spinner>`/`opentui-spinner` 문자열
0인지 grep을 CI에 추가**(회귀 방지). `prompt/index.tsx`엔 직접 경로 없음.

### E7. TUI layout resize (P5)
OpenTUI가 `useTerminalDimensions`로 resize 처리 → 대부분 H1 창 최대화로 해결. 잔여
여백은 세션/프롬프트 패널 fixed width/padding 점검(소스 필요, 낮은 우선순위).

---

## F. 더 나은 대안 설계 (방향 재검토)

| 방향 | 효과 | 난이도 | 위험 | 1주 MVP | 추천 |
|---|---|---|---|---|---|
| ① 현 TUI 계속 패치 | 중 | 낮 | 낮 | 가능 | 병행(단기) |
| ② **proxy-level broker**(E1) | **높음** | 중 | 중(파일필요) | 가능 | **강력추천** |
| ③ headless runner + 로그필터 wrapper | 높음 | 중 | 중 | 가능 | 추천(2주차) |
| ④ LIG Agent Workbench GUI(Tkinter) | 매우높음 | 높 | 높 | 어려움 | 조건부(장기) |
| ⑤ local web UI | 매우높음 | 높 | 중 | 어려움 | ④ 대신 권장 |
| ⑥ job queue/checkpoint/heartbeat | 높음 | 중 | 중 | 가능(골격존재) | 추천 |
| ⑦ 화면=요약, 상세=파일 | 높음 | 중 | 낮 | 가능 | 추천 |

**Opus 최종 추천 경로:**
- **단기 MVP(1주)** = ①+②+⑦: 현 TUI에 H1/H2/권한프로파일 적용 + proxy broker로
  tool-call 정규화 + 표시분리(compressor). 이게 체감 문제의 80%를 닫는다.
- **중기(2~3주)** = ③+⑥: OpenCode를 headless/`opencode run`으로도 돌리고 얇은
  wrapper가 로그를 필터→요약 표시, 상세는 파일. 장시간 작업은 큐/heartbeat로 계속.
- **장기** = ⑤ local web UI: wrapper 위에 로컬 http UI를 얹어 "상태/최종답변/필요입력"만
  보이는 조용한 워크벤치로 진화. ④ 풀 GUI는 망분리 유지비 대비 비추천 → ⑤로 대체.

핵심 통찰: 사용자가 원하는 건 TUI 미화가 아니라 **"모델이 알아서 하고 결과만 조용히
보고하는 채널"**. 그건 ②(신뢰성)+⑦(조용함)+⑥(멈춤없음)로 달성되고, TUI/GUI는 그 다음이다.

---

## G. 추가로 반드시 받아야 할 파일 (P3 검증 전제)

패키지에 **LIG↔OpenCode tool-call 변환 코드가 없다**(`llm_client.py`는 agent_ops
전용 별도 클라이언트). `COLLECT_LIG_PROXY_FILES.bat`를 실행해 아래를 모아 주면 정확한
삽입 위치와 unified diff까지 제시 가능:
1. `lig_toolcall_proxy*.py`/`lig_proxy*.py`/`proxy.py`/`server.py` (**최우선**)
2. `openai_compat*.py`/`harmony*.py`/`tool_router.py`/`toolcall_adapter.py`/`provider_adapter.py`
3. 설치된 opencode의 **provider 설정**(`opencode.json`의 provider·model·baseURL, 키 제거)
4. 최근 `DIAG_OPENCODE_LIG.bat` 리포트 1개
5. `올바른 JSON 형식`/`tool=:`가 찍힌 **실제 세션 로그 20~40줄**
6. 회사 PC `chcp` 결과 1줄 + opencode를 cmd/Windows Terminal 중 무엇으로 실행하는지

---

## H. 바로 적용 가능한 산출물 (이 PR에 포함)

- **H1** `workspace-template/RUN_OPENCODE_LIG.bat.txt` — 인코딩/창/USERDATA/`--auto` 하드닝.
- **H2** `workspace-template/.opencode/plugins/command-guard.ts` — soft-block(1줄 throw,
  정상 shell-write 허용, 파괴/corruption/malformed만 차단). 아래는 요지 diff:
```diff
- throw new Error("AgentOps command guard BLOCKED ...\n- <여러 줄 영어 사유>\n...")
+ if (block) throw new Error(`AgentOps guard [${block.kind}]: ${block.hint}`) // 1줄
+ // python -c / echo> / 정상 heredoc 는 더 이상 차단하지 않음(파괴/미완결만 차단)
```
- **H3** `workspace-template/COLLECT_LIG_PROXY_FILES.bat.txt` — proxy/provider/model/로그
  수집기(읽기 전용, 비밀 제거 안내 포함).
- **H4** 30분 테스트 체크리스트(아래).

### H4. 30분 테스트 체크리스트 (회사 PC)
1. `RUN_OPENCODE_LIG.bat` 실행 → 창이 **최대화**로 뜨고 한글/박스문자 정상(외계어 0). (P1/P5)
2. 하단 배지 `[PERM:AUTO ...]` 확인, `Shift+Tab`로 ASK↔AUTO 토글. (P2)
3. "설치 확인용 README 만들어줘" → 코드 전문 없이 **경로+요약**만. (P3/P4)
4. "라이브러리 뭐 필요한지 정리해줘" → pip list 전량 없이 요약. (P4)
5. `rm -rf` 유사 명령 유도 → 네이티브 권한 `deny`로 차단(가드 1줄 메시지). (P2 안전)
6. 정상 파일쓰기(예: `python -c`/`echo>`) 시도 → **차단되지 않고** 동작. (P4 회귀방지)
7. 장시간 작업 → `Unknown component type spinner` 0. (P6)
8. opencode 재설치/패치 후 재실행 → 이전 세션 선호가 유지·주입되는지(=USERDATA). (P7)
9. 실패 유도 → 채팅엔 원인 1~2줄, 상세는 `USERDATA\diagnostics`. (P4)
10. `COLLECT_LIG_PROXY_FILES.bat` 실행 → provider 설정/로그 수집 확인 후 공유. (§G)

---

## I. PR 운영 계획

> 참고: 본 저장소 규칙상 개발은 지정 브랜치 1개(`claude/opencodelig-quality-review-*`)에서
> 진행한다. 아래는 리뷰/롤아웃을 논리적으로 쪼갠 **권고 시퀀스**이며, 현재 이 PR은
> #7 범위(+ 문서/수집기/권한프로파일)를 담고 있다. 별도 브랜치 분리가 필요하면 지시 요망.

| PR | 목적 | 변경 파일 | 위험도 | 테스트 | 롤백 |
|---|---|---|---|---|---|
| **#7(현재)** | 런처/인코딩/창/USERDATA/권한프로파일/수집기 안정화 | `RUN_OPENCODE_LIG.bat.txt`, `opencode.permission.example.json`, `COLLECT_LIG_PROXY_FILES.bat.txt`, 본 문서 | 낮 | H4 1~9 | 파일 되돌림, 기존 런처 사용 |
| **#8** | command-guard soft-block | `.opencode/plugins/command-guard.ts` | 낮~중 | H4 5·6 | 이전 플러그인 복원 |
| **#9** | proxy/tool-call broker | proxy 측 신규(파일 확보 후) | 중~높 | 파일생성/question fallback | proxy broker 비활성화 플래그 |
| **#10** | 출력 compressor/memory loader/headless wrapper | 플러그인 신규 | 중 | H4 3·4·8·9 | 플러그인 제거 |

각 PR은 draft로 열고 Windows 실검증 결과를 붙인 뒤 ready 전환.

---

## J. 테스트 계획 (회사 PC 검증, pass/fail 기록)
- **인코딩**: 한글 입출력·박스문자·배지 정상, 외계어 0.
- **권한**: `--auto` 자동승인 + `deny` 패턴은 확실히 차단, Shift+Tab/`/permission` 동작.
- **AUTO 연속**: permission·question·guard·parse-fail 각 케이스에서 불필요 정지 0.
- **파일생성**: write/edit JSON오류 0, 실패 시 safe_file_writer fallback.
- **question fallback**: raw JSON 대신 한국어 질문 1~3개.
- **로그 압축**: pip list/대량 grep이 요약+파일경로로만.
- **코드 노출 방지**: 파일 생성 시 경로+요약만.
- **창 resize/fullscreen**: 최대화+조절 시 레이아웃 꽉 참.
- **spinner**: 크래시 0.
- **memory 유지**: 재설치/패치 후 이전 선호가 새 세션 컨텍스트에 주입·반영.
- **diagnostics**: 실패 시 채팅 요약 + 상세 파일 분리.
- **모델/provider 확인**: `COLLECT_...bat`로 provider·model·baseURL 확보.
- **공식문서 대조**: `--auto`/`question`/권한패턴/websearch 조건이 §B 표와 일치.

---

## K. Opus orchestration summary
1. 파일 인벤토리: runtime은 permission patch·agent_ops·플러그인 2개, 나머지는 문서/BAT.
2. 인코딩: BAT 본문 ASCII-only(안전), 진짜 깨짐은 **생성 런처 chcp 부재**로 규명 → H1.
3. AUTO: permission patch 양호하나 `permission.asked`만 처리 → 멈춤 정체는 question/
   guard/parse-fail/자기중단. 공식 `--auto`+네이티브 권한으로 재설계.
4. tool-call: proxy 실물 부재 확인 → 수집기(H3)+§G 요청, broker 설계(E1).
5. UX: quiet가 지침뿐 → guard soft-block(H2)+compressor(E5).
6. 레이아웃: 대부분 런처 최대화로 해결.
7. spinner: 소스 3곳 제거 확인, 바이너리 grep만 잔여.
8. **공식문서 재검증**: `--auto`=네이티브 자동승인, `question`=permission 게이팅,
   bash/edit=deny 패턴 지원, websearch=EXA/OpenCode provider 한정 — 설계에 반영.
9. **Opus 판단**: 근본은 "런처 1곳 + tool-call proxy". 전자는 이 PR로 해결, 후자는 파일
   확보 선행. 파괴 차단은 플러그인 throw→네이티브 권한으로 이관하는 게 더 안전·조용.
10. **"완료" 미선언**: P3는 proxy 파일+Windows 실검증 전엔 확언 불가.
</content>
