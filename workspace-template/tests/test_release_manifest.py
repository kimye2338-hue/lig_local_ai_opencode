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
    deferred = [f for f in files if str(f.get("status", "")).startswith("deferred")]
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

    # deferred = out of pilot scope (local-serving/voice only). Must NOT carry a
    # fake hash, and must explain why it is deferred — so the manifest stays honest.
    for entry in deferred:
        check(f"deferred entry has no fake hash: {entry['filename']}",
              not HEX64.match(str(entry["sha256"])), str(entry["sha256"]))
        check(f"deferred entry explains why: {entry['filename']}",
              len(str(entry["status"])) > 20, str(entry["status"]))

    # Pilot scope: the office/COM wheels the pilot actually needs are all resolved,
    # so the pilot bundle needs zero home-PC binary downloads.
    wheels = [f for f in files if "wheels" in str(f.get("category", ""))]
    check("all office/COM wheels resolved (pilot needs no home download)",
          bool(wheels) and all(str(w.get("status", "")).startswith("resolved") for w in wheels),
          str([w["filename"] for w in wheels if not str(w.get("status", "")).startswith("resolved")]))

    # no secrets/hosts in the manifest
    blob = json.dumps(manifest, ensure_ascii=False).lower()
    check("manifest has no secret-like tokens",
          not any(t in blob for t in ("api_key", "bearer ", "secret=", "password")), "token found")

    # bundle build check always runs (does not need prefetch/)
    _check_bundle_build()

    # file existence only when prefetch/ populated
    present = list(PREFETCH.glob("*")) if PREFETCH.exists() else []
    if not present:
        print(f"SKIP release/prefetch/ empty — file-existence checks skipped, not failed "
              f"({len(resolved)} resolved / {len(pending)} pending in manifest)")
        print(f"\nALL {PASS} CHECKS PASSED (release manifest)")
        return

    import hashlib
    # Pilot scope mirrors verify_prefetch: local-serving/voice categories are
    # optional (hash-verified only when present); wheels/runtime must exist.
    non_pilot = {"llm-gguf", "asr-model", "binary-github"}
    for entry in resolved:
        target = PREFETCH / str(entry["filename"])
        if not target.exists() and str(entry.get("category", "")) in non_pilot:
            print(f"OPT   {entry['filename']} — pilot-optional, not prefetched (ok)")
            continue
        check(f"prefetch file present: {entry['filename']}", target.exists(), str(target))
        h = hashlib.sha256(target.read_bytes()).hexdigest()
        check(f"prefetch sha256 matches: {entry['filename']}", h == entry["sha256"], h)

    print(f"\nALL {PASS} CHECKS PASSED (release manifest)")


def _check_bundle_build() -> None:
    """Run release/build_bundle.py into a tmp dir and validate the zip + manifest."""
    import importlib.util
    import tempfile
    import zipfile

    bb_path = REPO_ROOT / "release" / "build_bundle.py"
    check("build_bundle.py exists", bb_path.exists(), str(bb_path))
    spec = importlib.util.spec_from_file_location("build_bundle", bb_path)
    bb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bb)

    out = Path(tempfile.mkdtemp(prefix="bundle_test_"))
    zip_path = bb.build("testdate", out)
    check("bundle zip created", zip_path.exists() and zip_path.suffix == ".zip", str(zip_path))
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        check("bundle has MANIFEST_SHA256.txt", "MANIFEST_SHA256.txt" in names, str(names[:5]))
        # One-click install UX: root installer + first-read + daily menu + py resolver
        check("bundle has root 설치.bat", "설치.bat" in names, "no root installer")
        check("bundle has 처음_읽어주세요.txt", "처음_읽어주세요.txt" in names, "no first-read")
        check("bundle has AI비서 shim", any(n.endswith("launch/AI비서.bat") for n in names), "no shim")
        check("bundle has menu.bat (ASCII filename for cp949-safe call)",
              any(n.endswith("launch/menu.bat") for n in names), "no menu.bat")
        # cp949 트랩 가드: 더블클릭된 bat는 기본 코드페이지로 '내용'을 읽으므로,
        # bat 내용이 참조하는 파일명은 ASCII여야 한다 (한글은 파일 '이름'에만 허용).
        shim = zf.read([n for n in names if n.endswith("launch/AI비서.bat")][0])
        check("AI비서 shim content is pure ASCII",
              all(b < 0x80 for b in shim), "non-ascii in shim content")
        check("setup.bat desktop launcher calls ASCII menu.bat",
              b'echo call "menu.bat"' in zf.read("release/setup.bat"),
              "desktop launcher not ASCII-target")
        check("bundle has _py resolver", any(n.endswith("launch/_py.bat") for n in names), "no _py")
        inst = zf.read("설치.bat")
        check("root installer is CRLF", inst.count(b"\n") == inst.count(b"\r\n") > 0, "LF installer")
        setup = zf.read("release/setup.bat")
        check("setup.bat is CRLF", setup.count(b"\n") == setup.count(b"\r\n") > 0, "LF setup")
        # setup.bat lives in release/ but must treat the BUNDLE ROOT (its parent)
        # as ROOT — regression guard for the '%~dp0' path bug that broke install
        # (looked for release\workspace-template / release\release\prefetch).
        check("setup.bat resolves ROOT to bundle root (parent of release/)",
              b'%~dp0..' in setup, "ROOT not parent-resolved")
        check("setup.bat guards missing workspace-template with a clear stop",
              "번들 구조를 찾지 못했습니다".encode("utf-8") in setup, "no structure guard")
        check("launch bats do not hardcode py -3.11",
              not any(b"py -3.11 agent_ops" in zf.read(n) for n in names
                      if n.endswith(".bat") and "launch/" in n and not n.endswith("_py.bat")),
              "hardcoded launcher remains")
        check("bundle includes workspace-template source",
              any(n.startswith("workspace-template/agent_ops/") for n in names), str(len(names)))
        check("bundle includes plan board", any(n == "plan/STATUS.md" for n in names), "no STATUS")
        # manifest lists a sha256 per archived file (minus the manifest itself)
        manifest = zf.read("MANIFEST_SHA256.txt").decode("utf-8")
        hash_lines = [ln for ln in manifest.splitlines() if ln and not ln.startswith("#")]
        archived = [n for n in names if n != "MANIFEST_SHA256.txt"]
        check("manifest has one sha256 line per archived file",
              len(hash_lines) == len(archived), f"{len(hash_lines)} vs {len(archived)}")
        check("manifest lines are 64-hex + path",
              all(HEX64.match(ln.split("  ")[0]) for ln in hash_lines), "bad hash line")
    # no lig-api.env / secrets bundled
    check("bundle carries no lig-api.env", not any("lig-api.env" in n for n in names), "leak")


if __name__ == "__main__":
    main()
