# 회사 파일럿 기록 양식

성공률은 조작하지 않는다. 실패는 그대로 남기고, 재시도/사람 개입은 `개입 횟수`에 기록한다.

| # | 업무 | 명령 | 성공 기준 | 성공/실패 | 소요 | 개입 횟수 | 비고 |
|---|------|------|-----------|-----------|------|-----------|------|
| 1 | 아침 브리핑 (일정+액션아이템) | `launch\briefing.bat` | md 생성 + 일정/액션 반영 |  |  |  |  |
| 2 | 일정 등록/조회/완료 (자연어) | `py -3.11 agent_ops\agentops.py schedule add "내일 오전 10시 파일럿 점검"`<br>`py -3.11 agent_ops\agentops.py schedule today`<br>`py -3.11 agent_ops\agentops.py schedule done 1` | 등록, 조회, 완료가 같은 항목 기준으로 확인 |  |  |  |  |
| 3 | 시험 xlsx → 이상값 보고서+PPT | `py -3.11 agent_ops\agentops.py work --mode real --input pilot_inputs\시험결과.xlsx --task "시험 xlsx를 분석해 이상값 보고서와 발표용 PPT 초안을 만들어줘"` | 이상값 md 보고서 + PPT spec 생성 |  |  |  |  |
| 4 | 메일 분류+오늘 액션아이템 | `py -3.11 agent_ops\agentops.py work --mode real --input pilot_inputs\메일목록.txt --task "메일을 분류하고 오늘 처리할 액션아이템을 정리해줘"` | 분류 표 + 오늘 액션아이템 생성 |  |  |  |  |
| 5 | 회의 메모 → 회의록+일정 등록 | `py -3.11 agent_ops\agentops.py work --mode real --input pilot_inputs\회의메모.md --task "회의 메모를 회의록으로 정리하고 일정/담당 액션을 등록해줘"` | 회의록 md + 일정/담당 액션 반영 |  |  |  |  |
| 6 | 주간보고 초안 자동 생성 | `py -3.11 agent_ops\agentops.py weekly` | 이번 주 audit/schedule/artifact 기반 주간보고 초안 생성 |  |  |  |  |
| 7 | Excel 2016 데이터 정리 (COM 실행) | `py -3.11 agent_ops\agentops.py work --mode real --execute --input pilot_inputs\매출정리.xlsx --task "Excel 2016에서 사본 파일로 데이터를 정리하고 요약 시트를 만들어줘"` | `사본_` Excel 파일에 정리 결과 생성, 원본 불변 |  |  |  |  |
| 8 | 보고서 → HWP 2019 변환 | `py -3.11 agent_ops\agentops.py work --mode real --execute --input pilot_inputs\보고서.md --task "보고서 md를 HWP 2019 문서로 변환해줘"` | 신규 `.hwp` 파일 생성 |  |  |  |  |
| 9 | SolidWorks 2022 매크로 실행 (사본) | `py -3.11 agent_ops\agentops.py work --mode real --execute --input pilot_inputs\부품.SLDPRT --input pilot_inputs\검사매크로.swp --task "SolidWorks 2022에서 사본 문서에 매크로를 실행해줘"` | `사본_` 문서 사용, 원본 불변, 실행 결과 기록 |  |  |  |  |
| 10 | MATLAB 배치 후처리 실행 | `py -3.11 agent_ops\agentops.py work --mode real --execute --input pilot_inputs\후처리.m --task "MATLAB 배치로 후처리 스크립트를 실행하고 결과를 요약해줘"` | MATLAB batch exit 0 + 결과 요약 |  |  |  |  |
| 11 | AutoCAD .scr 일괄 처리 / Fluent journal 실행 중 1 | `py -3.11 agent_ops\agentops.py work --mode real --execute --input pilot_inputs\도면.dwg --input pilot_inputs\작업.scr --task "AutoCAD에서 사본 DWG에 scr 일괄 처리를 실행해줘"` | 사본 DWG 처리 또는 명확한 adapter 실패 기록 |  |  |  |  |
| 12 | 사내 웹페이지 텍스트 추출→요약 | `py -3.11 agent_ops\agentops.py work --mode real --task "열려 있는 Chrome 사내 웹페이지의 본문 텍스트를 추출해 요약해줘"` | Chrome CDP 텍스트 추출 + 요약 md 생성 |  |  |  |  |

## 파일럿 종료 판정

- 12종 중 10종 이상이 "지시 → 결과물" E2E로 성공하면 Day 1 목표 달성.
- 사람 개입은 업무당 승인 1회 이내를 목표로 기록한다.
- 실패 항목은 `docs\PILOT_BACKLOG.md`에 증상, 진단 파일, 재현 명령을 옮긴다.
