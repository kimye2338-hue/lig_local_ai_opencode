# -*- coding: utf-8 -*-
"""Office 파일 생성 검증 (오프라인, Office 설치 불필요). 라이브러리 있으면 실제 생성,
없으면 우아한 반입 안내를 검증한다."""
from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

from agent_ops import office_writer as ow  # noqa: E402

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
    d = Path(tempfile.mkdtemp())

    # xlsx
    r = ow.write_xlsx(d / "실적.xlsx", ["부서", "매출"], [["영업", 120], ["개발", 80]])
    if ow.available("xlsx"):
        check("xlsx 실제 생성 + 유효 OOXML", r["ok"] and zipfile.is_zipfile(r["path"]), str(r))
    else:
        check("xlsx 미반입 우아한 안내", not r["ok"] and "openpyxl" in r.get("hint", ""), str(r))

    # docx
    r2 = ow.write_docx(d / "보고서.docx", "3분기 보고서",
                       [{"heading": "개요", "paragraphs": ["요약"], "bullets": ["항목"],
                         "table": {"headers": ["항목", "값"], "rows": [["매출", "200"]]}}])
    if ow.available("docx"):
        check("docx 실제 생성 + 유효 OOXML", r2["ok"] and zipfile.is_zipfile(r2["path"]), str(r2))
    else:
        check("docx 미반입 우아한 안내", not r2["ok"] and "python-docx" in r2.get("hint", ""), str(r2))

    # pptx
    r3 = ow.write_pptx(d / "발표.pptx",
                       [{"title": "매출 12% 증가", "points": ["영업 호조", "개발 미달"]}],
                       title="3분기 실적")
    if ow.available("pptx"):
        check("pptx 실제 생성 + 유효 OOXML", r3["ok"] and zipfile.is_zipfile(r3["path"]), str(r3))
    else:
        check("pptx 미반입 우아한 안내", not r3["ok"] and "python-pptx" in r3.get("hint", ""), str(r3))

    # status는 항상 세 포맷 bool
    st = ow.status()
    check("status 세 포맷 보고", set(st.keys()) == {"docx", "pptx", "xlsx"}, str(st))

    print(f"\nALL {PASS} CHECKS PASSED (office writer)")


if __name__ == "__main__":
    main()
