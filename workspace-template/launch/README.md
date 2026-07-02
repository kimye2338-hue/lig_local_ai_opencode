# OpenCodeLIG 실행 순서 (회사 PC 기준)

모든 명령은 이 `launch` 폴더에서 실행한다. 더블클릭 대신 CMD에서 실행해야 메시지를 볼 수 있다.

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

## 3. real 모드 (회사 gateway 필요 — company validation pending)

먼저 secret 파일을 채운다 (repo 밖, 로컬 전용):

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env
(템플릿: workspace-template\config\lig-api.env.example)
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

- `--make-artifacts`를 붙이면 `agent_ops\results\artifacts\<실행시각>\`에
  열어서 바로 쓸 수 있는 scaffold(.bas/.md/slide_spec.json/.py)를 생성한다.
- 현재 가능한 capability 전체 목록은 `diag.bat` 출력의 `capabilities` 섹션,
  앱 실행 연동 상태는 `app_adapters` 섹션 참고 (실제 앱 실행은 아직 전부 pending).

## 4. 문제 발생 시

```bat
diag.bat
resume.bat
```

- 진단 파일: `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\`
  (`agent-loop-last.json`, `tool-dispatch-history.jsonl`, `runtime-last.json` 등, secret-free)
