# 회사 파일럿 Day 1

원칙: 각 단계는 명령, 기대 출력, 실패 시 바로 볼 RUNBOOK 항목을 남긴다. `lig-api.env` 실값과 gateway host/key는 문서, 보고서, 이슈에 복사하지 않는다.

| 순서 | 단계 | 명령 | 기대 출력 | 실패 시 |
|------|------|------|-----------|---------|
| 1 | 반입 zip 압축 해제 | `powershell -NoProfile -Command "Expand-Archive .\OpenCodeLIG.zip .\OpenCodeLIG -Force"` | `OpenCodeLIG\workspace-template\` 폴더 생성 | `docs\RUNBOOK.md`의 디스크 부족 항목 확인 |
| 2 | setup 실행 | `OpenCodeLIG\setup.bat` | Python 3.11 확인과 사용자 데이터 폴더 준비 완료 | `docs\RUNBOOK.md`의 콘솔/파일 한글 깨짐 항목 확인 |
| 3 | doctor 기준선 | `cd OpenCodeLIG\workspace-template` 후 `launch\diag.bat` | `lig_api_config`, `providers`, `operations` 섹션 출력 | `docs\RUNBOOK.md`의 gateway 설정 오류 항목 확인 |
| 4 | `lig-api.env` 작성 | `notepad %USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env` | `LIG_GATEWAY_BASE_URL`, `LIG_API_KEY`, route/model override 필요값 저장 | `docs\RUNBOOK.md`의 gateway 설정 오류 항목 확인 |
| 5 | gateway 3라우트 smoke | `launch\gateway-smoke.bat` | `lig-coding`, `lig-chat`, `lig-fallback` route 결과가 JSON에 기록 | `docs\RUNBOOK.md`의 LLM 무응답/timeout 항목 확인 |
| 6 | tool-call 형식 실측 | `launch\run-agent.bat --mode real --task "오늘 파일럿용 간단한 할 일 1개를 등록하고 결과를 알려줘"` | tool call id 대응 후 일정/결과가 생성되거나 명확한 실패 사유 출력 | `docs\RUNBOOK.md`의 tool-call 반복 실패 항목 확인 |
| 7 | 파서 분리 확인 | `launch\run-agent.bat --mode mock --task "한글 테스트: 오늘 오후 3시 파일럿 점검 일정 등록"` | mock 모드에서 한글 task가 깨지지 않고 정상 완료 | `docs\RUNBOOK.md`의 콘솔/파일 한글 깨짐 항목 확인 |
| 8 | 파일럿 기록 시작 | `notepad docs\PILOT_RECORD.md` | 12종 업무의 성공/실패/소요/개입 횟수 기록 | 실패율을 조작하지 말고 `docs\PILOT_BACKLOG.md` 후보로 남김 |

## 산출물 위치

- gateway smoke JSON: `launch\pilot_results\gateway\probe_gateway_YYYYMMDD.json`
- agent diagnostics: `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\`
- audit log: `%USERPROFILE%\OpenCodeLIG_USERDATA\audit\audit.jsonl`
- 업무 결과물: `%USERPROFILE%\OpenCodeLIG_USERDATA\results\`
