# 문서 → Markdown 변환 (오프라인, markitdown)

`input_ingest`가 지금까지 못 읽던 **PDF·DOCX·PPTX·HTML·XLS 등**을 오프라인으로 읽게
한다. microsoft/**markitdown**(MIT)을 optional dependency 로 감싸, 있으면 쓰고 없으면
명확히 "반입 필요"로 안내한다(조용한 실패 없음). 네트워크 0 — 이미지 캡션/오디오
전사/YouTube 같은 온라인 기능은 쓰지 않는다.

모듈: `agent_ops/doc_convert.py`. 지원 확장자: PDF, DOCX/DOC, PPTX/PPT, XLSX/XLS,
HTML/HTM, XML, EPUB, RTF, ODT.

## 동작

- `--input 회의자료.pdf` 처럼 문서를 넣으면 markitdown 으로 Markdown 변환 후 기존
  텍스트 분석(facts/preview/notable)에 태운다. 비밀정보 마스킹도 그대로 적용.
- markitdown 미반입이면 해당 파일을 `unsupported` 로 두고 어떤 wheel 을 넣어야 하는지 안내.
- browser_cdp 로 받은 포털 HTML 을 깔끔한 Markdown 으로 정리: `doc_convert.convert_html(html)`.

## 오프라인 반입 (air-gap)

markitdown 은 코어가 순수 Python, PDF/Office 는 wheel extras 다. 인터넷 되는 PC에서
wheelhouse 를 만들어 회사 PC로 반입한다:

```bat
rem 인터넷 되는 PC에서 (Python 3.11):
pip download "markitdown[pdf,docx,pptx,xlsx]" -d wheelhouse

rem 회사 오프라인 PC에서:
pip install --no-index --find-links wheelhouse "markitdown[pdf,docx,pptx,xlsx]"
```

- 클라우드/LLM extras(`[az-doc-intel]`, `[audio-transcription]`, `[youtube-transcription]`)는
  **넣지 않는다** — 오프라인 용도에 불필요하고 네트워크를 요구한다.
- `release/dependencies.json` 의 프리페치 목록에 `markitdown[pdf,docx,pptx,xlsx]` 추가 권장.

## 라이선스

markitdown: MIT. 사내 배포 무리 없음.

## 검증

- 어댑터/우아한 실패: 구현·검증 완료(미설치 시 반입 안내, 설치 시 변환).
- 실제 PDF/DOCX 변환 품질: 회사 PC에서 wheel 반입 후 검증 대기.
