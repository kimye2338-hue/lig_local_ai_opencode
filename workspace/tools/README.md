# 반입 목록 (오프라인) — 무엇을 어디에 넣나

이 폴더에는 **설치 파일·바이너리·wheel 이 기본 포함돼 있지 않다**(용량·라이선스 때문).
아래는 선택 기능을 쓰려면 인터넷 되는 PC에서 받아 회사 PC로 반입하는 목록이다.
**핵심 기능(대화·업무 지시·보고서·기억 위키)은 이것들 없이도 바로 동작한다.**

지금 무엇이 준비됐는지 확인: `python agent_ops\agentops.py deps`

## 1. 파이썬 wheel (한 번에 받기)

인터넷 PC에서:
```bat
pip download markitdown[pdf,docx,pptx,xlsx] python-docx python-pptx openpyxl windows-use -d wheelhouse
```
회사 PC에서(폴더째 반입 후):
```bat
pip install --no-index --find-links wheelhouse markitdown[pdf,docx,pptx,xlsx] python-docx python-pptx openpyxl windows-use
```
- markitdown: PDF/워드/PPT/엑셀 **읽기**
- openpyxl·python-docx·python-pptx: 진짜 xlsx/docx/pptx **생성**(대개 이미 있음 — deps로 확인)
- windows-use: COM 없는 Windows 앱 조작(선택)

## 2. Obsidian (위키 열람, 선택)

- 무설치 포터블 권장: `tools\Obsidian\Obsidian.exe` 로 배치 → `launch\wiki.bat` 가 자동 인식.
- 또는 일반 설치(그러면 `%LOCALAPPDATA%\Obsidian\Obsidian.exe` 도 인식).
- 없어도 위키(.md)는 정상 — 그래프/의미검색 UI만 없을 뿐. 상세: `docs\OBSIDIAN_WIKI.md`.

## 3. OCR 엔진 (화면 읽기, 선택)

- RapidOCR(권장): `rapidocr_onnxruntime`+`onnxruntime` wheel 반입, 모델은 `tools\ocr\rapidocr\`.
- 또는 Tesseract: `tools\ocr\tesseract\tesseract.exe` + `tessdata\kor.traineddata`,`eng.traineddata`.
- 상세: `docs\OCR_SCREEN.md`.

## 4. (선택) 비상 로컬 LLM — 게이트웨이 다운 대비

- **무설치**: llamafile 단일 `.exe` 하나를 실행하면 로컬 OpenAI 호환 서버가 열린다.
- `lig-api.env` 의 `LIG_EMERGENCY_LOCAL_BASE_URL` 두 줄을 채우면 게이트웨이 실패 시 자동 폴백.
- 회사 PC에 로컬 런타임이 없으면 그냥 비워 두면 된다(아무 영향 없음).

> 실제 바이너리는 저장소에 커밋하지 않는다(용량·라이선스). 경로 규약과 안내만 관리한다.
