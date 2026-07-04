# -*- coding: utf-8 -*-
"""Office adapter tests for absence-safe COM integrations.

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
os.environ["LIG_SCHEDULE_DIR"] = str(tmp_root / "schedule")

WS_TEMPLATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS_TEMPLATE))

from agent_ops.adapters import ADAPTERS  # noqa: E402
from agent_ops.adapters import excel_com  # noqa: E402
from agent_ops.adapters import hwp_com  # noqa: E402
from agent_ops.adapters import office_convert  # noqa: E402
from agent_ops.adapters import outlook_com  # noqa: E402
from agent_ops.adapters import solidworks_com  # noqa: E402
from agent_ops import schedule_store  # noqa: E402
from agent_ops.artifact_generators import classify_mail  # noqa: E402

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
    check("office adapter exposes execute", callable(office.get("execute")))
    check("office home smoke is honest", "Office 2016 검증은 app validation pending" in office.get("home_smoke", ""))
    check("office consumes document conversion", "document" in office.get("consumes", []), str(office.get("consumes")))
    outlook = ADAPTERS["outlook"]
    check("outlook adapter remains unavailable", outlook["available"] is False)
    check("outlook adapter exposes execute", outlook.get("execute") is outlook_com.execute)
    hwp = ADAPTERS["hwp"]
    check("hwp adapter remains unavailable", hwp["available"] is False)
    check("hwp adapter exposes execute", hwp.get("execute") is hwp_com.execute)
    solidworks = ADAPTERS["solidworks"]
    check("solidworks adapter remains unavailable", solidworks["available"] is False)
    check("solidworks adapter exposes execute", solidworks.get("execute") is solidworks_com.execute)
    check("outlook actions keep send non-public",
          set(outlook_com.ACTIONS) == {"read_calendar", "sync_calendar", "read_inbox"}
          and "send_mail" not in outlook_com.ACTIONS, str(outlook_com.ACTIONS))
    check("excel actions fixed", set(excel_com.ACTIONS) == {
        "open_copy", "read_range", "write_range", "run_macro_file", "save", "close"})
    check("office conversion actions fixed", set(office_convert.ACTIONS) == {"md_to_docx", "spec_to_pptx"})
    check("hwp actions fixed", set(hwp_com.ACTIONS) == {"md_to_hwp"})
    check("solidworks actions fixed", set(solidworks_com.ACTIONS) == {"run_macro"})
    check("no original-open API exposed", "open" not in excel_com.ACTIONS and "open_original" not in excel_com.ACTIONS)
    check("hwp exposes only new-file conversion API", "open" not in hwp_com.ACTIONS and "open_original" not in hwp_com.ACTIONS)

    bad = excel_com.execute("no_such_action", {})
    check("unknown action returns ok false", bad["ok"] is False and "unknown action" in bad["error"], str(bad))
    check("unknown action lists available actions", "open_copy" in bad.get("available_actions", []), str(bad))
    bad_convert = office_convert.execute("no_such_action", {})
    check("office conversion unknown action returns ok false",
          bad_convert["ok"] is False and "md_to_docx" in bad_convert.get("available_actions", []),
          str(bad_convert))
    routed = office["execute"]("md_to_docx", {"path": str(tmp_root / "missing.md")})
    check("office adapter routes conversion action",
          routed["ok"] is False and ("Markdown 파일 없음" in routed.get("error", "")
                                     or "pywin32 미설치" in routed.get("error", "")),
          str(routed))
    bad_outlook = outlook_com.execute("no_such_action", {})
    check("outlook unknown action returns ok false",
          bad_outlook["ok"] is False and "read_calendar" in bad_outlook.get("available_actions", []),
          str(bad_outlook))
    bad_hwp = hwp_com.execute("no_such_action", {})
    check("hwp unknown action returns ok false",
          bad_hwp["ok"] is False and "md_to_hwp" in bad_hwp.get("available_actions", []),
          str(bad_hwp))
    bad_sw = solidworks_com.execute("no_such_action", {})
    check("solidworks unknown action returns ok false",
          bad_sw["ok"] is False and "run_macro" in bad_sw.get("available_actions", []),
          str(bad_sw))

    if outlook_com._PYWIN32_ERROR:
        # AGENTOPS_ROOT is a data root here; child subprocess must import from code root.
        absent = outlook_com.execute("read_calendar", {"days": 1})
        check("outlook absence path explains pywin32",
              absent["ok"] is False and "pywin32 미설치" in absent.get("error", ""), str(absent))

    if excel_com._PYWIN32_ERROR:
        for action in ("open_copy", "read_range", "write_range", "run_macro_file", "save"):
            result = excel_com.execute(action, {"path": "missing.xlsx", "bas_path": "missing.bas"})
            check(f"{action} absence path explains pywin32", result["ok"] is False
                  and "pywin32 미설치" in result.get("error", ""), str(result))
        for action in office_convert.ACTIONS:
            result = office_convert.execute(action, {"path": "missing.md", "spec_path": "missing.json"})
            check(f"{action} absence path explains pywin32", result["ok"] is False
                  and "pywin32 미설치" in result.get("error", ""), str(result))
        hwp_absent = hwp_com.execute("md_to_hwp", {"path": str(tmp_root / "missing.md"),
                                                  "out_path": str(tmp_root / "out.hwp")})
        check("hwp absence path explains pywin32",
              hwp_absent["ok"] is False and "pywin32 미설치" in hwp_absent.get("error", ""),
              str(hwp_absent))
    else:
        missing = excel_com.execute("read_range", {"sheet": "Sheet1", "range": "A1"})
        check("read before open asks open_copy first", missing["ok"] is False and "open_copy 먼저" in missing["error"],
              str(missing))
        result = excel_com.execute("open_copy", {"path": str(tmp_root / "missing.xlsx")})
        check("open_copy missing workbook fails cleanly", result["ok"] is False and "원본 파일 없음" in result["error"], str(result))
        missing_doc = office_convert.execute("md_to_docx", {"path": str(tmp_root / "missing.md")})
        check("md_to_docx missing source fails cleanly",
              missing_doc["ok"] is False and "Markdown 파일 없음" in missing_doc["error"], str(missing_doc))
        missing_spec = office_convert.execute("spec_to_pptx", {"spec_path": str(tmp_root / "missing.json")})
        check("spec_to_pptx missing source fails cleanly",
              missing_spec["ok"] is False and "slide spec 파일 없음" in missing_spec["error"], str(missing_spec))
        missing_hwp = hwp_com.execute("md_to_hwp", {"path": str(tmp_root / "missing.md"),
                                                   "out_path": str(tmp_root / "out.hwp")})
        check("md_to_hwp missing source fails cleanly",
              missing_hwp["ok"] is False and "Markdown 파일 없음" in missing_hwp["error"], str(missing_hwp))

    sw_doc = tmp_root / "part.SLDPRT"
    sw_doc.write_bytes(b"SOLIDWORKS_ORIGINAL")
    sw_bas = tmp_root / "macro.bas"
    sw_bas.write_text("Sub main()\nEnd Sub\n", encoding="utf-8")
    sw_fallback = solidworks_com.execute("run_macro", {"doc_path": str(sw_doc), "bas_path": str(sw_bas)})
    sw_copy = Path(sw_fallback.get("copy_path", ""))
    check("solidworks bas macro downgrades to manual import",
          sw_fallback["ok"] is False and sw_fallback.get("fallback") == "manual_import"
          and "매크로 편집기" in sw_fallback.get("guide", ""), str(sw_fallback))
    check("solidworks run_macro creates copy and preserves original",
          sw_copy.exists() and sw_copy.name.startswith("사본_") and sw_doc.read_bytes() == b"SOLIDWORKS_ORIGINAL",
          str(sw_fallback))
    sw_swp = tmp_root / "macro.swp"
    sw_swp.write_bytes(b"SWP")
    sw_absent = solidworks_com.execute("run_macro", {"doc_path": str(sw_doc), "bas_path": str(sw_swp)})
    check("solidworks absence path explains pywin32 or app access",
          sw_absent["ok"] is False
          and ("pywin32 미설치" in sw_absent.get("error", "")
               or "SolidWorks 실행/접속 실패" in sw_absent.get("error", "")),
          str(sw_absent))

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
    audit_text = audit_file.read_text(encoding="utf-8") if audit_file.exists() else ""
    check("excel adapter writes audit", "excel_com" in audit_text, str(audit_file))
    check("close action is audited without options", "excel_com.close" in audit_text, audit_text)

    items = [
        {"title": "설계 리뷰", "start": "2026-07-05 10:00", "end": "2026-07-05 11:00"},
        {"title": "설계 리뷰", "start": "2026-07-05 10:00", "end": "2026-07-05 11:00"},
        {"title": "", "start": "2026-07-06 10:00", "end": "2026-07-06 11:00"},
    ]
    synced = outlook_com.sync_to_schedule(items)
    check("outlook sync adds unique schedule item",
          synced["ok"] and len(synced["added"]) == 1 and synced["skipped"] == 2, str(synced))
    stored = schedule_store.list_items("all")
    check("outlook sync marks source outlook",
          len(stored) == 1 and stored[0]["source"] == "outlook", str(stored))
    synced_again = outlook_com.sync_to_schedule(items[:1])
    check("outlook sync skips duplicate title due",
          synced_again["ok"] and not synced_again["added"] and synced_again["skipped"] == 1, str(synced_again))

    original_outlook_error = outlook_com._PYWIN32_ERROR
    original_outlook_pythoncom = outlook_com.pythoncom
    original_outlook_win32com = outlook_com.win32com

    class FakeOutlookPythoncom:
        def CoInitialize(self):
            return None

        def CoUninitialize(self):
            return None

    class FakeClient:
        def GetActiveObject(self, _name):
            raise RuntimeError("Outlook is closed")

    class FakeWin32:
        client = FakeClient()

    try:
        outlook_com._PYWIN32_ERROR = ""
        outlook_com.pythoncom = FakeOutlookPythoncom()
        outlook_com.win32com = FakeWin32()
        missing_outlook = outlook_com._active_outlook()
        check("outlook closed asks user to start Outlook",
              missing_outlook["ok"] is False and "Outlook을 먼저 실행" in missing_outlook.get("error", ""),
              str(missing_outlook))
    finally:
        outlook_com._PYWIN32_ERROR = original_outlook_error
        outlook_com.pythoncom = original_outlook_pythoncom
        outlook_com.win32com = original_outlook_win32com

    inbox_item = {"from": "팀장", "subject": "결재 요청", "body": "금요일까지 승인 부탁드립니다."}
    check("outlook inbox item fits mail classifier",
          classify_mail(inbox_item) == "결재/승인", str(inbox_item))
    send = outlook_com.send_mail("user@example.com", "테스트", "본문")
    check("outlook send_mail fails closed dangerous",
          send["ok"] is False and send.get("risk") == "dangerous" and "기본 비노출" in send.get("error", ""),
          str(send))

    if excel_com._PYWIN32_ERROR:
        print(f"\nSKIP Excel COM live checks - skipped, not failed; ALL {PASS} STATIC CHECKS PASSED (office adapters)")
        return
    print(f"\nALL {PASS} CHECKS PASSED (office adapters)")


if __name__ == "__main__":
    main()
