# tools/ — 반입 바이너리 (오프라인)

인터넷이 없는 회사 PC용으로, 외부에서 받아 **반입**하는 실행 파일을 여기에 둡니다.
설치 시 이 폴더는 `%USERPROFILE%\OpenCodeLIG\tools\`로 복사됩니다.

## Obsidian (LLM 위키 열람/편집)

포터블 실행 파일을 아래 경로에 배치하면 `launch\wiki.bat`가 자동 인식합니다:

```
tools\Obsidian\Obsidian.exe
```

자세한 절차: `docs\OBSIDIAN_WIKI.md`.

## OCR 엔진 (화면 인식, 한/영)

오프라인 OCR 백엔드 중 하나를 반입해 두면 `senses` OCR가 자동 사용합니다
(자세한 경로/우선순위: `docs\OCR_SCREEN.md`).

- RapidOCR (onnxruntime, 권장): 모델 파일을 `tools\ocr\rapidocr\`에.
- 또는 Tesseract: `tools\ocr\tesseract\tesseract.exe` + `tessdata\kor.traineddata`,`eng.traineddata`.

> 이 폴더의 실제 바이너리는 저장소에 커밋하지 않습니다(용량·라이선스). 경로 규약과
> 안내만 관리하고, 바이너리는 반입 규정에 따라 배치합니다.
