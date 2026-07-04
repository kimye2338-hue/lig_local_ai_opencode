# -*- coding: utf-8 -*-
"""Schema + integrity checks for release/dependencies.json prefetch manifest.

Run: py -3.11 tests\\test_release_manifest.py

Pure stdlib, no network. File-existence is only checked when release/prefetch/
is populated (otherwise that part SKIPs); hash/schema shape is always checked.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# tests/ -> workspace-template -> repo root -> release/
REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "release" / "dependencies.json"
PREFETCH = REPO_ROOT / "release" / "prefetch"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
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
    check("manifest exists", MANIFEST.exists(), str(MANIFEST))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = manifest.get("prefetch_files", [])
    check("prefetch_files present and non-empty", isinstance(files, list) and bool(files), str(type(files)))

    required_keys = {"name", "filename", "url", "sha256", "size", "license", "purpose", "category", "status"}
    for entry in files:
        missing = required_keys - set(entry)
        check(f"entry has all keys: {entry.get('filename')}", not missing, str(missing))

    resolved = [f for f in files if str(f.get("status", "")).startswith("resolved")]
    pending = [f for f in files if "PENDING" in str(f.get("status", ""))]
    check("has resolved entries", bool(resolved), "0 resolved")

    for entry in resolved:
        check(f"resolved sha256 is 64-hex: {entry['filename']}",
              bool(HEX64.match(str(entry["sha256"]))), str(entry["sha256"]))
        check(f"resolved size is positive int: {entry['filename']}",
              isinstance(entry["size"], int) and entry["size"] > 0, str(entry["size"]))
        check(f"resolved url is https: {entry['filename']}",
              str(entry["url"]).startswith("https://"), str(entry["url"]))

    for entry in pending:
        check(f"pending entry carries a reason: {entry['filename']}",
              "PENDING" in str(entry["sha256"]) and len(str(entry["status"])) > 20, str(entry))

    # no secrets/hosts in the manifest
    blob = json.dumps(manifest, ensure_ascii=False).lower()
    check("manifest has no secret-like tokens",
          not any(t in blob for t in ("api_key", "bearer ", "secret=", "password")), "token found")

    # file existence only when prefetch/ populated
    present = list(PREFETCH.glob("*")) if PREFETCH.exists() else []
    if not present:
        print(f"SKIP release/prefetch/ empty — file-existence checks skipped, not failed "
              f"({len(resolved)} resolved / {len(pending)} pending in manifest)")
        print(f"\nALL {PASS} CHECKS PASSED (release manifest)")
        return

    import hashlib
    for entry in resolved:
        target = PREFETCH / str(entry["filename"])
        check(f"prefetch file present: {entry['filename']}", target.exists(), str(target))
        h = hashlib.sha256(target.read_bytes()).hexdigest()
        check(f"prefetch sha256 matches: {entry['filename']}", h == entry["sha256"], h)

    print(f"\nALL {PASS} CHECKS PASSED (release manifest)")


if __name__ == "__main__":
    main()
