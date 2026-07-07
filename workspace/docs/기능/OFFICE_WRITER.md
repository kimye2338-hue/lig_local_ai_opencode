# Office 파일 생성 (오프라인, Office 설치 불필요)

순수 Python 라이브러리로 **Office 설치 없이** 진짜 .xlsx/.docx/.pptx 를 오프라인 생성한다.
지금까지 산출물은 .md 초안뿐이었고 docx/pptx 는 "app validation pending" 이었는데, 이 경로가
그 갭을 메운다. 회사 PC에 MS Office 가 있으면 COM 어댑터(excel_com/office_convert)를,
없거나 앱 없이 만들려면 이 경로를 쓴다.

모듈: `agent_ops/office_writer.py`. 엔진: openpyxl(.xlsx) / python-docx(.docx) / python-pptx(.pptx).

## 사용 (CLI — 모델이 에이전트 모드에서 호출)

```bat
rem CSV → 서식 있는 엑셀
python agent_ops/agentops.py report-xlsx --input "데이터.csv"

rem JSON 스펙 → Word/PPT
python agent_ops/agentops.py office-doc --kind docx --spec "spec.json"
python agent_ops/agentops.py office-doc --kind pptx --spec "spec.json"
```

스펙(JSON):
- docx: `{"title":"…","sections":[{"heading":"…","paragraphs":["…"],"bullets":["…"],"table":{"headers":["A","B"],"rows":[["1","2"]]}}]}`
- pptx: `{"title":"표지","slides":[{"title":"핵심 메시지","points":["근거1","근거2"]}]}` (1슬라이드=1메시지)

산출물은 `agent_ops/results/reports/` 아래. 미반입 시 조용히 실패하지 않고 어떤 wheel 을
넣어야 하는지 안내한다.

## 오프라인 반입

```bat
rem 인터넷 PC:
pip download python-docx python-pptx openpyxl -d wheelhouse
rem 회사 오프라인 PC:
pip install --no-index --find-links wheelhouse python-docx python-pptx openpyxl
```

`release/dependencies.json` 의 프리페치 목록('office-doc-wheels')에 포함 권장.

## 원칙 (docs 디자인 코퍼스와 연동)

- 기존 템플릿/서식·수식 보존, 숫자는 숫자형 저장, 출력 후 유효성(열림) 확인.
- PPT 1슬라이드=1메시지, 제목은 주장. 자세히: `agent_ops/knowledge/design/document_slides.md`.

## 라이선스

openpyxl(MIT), python-docx(MIT), python-pptx(MIT) — 사내 배포 무리 없음.

## 상태

- 생성·유효성(OOXML): 로컬 검증 완료(xlsx/docx/pptx 실제 생성 + 유효 확인).
- 회사 PC 실사용 서식 품질: 파일럿 검증 대기.
