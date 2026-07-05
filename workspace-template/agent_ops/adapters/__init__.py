# -*- coding: utf-8 -*-
"""App adapters: where real app execution plugs in later.

Artifact *generation* (artifact_generators.py) is separated from app
*execution* on purpose: scaffolds are produced and validated locally today,
while running them inside SolidWorks/Office/Chrome/HWP is added here later
as independent adapters — without touching generators or the planner.

Each adapter declares what it automates, what it needs (dependency / app
install / company network), and its validation status. Adapters stay
"app validation pending" (or company validation pending) until proven on
a machine that has the app; proven adapters carry a `validated` note.

Adding a real adapter later:
  1) implement an `execute(...)` in its module. Calling conventions differ by
     family — action-based `execute(action, options)` for COM/browser adapters
     (excel_com/office_convert/outlook_com/hwp_com/solidworks_com/browser_cdp),
     path-based `execute(script_path, options)` for matlab_batch/fluent_batch,
     and `execute(dwg_path, scr_path, options)` for autocad_batch. Generic
     invocation goes through `plan_execution()` below, which wraps each family.
  2) flip `available` to True only after an actual run on the target app
  3) record any new dependency in release/dependencies.json first
"""
from __future__ import annotations

from typing import Any, Dict

from . import (autocad_batch, browser_cdp, excel_com, fluent_batch, hwp_com,
               matlab_batch, office_convert, outlook_com, solidworks_com)


def _office_execute(action: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch Office actions while keeping Excel copy policy unchanged."""
    if str(action or "") in office_convert.ACTIONS:
        return office_convert.execute(action, options)
    return excel_com.execute(action, options)

# adapter id -> spec. Keys mirror the capability registry vocabulary so
# doctor/plan can report generation and execution status side by side.
ADAPTERS: Dict[str, Dict[str, Any]] = {
    "solidworks": {
        "description": "SolidWorks 매크로 실행/COM 제어 (파트/어셈블리/도면)",
        "consumes": ["vba_macro"],
        "available": False,
        "requires": ["SolidWorks 설치", "pywin32 (COM 채택 시 — dependencies.json 'pywin32')"],
        "home_smoke": "회사 SolidWorks COM connect OK (2026-07-05 company_check) — 매크로 실행 검증은 파일럿 대기",
        "pending": "app validation pending: 회사 SolidWorks에서 run_macro 실행 검증(연결만 확인됨)",
        "execute": solidworks_com.execute,
    },
    "office": {
        "description": "Excel/Word/PowerPoint 매크로 실행/COM 제어 및 변환",
        "consumes": ["vba_macro", "slide_outline", "document"],
        "available": True,
        "requires": ["MS Office 설치", "pywin32 또는 python-pptx/openpyxl (dependencies.json 'office-doc-wheels')"],
        "validated": "회사 Excel 16.0 VBProject 매크로 주입+실행 A1=42 (2026-07-05 company_check)",
        "home_smoke": "passed 2026-07-04 (Excel 최신) + 회사 Excel 16.0 실행 확인 2026-07-05",
        "pending": "Word/PowerPoint 변환(md_to_docx/spec_to_pptx)은 app validation pending",
        "execute": _office_execute,
    },
    "outlook": {
        "description": "Outlook 2016 일정/받은편지함 읽기 및 schedule 동기화",
        "consumes": ["mail_report"],
        "available": True,
        "requires": ["Outlook 실행 중 세션", "pywin32 (COM)", "회사 Outlook 프로필"],
        "validated": "회사 Outlook 16.0 받은편지함/일정 read 성공 (2026-07-05 company_check)",
        "pending": "sync_calendar 쓰기 경로는 파일럿에서 확인",
        "execute": outlook_com.execute,
    },
    "browser": {
        "description": "Chrome 실제 제어 (CDP/selenium/playwright)",
        "consumes": ["browser_script"],
        "available": True,
        "requires": ["Chrome", "CDP는 추가 설치 불필요; selenium/playwright는 dependencies.json 'browser-automation-wheels'"],
        "validated": "local Chrome CDP, 2026-07-03",
        "pending": "사내 시스템 로그인은 company validation pending",
        "execute": browser_cdp.execute,
    },
    "matlab": {
        "description": "MATLAB 2024a -batch 스크립트 실행",
        "consumes": ["matlab_script"],
        "available": True,
        "requires": ["MATLAB 2024a 설치", "MATLAB_EXE 또는 PATH의 matlab"],
        "validated": "회사 MATLAB R2024a -batch 실행 성공 (mean=12.50 max=13.90, 2026-07-05 company_check)",
        "pending": "",
        "execute": matlab_batch.execute,
    },
    "autocad": {
        "description": "AutoCAD 2019 accoreconsole 배치 실행",
        "consumes": ["autocad_script"],
        "available": True,
        "requires": ["AutoCAD 2019 accoreconsole.exe", "ACCORECONSOLE_EXE 또는 표준 설치 경로"],
        "validated": "회사 AutoCAD 2019 accoreconsole /i 시드 + /s scr 실행·저장 성공 (2026-07-05)",
        "pending": "",
        "execute": autocad_batch.execute,
    },
    "fluent": {
        "description": "ANSYS Fluent 2024R1 journal 배치 실행",
        "consumes": ["fluent_journal"],
        "available": False,
        "requires": ["ANSYS Fluent 2024R1 설치", "FLUENT_EXE 또는 ANSYS Inc 표준 설치 경로"],
        "pending": "app validation pending: 회사 ANSYS Fluent 2024R1에서 fluent 3ddp -g -i journal 검증",
        "execute": fluent_batch.execute,
    },
    "hwp": {
        "description": "한글(HWP) 문서 자동화",
        "consumes": ["document"],
        "available": True,
        "requires": ["한글 설치", "pywin32 (HwpFrame COM)"],
        "validated": "회사 한글 10.0 문서 생성+저장 성공 (2026-07-05 company_check)",
        "pending": "",
        "execute": hwp_com.execute,
    },
}


def adapter_summary() -> Dict[str, Any]:
    """Secret-free execution-side inventory for doctor/diagnostics."""
    return {
        adapter_id: {
            "description": spec["description"],
            "consumes": spec["consumes"],
            "available": spec["available"],
            "validated": spec.get("validated", ""),
            "home_smoke": spec.get("home_smoke", ""),
            "pending": spec["pending"],
        }
        for adapter_id, spec in ADAPTERS.items()
    }


# --- artifact-kind -> adapter execution dispatch (work --execute) -----------
# Only mappings proven safe are auto-run; everything else returns ready=False
# with an honest reason + manual command. Prerequisites (e.g. an input .dwg /
# .xlsx) must come from the user's --input paths — never guessed.

def _first_with_suffix(paths, *suffixes):
    for p in paths:
        if str(p).lower().endswith(suffixes):
            return str(p)
    return ""


def _first_named(paths, *names):
    for p in paths:
        from pathlib import Path as _P
        if _P(str(p)).name in names:
            return str(p)
    return ""


def executable_kinds(artifact_kinds, input_paths=()):
    """Which of these kinds would auto-execute under --execute (for approval risk)."""
    return [e["kind"] for e in plan_execution(artifact_kinds, [], input_paths, probe_only=True)
            if e["ready"]]


def plan_execution(artifact_kinds, files, input_paths=(), probe_only=False):
    """Build the safe auto-execution plan for generated artifacts.

    Returns a list of {kind, adapter, file, ready, reason, invoke}. `invoke` is a
    zero-arg callable running the adapter (None when not ready). With
    probe_only=True, file existence is not required (pre-generation risk probe).
    """
    files = [str(f) for f in (files or [])]
    inputs = [str(p) for p in (input_paths or [])]
    in_dwg = _first_with_suffix(inputs, ".dwg")
    in_xlsx = _first_with_suffix(inputs, ".xlsx", ".xlsm")
    entries = []

    def add(kind, adapter, file, ready, reason, invoke=None):
        entries.append({"kind": kind, "adapter": adapter, "file": file,
                        "ready": bool(ready), "reason": reason,
                        "invoke": invoke if ready else None})

    for kind in artifact_kinds or []:
        if kind == "matlab_script":
            m = _first_with_suffix(files, ".m") or ("<작업.m>" if probe_only else "")
            if not ADAPTERS["matlab"]["available"]:
                add(kind, "matlab", m, False, ADAPTERS["matlab"].get("pending") or "unavailable")
            elif m:
                add(kind, "matlab", m, True, "matlab -batch 실행",
                    (lambda p=m: matlab_batch.execute(p, {})))
            else:
                add(kind, "matlab", "", False, ".m 산출물이 없어 실행 생략")
        elif kind == "autocad_script":
            scr = _first_with_suffix(files, ".scr") or ("<작업.scr>" if probe_only else "")
            if not ADAPTERS["autocad"]["available"]:
                add(kind, "autocad", scr, False, ADAPTERS["autocad"].get("pending") or "unavailable")
            elif not in_dwg:
                add(kind, "autocad", scr, False,
                    "입력 도면(.dwg)이 없어 실행 생략 — --input <도면.dwg> 지정 시 사본에서 자동 실행")
            elif scr:
                add(kind, "autocad", scr, True, f"accoreconsole /i {in_dwg} 사본 + /s 실행",
                    (lambda d=in_dwg, s=scr: autocad_batch.execute(d, s, {})))
            else:
                add(kind, "autocad", "", False, ".scr 산출물이 없어 실행 생략")
        elif kind in ("document", "meeting_minutes"):
            md = (_first_named(files, "문서.md", "회의록.md")
                  or _first_with_suffix(files, ".md")
                  or ("<문서.md>" if probe_only else ""))
            if not ADAPTERS["hwp"]["available"]:
                add(kind, "hwp", md, False, ADAPTERS["hwp"].get("pending") or "unavailable")
            elif md:
                from pathlib import Path as _P
                out = str(_P(md).with_suffix(".hwp"))
                add(kind, "hwp", md, True, f"HWP 변환(md_to_hwp) -> {_P(out).name}",
                    (lambda p=md, o=out: hwp_com.execute("md_to_hwp", {"path": p, "out_path": o})))
            else:
                add(kind, "hwp", "", False, ".md 산출물이 없어 변환 생략")
        elif kind == "vba_macro":
            bas = _first_with_suffix(files, ".bas") or ("<macro.bas>" if probe_only else "")
            if not ADAPTERS["office"]["available"]:
                add(kind, "office", bas, False, ADAPTERS["office"].get("pending") or "unavailable")
            elif not in_xlsx:
                add(kind, "office", bas, False,
                    "대상 엑셀(.xlsx)이 없어 실행 생략 — --input <파일.xlsx> 지정 시 사본에서 매크로 자동 실행. "
                    "수동: Excel에서 Alt+F11 -> .bas 가져오기 -> 실행")
            elif bas:
                def _run_excel(x=in_xlsx, b=bas):
                    opened = excel_com.execute("open_copy", {"path": x})
                    if not opened.get("ok"):
                        return opened
                    ran = excel_com.execute("run_macro_file", {"bas_path": b})
                    saved = excel_com.execute("save", {}) if ran.get("ok") else {"ok": False}
                    excel_com.execute("close", {})
                    if not ran.get("ok"):
                        return ran
                    ran["copy_path"] = opened.get("copy_path", "")
                    ran["saved"] = bool(saved.get("ok"))
                    return ran
                add(kind, "office", bas, True, f"Excel 사본({in_xlsx})에 매크로 주입+실행", _run_excel)
            else:
                add(kind, "office", "", False, ".bas 산출물이 없어 실행 생략")
        elif kind == "fluent_journal":
            add(kind, "fluent", _first_with_suffix(files, ".jou"), False,
                ADAPTERS["fluent"].get("pending") or "app validation pending")
        else:
            # slide_outline / browser_script / mail_report / ansys_script 등:
            # 자동 실행 매핑 없음 — 산출물 자체가 결과물이거나 별도 세션이 필요.
            add(kind, "-", "", False, "자동 실행 매핑 없음 (산출물 확인/수동 사용)")
    return entries
