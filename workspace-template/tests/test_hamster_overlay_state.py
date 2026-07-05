# -*- coding: utf-8 -*-
"""Pure state parser tests for hamster_overlay.py (no GUI required)."""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_ops.ui.hamster_overlay import load_snapshot, read_recent_events  # noqa: E402

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
    root = Path(tempfile.mkdtemp(prefix="hamster_state_"))
    state = root / "state"
    diag = root / "diag"
    state.mkdir()
    diag.mkdir()

    snap = load_snapshot(state, diag)
    check("empty state is idle", snap.status == "idle", str(snap))

    (diag / "tool-dispatch-last.json").write_text(json.dumps({
        "timestamp": "2026-07-05T18:00:00",
        "tool": "read_file",
        "ok": True,
    }, ensure_ascii=False), encoding="utf-8")
    snap = load_snapshot(state, diag)
    check("tool success maps to working", snap.status == "working" and snap.task == "read_file", str(snap))

    (diag / "tool-dispatch-last.json").write_text(json.dumps({
        "timestamp": "2026-07-05T18:01:00",
        "tool": "click",
        "ok": False,
        "root_cause_category": "browser_unavailable",
        "error": "Chrome CDP 연결 실패",
    }, ensure_ascii=False), encoding="utf-8")
    snap = load_snapshot(state, diag)
    check("browser_unavailable maps to error", snap.status == "error" and "Chrome" in snap.message, str(snap))

    time.sleep(0.02)
    (state / "current_status.json").write_text(json.dumps({
        "status": "needs_user",
        "task": "GitHub PR",
        "message": "승인이 필요합니다.",
        "last_update": "2026-07-05T18:02:00+09:00",
    }, ensure_ascii=False), encoding="utf-8")
    snap = load_snapshot(state, diag)
    check("explicit current_status wins when newest", snap.status == "needs_user" and snap.task == "GitHub PR", str(snap))

    with (diag / "tool-dispatch-history.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": "t1", "tool": "read_file", "ok": True}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"timestamp": "t2", "tool": "click", "ok": False, "error": "실패"}, ensure_ascii=False) + "\n")
    events = read_recent_events(state, diag, limit=5)
    check("recent events read from history", len(events) == 2 and "click" in events[-1], str(events))

    print(f"\nALL {PASS} CHECKS PASSED (hamster overlay state)")


if __name__ == "__main__":
    main()
