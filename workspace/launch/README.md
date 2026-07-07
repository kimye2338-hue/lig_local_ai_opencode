# OpenCodeLIG 실행 순서 (회사 PC 기준)

일반 사용자는 `launch\menu.bat`(AI비서 메뉴)를 실행하면 된다 —
업무 시키기 / 아침 브리핑 / 주간보고 / 상태 진단 / 게이트웨이 점검이 번호 메뉴로 뜬다.
이 문서에 나오는 개별 bat(`briefing.bat`, `diag.bat`, `probe-*.bat` 등)를 직접 쓸 때는
더블클릭 대신 CMD에서 실행해야 메시지가 창이 바로 닫히지 않고 남는다.

모든 bat는 `_py.bat`가 Python을 자동으로 찾아 쓴다 — `py -3.11`이 없어도
`python`(3.11.x이기만 하면) 또는 `python3.11`/`python3`만 있으면 그대로 동작한다.
산출물로 생성되는 `.md` 파일은 일반 텍스트라 메모장으로 열어도 된다.

## 1. 환경 점검

```bat
diag.bat
```

- Python 3.11 / provider 설정(lig-api.env) / 사용 가능한 도구 목록을 한 번에 보여준다.
- secret 값은 출력되지 않는다 (presence flag만).

## 2. mock 모드로 파이프라인 검증 (회사 API 불필요)

```bat
run-agent.bat --mode mock --task "한글 문서를 읽고 요약 파일을 만들어줘"
```

- mock LLM이 write → read → 최종 응답 흐름을 실제 파일 작업으로 수행한다.
- 결과: `모의_결과\작업_요약.md` 생성, 응답은 `agent_ops\results\llm_responses\agent_cli_last.md`.
- mock 모드는 파이프라인 검증용이며 실제 모델 응답이 아니다.

## 3. real 모드 (회사 gateway — 2026-07-05 회사 실측 완료)

회사 PC 실측으로 real gateway 파이프라인(요청→tool-use→응답) end-to-end 성공,
업무 시나리오 6/6 확인됨(`probe/results/company_check_20260705.md`). 다만 게이트웨이
주소/키(`lig-api.env`)는 PC마다 로컬로 채워야 한다 — repo에는 절대 들어가지 않는다.

먼저 secret 파일을 채운다 (repo 밖, 로컬 전용):

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env
(템플릿: config\lig-api.env.example)
```

그 다음:

```bat
run-agent.bat --mode real --task "작업 설명"
```

- 설정이 비어 있으면 무엇이 빠졌는지 알려주고 종료한다 (exit 2).

## 3-1. 업무 계획/산출물 scaffold (API 불필요)

```bat
py -3.11 ..\agent_ops\agentops.py plan --task "Excel 매크로 만들어줘" --make-artifacts
```

- 요청이 어떤 capability(문서/매크로/PPT/브라우저/메일 등)로 처리되는지,
  왜 그렇게 판단했는지(matched_keywords/confidence)와
  app/company validation pending 항목을 보여준다.
- 복합 업무도 자동 분해된다. 예:

  ```bat
  py -3.11 ..\agent_ops\agentops.py plan --task "시험 결과 파일 읽고 표 정리해서 보고서와 PPT 초안 만들어줘" --make-artifacts
  ```

- `--input 파일또는폴더` (반복 지정 가능)를 붙이면 실제 입력 자료를 읽고
  그 내용(CSV 행/열/이상 행, 로그 ERROR 건수, 매크로 진입점, 메일 목록 등)을
  산출물에 반영한다. 지원: MD/TXT/CSV/TSV/LOG/PY/BAS/BAT/JSON.

  ```bat
  py -3.11 ..\agent_ops\agentops.py plan --task "시험 결과 파일 읽고 이상값 정리해서 보고서 만들어줘" --input ..\..\시험결과.csv --make-artifacts
  ```

  - 출력의 `input-grounded: 예/아니오`가 입력 반영 여부를 정직하게 알려준다
    (입력 파일명이 산출물에 반영되지 않으면 품질 검사가 실패한다).
  - 미지원 형식(바이너리 등)은 산출물의 "입력 자료" 섹션에 미반영으로 명시된다.
  - 읽은 입력 요약(work context)은 secret-free로
    `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\work-context-last.json`에 저장된다.

- `--make-artifacts`를 붙이면 `agent_ops\results\artifacts\<실행시각>\`에
  열어서 바로 쓸 수 있는 scaffold(.bas/.md/slide_spec.json/.py)를 생성한다.
  - 생성 직후 품질 검사(artifact quality validator)가 자동 실행되어
    "품질 검사 [kind]: OK (n rules)" 형태로 결과를 보여준다.
  - 한 요청에서 나온 보고서/슬라이드/매크로는 같은 실행 ID와 작업 요약을
    공유한다 (파일 상단 "작업 컨텍스트" 참고).
- plan 출력에는 계획 근거(matched_keywords/confidence) 외에
  `task_summary`/`artifact_plan`/`validation_plan`/`next_exact_command`와
  app/company pending 구분이 포함된다.
- LLM이 scaffold의 TODO를 채우는 enrich 경로는 mock으로 검증되어 있고,
  실제 gateway 연동은 company validation pending이다.
- 현재 가능한 capability 전체 목록은 `diag.bat` 출력의 `capabilities` 섹션,
  앱 실행 연동 상태는 `app_adapters` 섹션, 계획/품질/enrich 상태는
  `artifact_pipeline` 섹션 참고. office(Excel)/outlook/matlab/hwp/autocad/browser는
  회사 실측 완료(available). SolidWorks(연결만 확인)/Fluent/office의 Word·PPT 변환은
  아직 pending.

## 4. 문제 발생 시

```bat
diag.bat
resume.bat
```

- 진단 파일: `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\`
  (`agent-loop-last.json`, `tool-dispatch-history.jsonl`, `runtime-last.json` 등, secret-free)

## 5. 로컬 LLM으로 real 모드 검증 (Ollama, locally validated 대상)

집 PC나 별도 검증 PC에 Ollama가 이미 설치되어 있을 때만 수행한다. 이 절은 회사 gateway 검증이 아니라 `local_openai` 프로필 실측이다.

```bat
ollama pull qwen2.5:7b-instruct
set LIG_PROVIDER_PROFILE=local_openai
set LIG_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
set LIG_LOCAL_MODEL=qwen2.5:7b-instruct
run-agent.bat --mode real --task "메모.txt 파일을 읽고 요약해서 요약.md로 저장해줘"
```

- 7B가 느리거나 VRAM/RAM이 부족하면 `qwen2.5:3b-instruct`로 낮추고 보고서에 모델 변경을 기록한다.
- `diag.bat`의 `llm_endpoints` 섹션에서 프로필, route 설정 여부, 로컬 endpoint 도달 여부를 확인한다. secret 값과 내부 host 원문은 출력하지 않는다.
- 자동 회귀용 스모크 테스트는 다음 명령이다. 서버가 없으면 SKIP+exit 0으로 끝나며 실패로 보지 않는다.

```bat
cd /d %USERPROFILE%\OpenCodeLIG\workspace
py -3.11 tests\test_real_llm_smoke.py
```
