# -*- coding: utf-8 -*-
"""Input ingestion regressions for model-grounding parsers."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def main() -> None:
    from agent_ops import input_ingest as ing

    tmp = Path(tempfile.mkdtemp(prefix="input_ingest_"))
    csv = tmp / "시험결과.csv"
    csv.write_text("항목,값,판정\n치수A,10,합격\n치수B,99,불합격\n", encoding="utf-8")
    secret = tmp / "secret.txt"
    secret.write_text("api_key=SECRET_VALUE_123\n일반 줄\n", encoding="utf-8")
    mail_json = tmp / "mail.json"
    mail_json.write_text(json.dumps([
        {"from": "a@example", "subject": "회의", "body": "자료 요청"}
    ], ensure_ascii=False), encoding="utf-8")
    binary = tmp / "model.bin"
    binary.write_bytes(b"\x00\x01\x02")

    result = ing.ingest_inputs([csv, secret, mail_json, binary])
    blob = json.dumps(result, ensure_ascii=False)
    check("csv facts and notable rows", "CSV 2행" in blob and "불합격" in blob, blob)
    check("secret-like lines are masked", "SECRET_VALUE_123" not in blob and "[masked: secret-like line]" in blob)
    check("mail json parsed", result["mails"] and result["mails"][0]["subject"] == "회의", str(result["mails"]))
    check("binary file unsupported, not silent", any(x["name"] == "model.bin" for x in result["unsupported"]), str(result))

    # If openpyxl is absent but markitdown can convert XLSX, the ingest path
    # should still use that parser instead of reporting XLSX as unsupported.
    xlsx = tmp / "표.xlsx"
    xlsx.write_bytes(b"fake xlsx bytes")
    old_openpyxl = ing.openpyxl
    old_can = ing.doc_convert.can_convert
    old_convert = ing.doc_convert.convert_file
    try:
        ing.openpyxl = None
        ing.doc_convert.can_convert = lambda suffix: suffix == ".xlsx"  # type: ignore[assignment]
        ing.doc_convert.convert_file = lambda path: {  # type: ignore[assignment]
            "ok": True,
            "suffix": ".xlsx",
            "engine": "markitdown",
            "markdown": "컬럼A | 컬럼B\n값1 | 값2",
            "chars": 18,
        }
        fallback = ing.ingest_inputs([xlsx])
    finally:
        ing.openpyxl = old_openpyxl
        ing.doc_convert.can_convert = old_can  # type: ignore[assignment]
        ing.doc_convert.convert_file = old_convert  # type: ignore[assignment]
    check("xlsx falls back to markitdown when openpyxl missing",
          fallback["ok"] and fallback["files"][0]["type"] == "doc:xlsx"
          and "markitdown" in json.dumps(fallback, ensure_ascii=False), str(fallback))

    print("\nALL CHECKS PASSED (input ingest)")


if __name__ == "__main__":
    main()
