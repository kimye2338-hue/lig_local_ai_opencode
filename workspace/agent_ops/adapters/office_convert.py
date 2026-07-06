# -*- coding: utf-8 -*-
"""Word/PowerPoint COM conversion actions that create new files only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..audit import record as audit_record

try:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore
    _PYWIN32_ERROR = ""
except Exception as exc:  # pragma: no cover - environment dependent
    pythoncom = None  # type: ignore
    win32com = None  # type: ignore
    _PYWIN32_ERROR = exc.__class__.__name__

ACTIONS = ("md_to_docx", "spec_to_pptx")
DOCX_FORMAT = 16
PPTX_FORMAT = 24


def _missing_pywin32() -> Dict[str, Any]:
    return {"ok": False, "error": "pywin32 미설치 — dependencies.json 'pywin32' 참조"}


def _need_pywin32() -> Optional[Dict[str, Any]]:
    if _PYWIN32_ERROR or pythoncom is None or win32com is None:
        return _missing_pywin32()
    return None


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for idx in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_{idx}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("output name exhausted")


def _output_path(src: Path, options: Dict[str, Any], suffix: str) -> Path:
    raw = str(options.get("output_path") or "").strip()
    if raw:
        target = Path(raw).expanduser().resolve()
        if target.exists():
            return _unique_path(target)
        return target
    return _unique_path(src.with_suffix(suffix))


def _audit(action: str, options: Dict[str, Any], result: Dict[str, Any]) -> None:
    audit_record({
        "kind": "adapter",
        "name": f"office_convert.{action}",
        "target": options.get("path") or options.get("spec_path") or result.get("path", ""),
        "risk": "dangerous",
        "verdict": "approved" if result.get("ok") else "failed",
        "detail": result.get("error", ""),
    })


def _md_blocks(text: str) -> List[Dict[str, str]]:
    blocks: List[Dict[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# "):
            blocks.append({"style": "Title", "text": line[2:].strip()})
        elif line.startswith("## "):
            blocks.append({"style": "Heading 1", "text": line[3:].strip()})
        elif line.startswith("### "):
            blocks.append({"style": "Heading 2", "text": line[4:].strip()})
        elif line.startswith(("- ", "* ")):
            blocks.append({"style": "List Bullet", "text": line[2:].strip()})
        else:
            blocks.append({"style": "Normal", "text": line})
    return blocks or [{"style": "Normal", "text": text.strip()}]


def _md_to_docx(options: Dict[str, Any]) -> Dict[str, Any]:
    missing = _need_pywin32()
    if missing:
        return missing
    src = Path(str(options.get("path") or "")).expanduser().resolve()
    if not src.exists():
        return {"ok": False, "error": "Markdown 파일 없음"}
    out = _output_path(src, options, ".docx")
    word = None
    doc = None
    try:
        pythoncom.CoInitialize()
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = bool(options.get("visible", False))
        word.DisplayAlerts = 0
        doc = word.Documents.Add()
        for block in _md_blocks(src.read_text(encoding="utf-8", errors="replace")):
            para = doc.Paragraphs.Add()
            para.Range.Text = block["text"]
            try:
                para.Range.Style = block["style"]
            except Exception:
                pass
            para.Range.InsertParagraphAfter()
        out.parent.mkdir(parents=True, exist_ok=True)
        doc.SaveAs2(str(out), FileFormat=DOCX_FORMAT)
        return {"ok": True, "path": str(out)}
    except Exception as exc:
        return {"ok": False, "error": f"md_to_docx failed: {exc.__class__.__name__}"}
    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _slides_from_spec(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    slides = spec.get("slides")
    if isinstance(slides, list) and slides:
        return [s if isinstance(s, dict) else {"title": str(s), "points": []} for s in slides]
    return [{"title": str(spec.get("title") or "Presentation"), "points": spec.get("points") or []}]


def _spec_to_pptx(options: Dict[str, Any]) -> Dict[str, Any]:
    missing = _need_pywin32()
    if missing:
        return missing
    src = Path(str(options.get("spec_path") or options.get("path") or "")).expanduser().resolve()
    if not src.exists():
        return {"ok": False, "error": "slide spec 파일 없음"}
    out = _output_path(src, options, ".pptx")
    ppt = None
    deck = None
    try:
        spec = json.loads(src.read_text(encoding="utf-8", errors="replace"))
        pythoncom.CoInitialize()
        ppt = win32com.client.DispatchEx("PowerPoint.Application")
        deck = ppt.Presentations.Add()
        for idx, slide_spec in enumerate(_slides_from_spec(spec), start=1):
            slide = deck.Slides.Add(idx, 2)
            title = str(slide_spec.get("title") or f"Slide {idx}")
            points = slide_spec.get("points") or []
            slide.Shapes.Title.TextFrame.TextRange.Text = title
            body = slide.Shapes.Placeholders(2).TextFrame.TextRange
            body.Text = "\r".join(str(point) for point in points)
        out.parent.mkdir(parents=True, exist_ok=True)
        deck.SaveAs(str(out), PPTX_FORMAT)
        return {"ok": True, "path": str(out), "slides": len(_slides_from_spec(spec))}
    except Exception as exc:
        return {"ok": False, "error": f"spec_to_pptx failed: {exc.__class__.__name__}"}
    finally:
        if deck is not None:
            try:
                deck.Close()
            except Exception:
                pass
        if ppt is not None:
            try:
                ppt.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def execute(action: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """Execute one conversion action. Never overwrites source files."""
    opts = options if isinstance(options, dict) else {}
    action_name = str(action or "")
    try:
        if action_name not in ACTIONS:
            result = {"ok": False, "error": f"unknown action: {action_name}", "available_actions": list(ACTIONS)}
        elif action_name == "md_to_docx":
            result = _md_to_docx(opts)
        else:
            result = _spec_to_pptx(opts)
    except Exception as exc:
        result = {"ok": False, "error": f"{action_name} failed: {exc.__class__.__name__}"}
    _audit(action_name, opts, result)
    return result
