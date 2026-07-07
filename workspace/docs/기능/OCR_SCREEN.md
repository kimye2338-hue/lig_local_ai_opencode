# 화면 OCR (한/영, 오프라인)

브라우저/앱 자동화 중 **화면을 봐야만 알 수 있는 상황**(포털 SPA가 예상과 다르게
렌더링, 버튼/에러가 이미지로만 표시)에서 스크린샷을 찍어 글자를 읽고 다음 행동을
판단한다. 완전 오프라인.

모듈: `agent_ops/adapters/ocr_screen.py` (어댑터 id `ocr_screen`).

## action

```python
from agent_ops.adapters import ocr_screen
ocr_screen.execute("capabilities", {})          # 사용 가능한 백엔드 확인
ocr_screen.execute("read_screen", {"lang": "korean+english"})   # 전체 화면
ocr_screen.execute("read_screen", {"region": [x, y, w, h]})     # 영역 지정
ocr_screen.execute("read_image", {"path": "shot.png"})          # 기존 이미지
```

반환: `{ok, engine, text, lines:[{text,score,box}], source_image, ...}`.
백엔드가 없으면 조용히 실패하지 않고 `ok:false, error:"OCR 엔진 미반입"`으로 안내.

## 스크린샷 캡처 (무설치 폴백 내장)

우선순위: **mss → Pillow(ImageGrab) → PowerShell**. 앞의 둘이 없어도 Windows면
PowerShell로 전체 화면을 캡처하므로 추가 설치 없이 동작한다.

## OCR 엔진 반입 (둘 중 하나)

오프라인 PC라 엔진은 **반입**한다. 경로 규약(`%USERPROFILE%\OpenCodeLIG\tools\ocr\`,
또는 `LIG_OCR_DIR` 환경변수):

1. **RapidOCR (권장 — 한/영 동시, 언어팩 불필요)**
   - `pip`용 wheel(`rapidocr_onnxruntime`, `onnxruntime`)과 모델을 반입해 설치.
   - import 되면 자동 우선 사용.
2. **Tesseract (대안)**
   - `tools\ocr\tesseract\tesseract.exe`
   - `tools\ocr\tesseract\tessdata\kor.traineddata`, `eng.traineddata`
   - `pytesseract` wheel 설치. 언어는 `kor+eng` 자동.

## 브라우저 막힘 시 폴백 (통합 지점)

권장 사용 패턴: `browser_cdp`로 DOM 조작이 실패/모호할 때, LLM이 `ocr_screen.read_screen`을
호출해 화면 텍스트를 확보 → 그 텍스트를 근거로 다음 셀렉터/좌표를 결정. (LLM 툴 노출은
`tool_dispatch`에 `ocr_read_screen` 툴로 등록해 확장 — 현재 어댑터 레지스트리에 등록됨.)

## 상태

- 어댑터/스크린샷 폴백: 구현 완료(구문·capabilities 검증).
- 실제 한/영 인식 정확도: 회사 PC에서 엔진 반입 후 검증 대기(app validation pending).
