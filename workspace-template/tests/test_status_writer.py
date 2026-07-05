# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
    tmp = Path(tempfile.mkdtemp(prefix="status_writer_"))
    os.environ["LIG_STATE_DIR"] = str(tmp)
    from agent_ops.status_writer import publish_event, publish_status  # noqa: E402

    payload = publish_status("working", message="테스트 중", task="unit", progress=42, run_id="r1")
    check("publish_status returns payload", payload["status"] == "working" and payload["progress"] == 42, str(payload))
    current = json.loads((tmp / "current_status.json").read_text(encoding="utf-8"))
    check("current_status written", current["task"] == "unit" and current["run_id"] == "r1", str(current))

    event = publish_event("TASK_DONE", message="완료", status="done", task="unit", run_id="r1")
    check("publish_event returns event", event["kind"] == "TASK_DONE" and event["status"] == "done", str(event))
    lines = (tmp / "events.ndjson").read_text(encoding="utf-8").splitlines()
    check("events.ndjson appended", len(lines) == 1 and "TASK_DONE" in lines[0], str(lines))
    current = json.loads((tmp / "current_status.json").read_text(encoding="utf-8"))
    check("publish_event updates current", current["status"] == "done" and current["message"] == "완료", str(current))

    print(f"\nALL {PASS} CHECKS PASSED (status writer)")


if __name__ == "__main__":
    main()
