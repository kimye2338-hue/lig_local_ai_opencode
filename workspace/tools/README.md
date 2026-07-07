# 반입 목록 (오프라인) — 무엇을 어디에 넣나

**핵심 기능(대화·업무 지시·보고서·기억 위키)은 아래 것들 없이도 바로 동작한다.**
선택 기능(문서 읽기·진짜 Office 파일·화면 OCR)을 쓰려면 wheel을 설치한다.

지금 무엇이 준비됐는지 확인: `python agent_ops\agentops.py deps`

## 1. 파이썬 wheel — **이 패키지에 이미 포함됨** (`tools\wheelhouse`)

이 배포본에는 wheel이 `tools\wheelhouse` 에 **이미 들어 있다**. 설치만 하면 된다:
```bat
launch\install-tools.bat
```
(오프라인·인터넷 불필요. openpyxl/python-docx/python-pptx + markitdown + rapidocr 설치.)

수동으로 하려면:
```bat
pip install --no-index --find-links tools\wheelhouse openpyxl python-docx python-pptx markitdown[pdf,docx,pptx,xlsx] rapidocr-onnxruntime
```
- openpyxl·python-docx·python-pptx: 진짜 xlsx/docx/pptx **생성**
- markitdown: PDF/워드/PPT/엑셀 **읽기**
- rapidocr-onnxruntime: 화면 **OCR**(막힐 때 화면 글자 읽기)
- (windows-use = COM 없는 앱 조작: 의존성이 매우 커서 미포함. 필요 시 별도 반입.)

## 2. Obsidian (위키 열람, 선택) — 용량이 커서 직접 받기

- 설치본 1개(약 295MB)라 이 패키지엔 미포함. 인터넷 PC에서 직접 받아 회사 PC로 반입:
  `https://github.com/obsidianmd/obsidian-releases/releases/latest` → `Obsidian-x.x.x.exe`
- 회사 PC에서 그 exe를 1회 실행(오프라인 설치 가능) → `launch\wiki.bat` 가
  `%LOCALAPPDATA%\Obsidian\Obsidian.exe` 로 자동 인식. 포터블로 두려면 `tools\Obsidian\Obsidian.exe`.
- 없어도 위키(.md)는 정상 — 그래프/의미검색 UI만 없을 뿐. 상세: `docs\기능\OBSIDIAN_WIKI.md`.

## 3. OCR 엔진 (화면 읽기, 선택) — wheel은 포함됨

- RapidOCR wheel(rapidocr-onnxruntime + onnxruntime + opencv)은 `tools\wheelhouse` 에 포함.
  `launch\install-tools.bat` 로 함께 설치된다. 기본 모델은 wheel에 내장.
- 또는 Tesseract: `tools\ocr\tesseract\tesseract.exe` + `tessdata\kor+eng.traineddata`.
- 또는 Tesseract: `tools\ocr\tesseract\tesseract.exe` + `tessdata\kor.traineddata`,`eng.traineddata`.
- 상세: `docs\기능\OCR_SCREEN.md`.

## 4. (선택) 비상 로컬 LLM — 게이트웨이 다운 대비

- **무설치**: llamafile 단일 `.exe` 하나를 실행하면 로컬 OpenAI 호환 서버가 열린다.
- `lig-api.env` 의 `LIG_EMERGENCY_LOCAL_BASE_URL` 두 줄을 채우면 게이트웨이 실패 시 자동 폴백.
- 회사 PC에 로컬 런타임이 없으면 그냥 비워 두면 된다(아무 영향 없음).

> 실제 바이너리는 저장소에 커밋하지 않는다(용량·라이선스). 경로 규약과 안내만 관리한다.
