# 레퍼런스 지식베이스 — 작성 규약 (수집 에이전트/사람 공용)

이 폴더는 **큐레이션된 사실**의 층이다(개인 기억과 분리). 모델이 "이거 만들어줘"에
정확한 근거로 즉시 답하도록, 공학 도메인·규격·소프트스킬·소프트웨어 API를 담는다.

## 폴더
- `apis/` 소프트웨어 API·명령 (SolidWorks 2022 / AutoCAD 2019 / Fluent 2024R1 / MATLAB
  R2024a / Excel·Outlook VBA / Python / CMD·PowerShell / Windows)
- `domains/` 공학 도메인 (구조·진동·열유체·유도탄·공력·기구·전자·HW·케이블·치구 등)
- `standards/` 규격 (MIL-STD-810H, 금속·나사 규격 등)
- `lifeskills/` 소프트스킬 (협상·커리어·ADHD·성과·문서·논문 등)
- `_moc/<도메인>.md` Maps of Content — 도메인 허브(하위주제 지도)

## 노트 규약 (팩트체크)
모든 노트는 프론트매터로 시작한다:
```yaml
---
title: 진동해석 기초
domain: 진동해석
aliases: 진동, vibration, 모달, modal, 랜덤진동
sources: [출처 URL/문서, ...]     # 출처 없는 주장 금지
verified: true                    # 교차검증 통과(아니면 draft)
confidence: high                  # high | medium | low
version: (해당 시 소프트웨어/규격 버전)
reviewed: 2026-07-07
---
```
본문은 `## 주제` 섹션으로 나눈다(주입기가 작업 관련 섹션만 골라 넣는다). 수치·규격은
"출처에 이렇게 명시"를 병기한다. 확실치 않으면 `verified: false`(draft)로 두면 주입 시
'미검증' 꼬리표가 붙는다.

## 검색 동작
작업 프롬프트 → 키워드로 관련 노트 감지 → 해당 도메인 MOC(지도) + 노트의 작업 섹션 주입.
`python -m agent_ops.knowledge_base "진동 시험 지그"` 로 무엇이 주입되는지 확인.
