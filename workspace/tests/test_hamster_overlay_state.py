# -*- coding: utf-8 -*-
"""Pure state parser tests for hamster_overlay.py (no GUI required)."""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_ops.ui.hamster_overlay as hamster_overlay  # noqa: E402
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

    # --- 펫 이미지 에셋 (사용자 제공 스티커, 2026-07-05) ---
    import os
    from agent_ops.ui.hamster_overlay import STATUS_LABELS, load_pet_images, pet_asset_dir
    assets = pet_asset_dir()
    for status in STATUS_LABELS:
        p = assets / f"{status}.png"
        check(f"pet asset {status}.png shipped",
              p.is_file() and p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", str(p))

    class FakeTk:
        class PhotoImage:
            def __init__(self, file):
                self.file = file
    imgs = load_pet_images(FakeTk)
    check("loader maps every status to an image", set(imgs) == set(STATUS_LABELS), str(set(imgs)))
    os.environ["LIG_PET_DIR"] = str(root / "no_such_dir")
    check("missing pet dir falls back gracefully", load_pet_images(FakeTk) == {})
    os.environ.pop("LIG_PET_DIR")

    # --- 에이전트 루프가 라이브 상태를 발행 → 펫이 실시간으로 읽는다 ---
    os.environ["LIG_STATE_DIR"] = str(state)
    from agent_ops.tool_dispatch import run_agent_loop

    def transport(url, payload, headers, timeout):
        return {"choices": [{"message": {"content": "끝"}}]}

    run_agent_loop("펫 상태 테스트", root, env={"LIG_GATEWAY_BASE_URL": "http://127.0.0.1:9",
                                               "LIG_API_KEY": "x"},
                   transport=transport, diag_dir=diag)
    current = json.loads((state / "current_status.json").read_text(encoding="utf-8"))
    check("agent loop publishes live status for pet",
          current["status"] == "done" and current["task"].startswith("펫 상태"), str(current))
    snap = load_snapshot(state, diag)
    check("pet snapshot reflects agent completion", snap.status == "done", str(snap))
    os.environ.pop("LIG_STATE_DIR")

    check("overlay geometry restore has regex module available",
          hasattr(hamster_overlay, "re"), "hamster_overlay imports re for _onscreen")

    print(f"\nALL {PASS} CHECKS PASSED (hamster overlay state)")


if __name__ == "__main__":
    main()
