# -*- coding: utf-8 -*-
"""Office adapter tests for absence-safe Excel COM integration.

Run: py -3.11 tests\\test_office_adapters.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

tmp_root = Path(tempfile.mkdtemp(prefix="office_adapter_test_"))
os.environ["AGENTOPS_ROOT"] = str(tmp_root)
os.environ["LIG_AUDIT_DIR"] = str(tmp_root / "audit")

WS_TEMPLATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS_TEMPLATE))

from agent_ops.adapters import ADAPTERS  # noqa: E402
from agent_ops.adapters import excel_com  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def main() -> None:
    office = ADAPTERS["office"]
    check("office adapter remains unavailable", office["available"] is False)
    check("office adapter exposes execute", office.get("execute") is excel_com.execute)
    check("excel actions fixed", set(excel_com.ACTIONS) == {
        "open_copy", "read_range", "write_range", "run_macro_file", "save", "close"})
    check("no original-open API exposed", "open" not in excel_com.ACTIONS and "open_original" not in excel_com.ACTIONS)

    bad = excel_com.execute("no_such_action", {})
    check("unknown action returns ok false", bad["ok"] is False and "unknown action" in bad["error"], str(bad))
    check("unknown action lists available actions", "open_copy" in bad.get("available_actions", []), str(bad))

    if excel_com._PYWIN32_ERROR:
        for action in ("open_copy", "read_range", "write_range", "run_macro_file", "save"):
            result = excel_com.execute(action, {"path": "missing.xlsx", "bas_path": "missing.bas"})
            check(f"{action} absence path explains pywin32", result["ok"] is False
                  and "pywin32 미설치" in result.get("error", ""), str(result))
    else:
        missing = excel_com.execute("read_range", {"sheet": "Sheet1", "range": "A1"})
        check("read before open asks open_copy first", missing["ok"] is False and "open_copy 먼저" in missing["error"],
              str(missing))
        result = excel_com.execute("open_copy", {"path": str(tmp_root / "missing.xlsx")})
        check("open_copy missing workbook fails cleanly", result["ok"] is False and "원본 파일 없음" in result["error"], str(result))

    bas = tmp_root / "macro.bas"
    bas.write_text("Sub Smoke()\nRange(\"A1\").Value = 42\nEnd Sub\n", encoding="utf-8")

    class BrokenComponents:
        def Add(self, _kind):
            raise RuntimeError("VBProject blocked")

    class BrokenProject:
        VBComponents = BrokenComponents()

    class FakeWorkbook:
        VBProject = BrokenProject()

    class FakeExcel:
        def Run(self, _name):
            raise AssertionError("Run should not be reached when VBProject is blocked")

    original_error = excel_com._PYWIN32_ERROR
    original_pythoncom = excel_com.pythoncom
    original_win32com = excel_com.win32com

    class FakePythoncom:
        def CoUninitialize(self):
            return None

    try:
        excel_com._PYWIN32_ERROR = ""
        excel_com.pythoncom = FakePythoncom()
        excel_com.win32com = object()
        excel_com._SESSION.clear()
        excel_com._SESSION.update({"wb": FakeWorkbook(), "xl": FakeExcel(), "copy_path": str(tmp_root / "copy.xlsx")})
        fallback = excel_com.execute("run_macro_file", {"bas_path": str(bas)})
        check("VBProject block downgrades to manual_import",
              fallback["ok"] is False and fallback.get("fallback") == "manual_import", str(fallback))
        check("manual import guide names Alt+F11", "Alt+F11" in fallback.get("guide", ""), str(fallback))
        excel_com.execute("close", {})
    finally:
        excel_com._PYWIN32_ERROR = original_error
        excel_com.pythoncom = original_pythoncom
        excel_com.win32com = original_win32com

    audit_file = tmp_root / "audit" / "audit.jsonl"
    check("excel adapter writes audit", audit_file.exists() and "excel_com" in audit_file.read_text(encoding="utf-8"),
          str(audit_file))

    if excel_com._PYWIN32_ERROR:
        print(f"\nSKIP Excel COM live checks - skipped, not failed; ALL {PASS} STATIC CHECKS PASSED (office adapters)")
        return
    print(f"\nALL {PASS} CHECKS PASSED (office adapters)")


if __name__ == "__main__":
    main()
