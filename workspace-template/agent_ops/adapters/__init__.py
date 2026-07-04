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
  1) implement `execute(artifact_path, options) -> dict` in its module
  2) flip `available` to True only after an actual run on the target app
  3) record any new dependency in release/dependencies.json first
"""
from __future__ import annotations

from typing import Any, Dict

from . import autocad_batch, browser_cdp, excel_com, matlab_batch, office_convert, outlook_com


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
        "pending": "app validation pending: SolidWorks가 있는 PC에서 매크로 실행 검증",
    },
    "office": {
        "description": "Excel/Word/PowerPoint 매크로 실행/COM 제어 및 변환",
        "consumes": ["vba_macro", "slide_outline", "document"],
        "available": False,
        "requires": ["MS Office 설치", "pywin32 또는 python-pptx/openpyxl (dependencies.json 'office-doc-wheels')"],
        "pending": "app validation pending: Office가 있는 PC에서 매크로/변환 실행 검증",
        "home_smoke": "passed 2026-07-04 (Excel 최신) — Office 2016 검증은 app validation pending",
        "execute": _office_execute,
    },
    "outlook": {
        "description": "Outlook 2016 일정/받은편지함 읽기 및 schedule 동기화",
        "consumes": ["mail_report"],
        "available": False,
        "requires": ["Outlook 실행 중 세션", "pywin32 (COM)", "회사 Outlook 프로필"],
        "pending": "company validation pending: Outlook 2016 실행 세션에서 일정/메일 read 검증",
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
        "available": False,
        "requires": ["MATLAB 2024a 설치", "MATLAB_EXE 또는 PATH의 matlab"],
        "pending": "app validation pending: 회사 MATLAB 2024a에서 -batch 실행 검증",
        "execute": matlab_batch.execute,
    },
    "autocad": {
        "description": "AutoCAD 2019 accoreconsole 배치 실행",
        "consumes": ["autocad_script"],
        "available": False,
        "requires": ["AutoCAD 2019 accoreconsole.exe", "ACCORECONSOLE_EXE 또는 표준 설치 경로"],
        "pending": "app validation pending: 회사 AutoCAD 2019 accoreconsole에서 /i 사본 dwg + /s scr 검증",
        "execute": autocad_batch.execute,
    },
    "hwp": {
        "description": "한글(HWP) 문서 자동화",
        "consumes": ["document"],
        "available": False,
        "requires": ["한글 설치", "pywin32 (HwpFrame COM)"],
        "pending": "app validation pending: 한글이 있는 PC에서 검증",
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
