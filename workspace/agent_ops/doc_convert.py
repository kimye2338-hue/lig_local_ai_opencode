# -*- coding: utf-8 -*-
"""문서 → Markdown 변환 (오프라인) — microsoft/markitdown 래퍼.

우리 `input_ingest`는 지금까지 PDF/DOCX/PPTX/HTML 을 읽지 못했다(.csv/.xlsx/.txt 등만).
markitdown(MIT)은 그 포맷들을 **완전 오프라인**으로 Markdown 으로 변환한다(코어는 순수
Python, PDF/Office 는 wheel extras — 클라우드/LLM 불필요, 이미지 캡션 등만 opt-in).

설계(우리 optional-dep 패턴과 동일 — openpyxl/RapidOCR 처럼):
  - markitdown 이 설치돼 있으면 사용, 없으면 **조용히 실패하지 않고** "반입 필요"로 안내.
  - 네트워크 0. 이미지 캡션/오디오 전사/YouTube 같은 온라인 기능은 쓰지 않는다.

반입(오프라인): 내부망 wheelhouse 로
  `markitdown[pdf,docx,pptx,xlsx]` (+ 의존 wheel) 을 pip 설치. docs/기능/DOC_CONVERT.md 참고.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

# markitdown 이 변환할 수 있고 우리가 오프라인으로 신뢰하는 확장자.
MARKITDOWN_SUFFIXES = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
    ".html", ".htm", ".xml", ".epub", ".rtf", ".odt",
}

_EXTRA_HINT = {
    ".pdf": "markitdown[pdf]", ".docx": "markitdown[docx]", ".doc": "markitdown[docx]",
    ".pptx": "markitdown[pptx]", ".ppt": "markitdown[pptx]",
    ".xlsx": "markitdown[xlsx]", ".xls": "markitdown[xls]",
}


def available() -> bool:
    try:
        import markitdown  # noqa: F401
        return True
    except Exception:
        return False


def can_convert(suffix: str) -> bool:
    return suffix.lower() in MARKITDOWN_SUFFIXES


def _hint_for(suffix: str) -> str:
    return _EXTRA_HINT.get(suffix.lower(), "markitdown[pdf,docx,pptx,xlsx]")


def convert_file(path: Path) -> Dict[str, Any]:
    """파일을 Markdown 으로 변환. 반환 {ok, markdown, suffix, engine, error?, hint?}.

    markitdown 미설치/변환 실패 시 ok=False + 반입 안내(조용한 실패 금지).
    """
    suffix = path.suffix.lower()
    if not can_convert(suffix):
        return {"ok": False, "suffix": suffix, "error": f"markitdown 대상 아님: {suffix}"}
    if not available():
        return {"ok": False, "suffix": suffix,
                "error": "markitdown 미반입",
                "hint": f"내부망 wheelhouse 로 {_hint_for(suffix)} 설치 필요 — docs/기능/DOC_CONVERT.md"}
    try:
        from markitdown import MarkItDown  # type: ignore
        # enable_plugins=False, LLM client 미지정 → 완전 오프라인(온라인 기능 비활성).
        md = MarkItDown(enable_plugins=False)
        result = md.convert(str(path))
        text = getattr(result, "text_content", None)
        if text is None:  # 구버전 호환
            text = getattr(result, "markdown", "") or str(result)
        return {"ok": True, "suffix": suffix, "engine": "markitdown",
                "markdown": text, "chars": len(text)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "suffix": suffix,
                "error": f"markitdown 변환 실패: {exc!r}",
                "hint": f"필요 extra: {_hint_for(suffix)}"}


def convert_html(html: str) -> Dict[str, Any]:
    """HTML 문자열(예: browser_cdp 로 받은 포털 페이지)을 깔끔한 Markdown 으로.

    브라우저 어댑터가 받은 raw HTML 을 LLM 에 넣기 전에 정리하는 용도.
    """
    if not available():
        return {"ok": False, "error": "markitdown 미반입", "hint": "markitdown wheel 반입 필요"}
    try:
        import io
        from markitdown import MarkItDown, StreamInfo  # type: ignore
        md = MarkItDown(enable_plugins=False)
        stream = io.BytesIO(html.encode("utf-8"))
        result = md.convert_stream(stream, stream_info=StreamInfo(extension=".html", mimetype="text/html"))
        text = getattr(result, "text_content", None) or getattr(result, "markdown", "") or ""
        return {"ok": True, "engine": "markitdown", "markdown": text, "chars": len(text)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"markitdown HTML 변환 실패: {exc!r}"}


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(convert_file(Path(sys.argv[1])), ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"available": available(),
                          "suffixes": sorted(MARKITDOWN_SUFFIXES)}, ensure_ascii=False, indent=2))
