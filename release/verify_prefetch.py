# -*- coding: utf-8 -*-
"""Verify prefetched dependency files against release/dependencies.json.

Run: py -3.11 release\\verify_prefetch.py

For each `prefetch_files` entry whose status starts with "resolved", check that
release/prefetch/<filename> exists and its SHA256 matches. PENDING_HOME_PREFETCH
entries are reported but not failed. If release/prefetch/ is empty (CI / no
downloads yet), print SKIP and exit 0 — this is a manifest integrity tool, not a
download gate.

Exit codes: 0 ok / SKIP, 1 hash mismatch or missing resolved file.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RELEASE = Path(__file__).resolve().parent
MANIFEST = RELEASE / "dependencies.json"
PREFETCH = RELEASE / "prefetch"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = manifest.get("prefetch_files", [])
    resolved = [f for f in files if str(f.get("status", "")).startswith("resolved")]
    pending = [f for f in files if "PENDING" in str(f.get("status", ""))]

    present = list(PREFETCH.glob("*")) if PREFETCH.exists() else []
    if not present:
        print(f"SKIP  release/prefetch/ is empty — manifest lists {len(resolved)} resolved "
              f"+ {len(pending)} pending; nothing to verify here. (skipped, not failed)")
        return 0

    failures = 0
    for entry in resolved:
        target = PREFETCH / str(entry["filename"])
        if not target.exists():
            print(f"MISS  {entry['filename']} — resolved in manifest but not in prefetch/")
            failures += 1
            continue
        actual = _sha256(target)
        if actual != entry["sha256"]:
            print(f"FAIL  {entry['filename']} sha256 mismatch\n      manifest={entry['sha256']}\n      actual  ={actual}")
            failures += 1
        else:
            print(f"OK    {entry['filename']}")
    for entry in pending:
        print(f"PEND  {entry['filename']} — {entry['status']}")

    if failures:
        print(f"\n{failures} verification failure(s).")
        return 1
    print(f"\nAll {len(resolved)} resolved files verified; {len(pending)} pending home prefetch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
