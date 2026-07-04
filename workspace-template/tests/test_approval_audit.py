# -*- coding: utf-8 -*-
"""Tests for approval gate and append-only audit logging.

Run: py -3.11 tests\test_approval_audit.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_ops import tool_dispatch  # noqa: E402
from agent_ops.approval import classify_risk, request_approval  # noqa: E402
from agent_ops.audit import record  # noqa: E402
from agent_ops.tool_dispatch import ToolDispatcher  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def read_jsonl(path: Path) -> list:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="agentops_approval_"))
    ws = tmp / "작업공간"
    ws.mkdir()
    (ws / "existing.txt").write_text("old", encoding="utf-8")
    outside = tmp / "outside.txt"

    # --- risk table: safe ---
    check("read inside safe", classify_risk("read_file", "existing.txt", ws) == "safe")
    check("new write inside safe", classify_risk("write_file", "new.txt", ws) == "safe")

    # --- risk table: caution ---
    check("overwrite inside caution", classify_risk("write_file", "existing.txt", ws) == "caution")
    check("replace inside caution", classify_risk("replace_in_file", "existing.txt", ws) == "caution")

    # --- risk table: dangerous ---
    check("outside write dangerous", classify_risk("write_file", str(outside), ws) == "dangerous")
    check("adapter execution dangerous", classify_risk("adapter_execute", "browser", ws) == "dangerous")
    check("schedule update dangerous", classify_risk("schedule.update", "today", ws) == "dangerous")

    # --- approval paths ---
    safe = request_approval([{"risk": "safe", "action_kind": "read_file", "target": "existing.txt"}], assume_yes=False)
    check("safe approval auto", safe["approved"] and safe["mode"] == "auto", str(safe))
    auto = request_approval([{"risk": "dangerous", "action_kind": "delete_file", "target": "x.txt"}], assume_yes=True)
    check("dangerous assume_yes auto", auto["approved"] and auto["mode"] == "auto", str(auto))
    denied = request_approval([{"risk": "dangerous", "action_kind": "delete_file", "target": "x.txt"}], input_fn=lambda _prompt: "n")
    check("dangerous denied without y", not denied["approved"] and denied["mode"] == "denied", str(denied))
    approved = request_approval([{"risk": "dangerous", "action_kind": "delete_file", "target": "x.txt"}], input_fn=lambda _prompt: "y")
    check("dangerous y approves", approved["approved"] and approved["mode"] == "interactive", str(approved))

    # --- audit jsonl append + redaction + basename ---
    audit_dir = tmp / "audit"
    os.environ["LIG_AUDIT_DIR"] = str(audit_dir)
    record({
        "run_id": "run-1",
        "kind": "tool",
        "name": "write_file",
        "target": str(ws / "secrets" / "full-path.txt"),
        "risk": "caution",
        "verdict": "approved",
        "detail": "ok",
    })
    record({
        "run_id": "run-2",
        "kind": "tool",
        "name": "write_file",
        "target": str(ws / "key.txt"),
        "risk": "dangerous",
        "verdict": "denied",
        "detail": "sk-test-secret-token-should-not-appear",
    })
    rows = read_jsonl(audit_dir / "audit.jsonl")
    text = (audit_dir / "audit.jsonl").read_text(encoding="utf-8")
    check("audit appends two rows", len(rows) == 2, text)
    check("audit target basename only", rows[0]["target"] == "full-path.txt" and str(ws) not in text, text)
    check("audit redacts secret detail", "sk-test" not in text and rows[1]["detail"] == "[REDACTED]", text)
    check("audit detail capped", len(rows[0]["detail"]) <= 80 and len(rows[1]["detail"]) <= 80, str(rows))

    # --- audit rotation keeps recording after backup ---
    rotate_audit = tmp / "rotate_audit"
    os.environ["LIG_AUDIT_DIR"] = str(rotate_audit)
    old_max = os.environ.get("LIG_AUDIT_MAX_BYTES")
    os.environ["LIG_AUDIT_MAX_BYTES"] = "200"
    try:
        for i in range(8):
            record({
                "run_id": f"rot-{i}",
                "kind": "tool",
                "name": "write_file",
                "target": f"rot-{i}.txt",
                "risk": "safe",
                "verdict": "approved",
                "detail": "rotation-check-" + ("x" * 60),
            })
    finally:
        if old_max is None:
            os.environ.pop("LIG_AUDIT_MAX_BYTES", None)
        else:
            os.environ["LIG_AUDIT_MAX_BYTES"] = old_max
    rotated = list(rotate_audit.glob("audit_*.jsonl.bak"))
    current_rows = read_jsonl(rotate_audit / "audit.jsonl")
    check("audit rotation creates bak file", bool(rotated), str(list(rotate_audit.iterdir())))
    check("audit keeps recording after rotation", bool(current_rows) and current_rows[-1]["run_id"] == "rot-7",
          str(current_rows))

    # --- dispatch hook records audit ---
    dispatch_audit = tmp / "dispatch_audit"
    os.environ["LIG_AUDIT_DIR"] = str(dispatch_audit)
    d = ToolDispatcher(ws, diag_dir=tmp / "diag")
    result = d.dispatch({"name": "write_file", "arguments": {"path": "hook.txt", "content": "hello"}})
    rows = read_jsonl(dispatch_audit / "audit.jsonl")
    check("dispatch succeeds with audit hook", result["ok"] and rows[-1]["name"] == "write_file", str(rows[-1]))
    check("dispatch audit secret-free basename", rows[-1]["target"] == "hook.txt" and str(ws) not in json.dumps(rows[-1], ensure_ascii=False), str(rows[-1]))

    # --- audit hook failure never breaks dispatch ---
    original = tool_dispatch.audit_record

    def broken_record(_event: dict) -> None:
        raise RuntimeError("audit unavailable")

    tool_dispatch.audit_record = broken_record
    try:
        result = d.dispatch({"name": "read_file", "arguments": {"path": "hook.txt"}})
        check("audit failure does not break dispatch", result["ok"], str(result))
    finally:
        tool_dispatch.audit_record = original

    print(f"\nALL {PASS} CHECKS PASSED (approval + audit)")


if __name__ == "__main__":
    main()
