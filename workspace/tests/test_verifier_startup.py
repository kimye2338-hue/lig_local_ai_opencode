# -*- coding: utf-8 -*-
"""Startup verifier tests.

Run: py -3.11 tests\test_verifier_startup.py
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

WS_TEMPLATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS_TEMPLATE))

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
    tmp = Path(tempfile.mkdtemp(prefix="verifier_startup_"))
    memory = tmp / "global_memory"
    memory.mkdir()
    (memory / "memory.jsonl").write_text("", encoding="utf-8")

    old_memory = os.environ.get("AGENTOPS_MEMORY_DIR")
    os.environ["AGENTOPS_MEMORY_DIR"] = str(memory)
    try:
        import agent_ops.core as core
        import agent_ops.memory_manager as memory_manager
        import agent_ops.verifier as verifier

        importlib.reload(core)
        importlib.reload(memory_manager)
        importlib.reload(verifier)
        report = verifier.verify()
        missing = "\n".join(report.get("missing", []))
        check("verifier accepts configured global memory",
              "memory.jsonl" not in missing, str(report.get("missing")))
    finally:
        if old_memory is None:
            os.environ.pop("AGENTOPS_MEMORY_DIR", None)
        else:
            os.environ["AGENTOPS_MEMORY_DIR"] = old_memory

    fresh = Path(tempfile.mkdtemp(prefix="verifier_fresh_memory_")) / "memory"
    old_memory = os.environ.get("AGENTOPS_MEMORY_DIR")
    os.environ["AGENTOPS_MEMORY_DIR"] = str(fresh)
    try:
        import agent_ops.core as core
        import agent_ops.memory_manager as memory_manager
        import agent_ops.verifier as verifier

        importlib.reload(core)
        importlib.reload(memory_manager)
        importlib.reload(verifier)
        report = verifier.verify()
        missing = "\n".join(report.get("missing", []))
        check("verifier initializes missing memory ledger",
              (fresh / "memory.jsonl").exists() and "memory.jsonl" not in missing,
              str(report.get("missing")))
    finally:
        if old_memory is None:
            os.environ.pop("AGENTOPS_MEMORY_DIR", None)
        else:
            os.environ["AGENTOPS_MEMORY_DIR"] = old_memory

    print(f"\nALL {PASS} CHECKS PASSED (verifier startup)")


if __name__ == "__main__":
    main()
