# -*- coding: utf-8 -*-
"""Verify prefetched dependency files against release/dependencies.json.

Run: py -3.11 release\\verify_prefetch.py

For each `prefetch_files` entry whose status starts with "resolved", check that
release/prefetch/<filename> exists and its SHA256 matches. Pilot scope: only
pilot categories (wheels / python runtime) MUST be present — resolved models
(llm-gguf / asr-model) are local-serving/voice-only, so a missing one prints
OPT, not a failure (hash is still verified when the file IS present). deferred
entries print DEFER; PENDING entries print PEND — neither fails. If
release/prefetch/ is empty (CI / no downloads yet), print SKIP and exit 0 —
this is a manifest integrity tool, not a download gate.

Exit codes: 0 ok / SKIP, 1 hash mismatch or missing pilot-required file.
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


# Categories NOT required for the company_gateway pilot: local LLM serving and
# voice (P20). Their hashes are still verified when the file is present.
_NON_PILOT_CATEGORIES = {"llm-gguf", "asr-model", "binary-github"}


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = manifest.get("prefetch_files", [])
    resolved = [f for f in files if str(f.get("status", "")).startswith("resolved")]
    pending = [f for f in files if "PENDING" in str(f.get("status", ""))]
    deferred = [f for f in files if str(f.get("status", "")).startswith("deferred")]

    present = list(PREFETCH.glob("*")) if PREFETCH.exists() else []
    if not present:
        print(f"SKIP  release/prefetch/ is empty — manifest lists {len(resolved)} resolved "
              f"+ {len(pending)} pending + {len(deferred)} deferred; nothing to verify here. "
              f"(skipped, not failed)")
        return 0

    failures = 0
    verified = 0
    for entry in resolved:
        target = PREFETCH / str(entry["filename"])
        optional = str(entry.get("category", "")) in _NON_PILOT_CATEGORIES
        if not target.exists():
            if optional:
                print(f"OPT   {entry['filename']} — 파일럿 불필요(로컬서빙/음성 전용); 미반입 정상")
            else:
                print(f"MISS  {entry['filename']} — pilot-required but not in prefetch/")
                failures += 1
            continue
        actual = _sha256(target)
        if actual != entry["sha256"]:
            print(f"FAIL  {entry['filename']} sha256 mismatch\n      manifest={entry['sha256']}\n      actual  ={actual}")
            failures += 1
        else:
            print(f"OK    {entry['filename']}")
            verified += 1
    for entry in pending:
        print(f"PEND  {entry['filename']} — {entry['status']}")
    for entry in deferred:
        print(f"DEFER {entry['filename']} — {entry['status']}")

    if failures:
        print(f"\n{failures} verification failure(s).")
        return 1
    print(f"\n{verified} file(s) hash-verified; {len(deferred)} deferred (not needed for pilot); "
          f"{len(pending)} pending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
