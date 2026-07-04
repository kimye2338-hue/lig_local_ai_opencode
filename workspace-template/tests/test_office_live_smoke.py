# -*- coding: utf-8 -*-
"""Live Office COM smoke for P15-04.

Run: py -3.11 tests\\test_office_live_smoke.py
Skips cleanly when pywin32 or Office COM is unavailable.
"""
from __future__ import annotations

import gc
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

tmp_root = Path(tempfile.mkdtemp(prefix="office_live_test_"))
os.environ["AGENTOPS_ROOT"] = str(tmp_root / "agentops")
os.environ["LIG_AUDIT_DIR"] = str(tmp_root / "audit")
os.environ["LIG_SCHEDULE_DIR"] = str(tmp_root / "schedule")

WS_TEMPLATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS_TEMPLATE))

from agent_ops.adapters import ADAPTERS  # noqa: E402
from agent_ops.adapters import excel_com, office_convert  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: object = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def _proc_count(image: str) -> int:
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {image}"],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return -1
    return sum(1 for line in output.splitlines() if line.lower().startswith(image.lower()))


def _wait_count(image: str, expected: int) -> int:
    count = _proc_count(image)
    for _ in range(20):
        if count == expected:
            return count
        time.sleep(0.25)
        gc.collect()
        count = _proc_count(image)
    return count


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _create_workbook(path: Path) -> None:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore

    pythoncom.CoInitialize()
    xl = None
    wb = None
    try:
        xl = win32com.client.DispatchEx("Excel.Application")
        xl.Visible = False
        xl.DisplayAlerts = False
        wb = xl.Workbooks.Add()
        ws = wb.Worksheets(1)
        ws.Range("A1").Value = "original"
        ws.Range("B1").Value = 10
        wb.SaveAs(str(path), FileFormat=51)
    finally:
        if wb is not None:
            wb.Close(SaveChanges=False)
        if xl is not None:
            xl.Quit()
        wb = None
        xl = None
        gc.collect()
        pythoncom.CoUninitialize()


def _open_generated_files(docx: Path, pptx: Path) -> None:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore

    pythoncom.CoInitialize()
    word = None
    doc = None
    ppt = None
    deck = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(str(docx), ReadOnly=True)
        check("docx opens and contains title", "변환 테스트" in doc.Content.Text)
        doc.Close(SaveChanges=False)
        doc = None
        word.Quit()
        word = None
        gc.collect()

        ppt = win32com.client.DispatchEx("PowerPoint.Application")
        deck = ppt.Presentations.Open(str(pptx), ReadOnly=True, Untitled=False, WithWindow=False)
        check("pptx opens with expected slides", deck.Slides.Count == 2, deck.Slides.Count)
        deck.Close()
        deck = None
        ppt.Quit()
        ppt = None
        gc.collect()
    finally:
        if doc is not None:
            doc.Close(SaveChanges=False)
        if word is not None:
            word.Quit()
        if deck is not None:
            deck.Close()
        if ppt is not None:
            ppt.Quit()
        gc.collect()
        pythoncom.CoUninitialize()


def main() -> None:
    if excel_com._PYWIN32_ERROR or office_convert._PYWIN32_ERROR:
        print("SKIP Office live smoke - pywin32 unavailable, skipped not failed")
        return

    before = {
        "EXCEL.EXE": _proc_count("EXCEL.EXE"),
        "WINWORD.EXE": _proc_count("WINWORD.EXE"),
        "POWERPNT.EXE": _proc_count("POWERPNT.EXE"),
    }
    if any(value < 0 for value in before.values()):
        print("SKIP Office live smoke - tasklist unavailable, skipped not failed")
        return

    source = tmp_root / "office_source.xlsx"
    _create_workbook(source)
    original_hash = _sha256(source)

    opened = excel_com.execute("open_copy", {"path": str(source)})
    check("excel open_copy succeeds", opened.get("ok"), opened)
    copy_path = Path(opened["copy_path"])
    written = excel_com.execute("write_range", {"sheet": "Sheet1", "range": "A2", "values": "copy-write"})
    check("excel write_range succeeds", written.get("ok"), written)
    read = excel_com.execute("read_range", {"sheet": "Sheet1", "range": "A2"})
    check("excel read_range sees copy value", read.get("values") == [["copy-write"]], read)
    saved = excel_com.execute("save", {})
    check("excel save succeeds", saved.get("ok"), saved)
    closed = excel_com.execute("close", {})
    check("excel close succeeds", closed.get("ok"), closed)
    check("excel copy exists", copy_path.exists(), copy_path)
    check("excel original hash unchanged", _sha256(source) == original_hash)

    md = tmp_root / "memo.md"
    md.write_text("# 변환 테스트\n\n## 개요\n- 첫 항목\n- 둘째 항목\n본문입니다.\n", encoding="utf-8")
    docx = office_convert.execute("md_to_docx", {"path": str(md)})
    check("md_to_docx succeeds", docx.get("ok"), docx)
    spec = tmp_root / "slides.json"
    spec.write_text(json.dumps({
        "slides": [
            {"title": "첫 슬라이드", "points": ["요점 1", "요점 2"]},
            {"title": "둘째 슬라이드", "points": ["마무리"]},
        ]
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    pptx = office_convert.execute("spec_to_pptx", {"spec_path": str(spec)})
    check("spec_to_pptx succeeds", pptx.get("ok"), pptx)
    _open_generated_files(Path(docx["path"]), Path(pptx["path"]))

    check("office available remains false", ADAPTERS["office"]["available"] is False)
    check("office home smoke wording keeps 2016 pending",
          "Office 2016 검증은 app validation pending" in ADAPTERS["office"].get("home_smoke", ""))

    after = {image: _wait_count(image, count) for image, count in before.items()}
    check("Excel process count restored", after["EXCEL.EXE"] == before["EXCEL.EXE"], (before, after))
    check("Word process count restored", after["WINWORD.EXE"] == before["WINWORD.EXE"], (before, after))
    check("PowerPoint process count restored", after["POWERPNT.EXE"] == before["POWERPNT.EXE"], (before, after))

    print(f"\nALL {PASS} CHECKS PASSED (office live smoke)")


if __name__ == "__main__":
    main()
