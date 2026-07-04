# -*- coding: utf-8 -*-
"""Offline-install rehearsal pre-flight (the cloud-doable half of P17-04).

Run: py -3.11 release\\rehearsal_check.py

The *actual* rehearsal is a HUMAN step (disable the network adapter, run
setup.bat, record doctor) — see docs/OFFLINE_REHEARSAL.md. This script front-loads
everything that can be checked *without* cutting the network, so the human run only
has to confirm what a machine cannot: real air-gap behaviour.

Checks (pure stdlib, no network):
  1. build_bundle.py produces a valid zip (reuses the P17-03 builder into a tmp dir).
  2. setup.bat is offline-safe: installs with --no-index, and contains NO network
     fetch commands (curl / Invoke-WebRequest / git clone / bare `pip install <pkg>`
     without --no-index / `--index-url`). This is deterministic → hard-fail.
  3. Runtime-network audit (advisory): grep bundled *.py for outbound calls
     (urlopen/requests/socket.connect/http(s)://) that would fire at import or
     startup, so the human knows exactly where to watch during the air-gap run.
     localhost / 127.0.0.1 / {env:} gateway URLs are expected and flagged OK.

Exit 0 = pre-flight clean (advisories may still print). Exit 1 = a hard offline
guarantee is broken — fix before the human rehearsal.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SETUP_BAT = REPO_ROOT / "release" / "setup.bat"
BUILD_BUNDLE = REPO_ROOT / "release" / "build_bundle.py"
PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def _check_bundle_builds() -> list[str]:
    check("build_bundle.py exists", BUILD_BUNDLE.exists(), str(BUILD_BUNDLE))
    spec = importlib.util.spec_from_file_location("build_bundle", BUILD_BUNDLE)
    bb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bb)
    out = Path(tempfile.mkdtemp(prefix="rehearsal_"))
    zip_path = bb.build("rehearsal", out)
    check("bundle zip built", zip_path.exists() and zip_path.suffix == ".zip", str(zip_path))
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    check("bundle carries setup.bat", any(n.endswith("release/setup.bat") for n in names), "no setup.bat")
    check("bundle carries doctor", any(n.endswith("agent_ops/doctor.py") for n in names), "no doctor")
    check("bundle carries no lig-api.env", not any("lig-api.env" in n for n in names), "leak")
    return names


# Network-fetch commands that would need internet if they ran during setup.
_NET_FETCH = re.compile(
    r"\b(curl|wget|bitsadmin|Invoke-WebRequest|iwr|Start-BitsTransfer)\b"
    r"|git\s+clone"
    r"|certutil\s+.*-urlcache",
    re.IGNORECASE,
)
# A pip line is offline-safe only if it forces --no-index (and no --index-url).
_PIP_LINE = re.compile(r"pip\s+(?:install|download)\b", re.IGNORECASE)


def _check_setup_offline_safe() -> None:
    check("setup.bat exists", SETUP_BAT.exists(), str(SETUP_BAT))
    text = SETUP_BAT.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    for i, ln in enumerate(lines, 1):
        stripped = ln.strip().lower()
        if stripped.startswith("rem") or stripped.startswith("::"):
            continue  # comment line — not executed
        check(f"setup.bat line {i} has no -ExecutionPolicy Bypass",
              "executionpolicy bypass" not in stripped, ln.strip())
        if _NET_FETCH.search(ln):
            check(f"setup.bat line {i} has no network fetch", False, ln.strip())
        if _PIP_LINE.search(ln):
            offline = "--no-index" in stripped and "--index-url" not in stripped
            check(f"setup.bat pip line {i} is offline (--no-index, no --index-url)",
                  offline, ln.strip())
    check("setup.bat scanned for offline safety", True)


# Runtime outbound-call markers (advisory — reported, not failed).
_OUTBOUND = re.compile(
    r"urllib\.request\.urlopen|requests\.(get|post|request)|http\.client|"
    r"socket\.create_connection|\.connect\(\s*\(|https?://",
    re.IGNORECASE,
)
_LOCAL_OK = re.compile(r"localhost|127\.0\.0\.1|0\.0\.0\.0|\{env:|<gateway|example\.com|opencode\.ai", re.IGNORECASE)


def _audit_runtime_network() -> None:
    """Advisory: list where bundled python could reach the network at runtime."""
    print("\n--- runtime-network audit (advisory — watch these during the air-gap run) ---")
    ops = REPO_ROOT / "workspace-template" / "agent_ops"
    hits = 0
    for py in sorted(ops.rglob("*.py")):
        try:
            src = py.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, ln in enumerate(src, 1):
            if _OUTBOUND.search(ln):
                rel = py.relative_to(REPO_ROOT).as_posix()
                tag = "OK(local/env)" if _LOCAL_OK.search(ln) else "REVIEW"
                print(f"  [{tag}] {rel}:{i}  {ln.strip()[:90]}")
                hits += 1
    if hits == 0:
        print("  (none — agent_ops core makes no outbound calls; CDP adapter uses "
              "localhost debug port only)")
    else:
        print(f"  {hits} outbound-capable line(s). REVIEW items must resolve to the "
              "LIG gateway (env-configured) or a local port — never a public host.")


def main() -> int:
    print("=== P17-04 offline rehearsal pre-flight ===\n")
    print("[1] bundle build")
    _check_bundle_builds()
    print("\n[2] setup.bat offline safety")
    _check_setup_offline_safe()
    _audit_runtime_network()
    print(f"\nALL {PASS} PRE-FLIGHT CHECKS PASSED (offline rehearsal)")
    print("Next: HUMAN air-gap run — see docs/OFFLINE_REHEARSAL.md (disable network, "
          "run setup.bat, capture outbound traffic, record plan/reports/P17-04-r1.md).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
