# -*- coding: utf-8 -*-
"""Build the offline bring-in bundle for the company PC.

Run: py -3.11 release\\build_bundle.py [--date YYYYMMDD] [--out DIR]

Packages the source tree (workspace-template + plan + docs + release manifest/
scripts) plus any prefetched binaries (release/prefetch/*) into a single
`OpenCodeLIG_BUNDLE_<date>.zip` with an internal `MANIFEST_SHA256.txt` listing
every archived file's SHA256. Pure stdlib. No network.

The zip is a transparent archive (no self-extracting exe, no encoded payload),
per release/dependencies.json transfer policy. Secrets never belong in the
bundle — a pre-zip scan rejects lig-api.env / obvious key files.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# What goes in. Directories are walked; missing ones are skipped with a note.
INCLUDE_DIRS = [
    "workspace-template",
    "plan",
    "docs",
]
INCLUDE_FILES = [
    "release/dependencies.json",
    "release/verify_prefetch.py",
    "release/setup.bat",
    "README.md",
    "AGENTS.md",
]
# Prefetched binaries (gitignored, present only after P17-02 downloads on a
# home/dev PC). Included when present.
PREFETCH_DIR = REPO_ROOT / "release" / "prefetch"

# Never bundle these (secret / noise), even if they slip into a source dir.
EXCLUDE_SUBSTRINGS = [
    "lig-api.env",
    "__pycache__/",
    ".pyc",
    "/모의_결과/",
    "/prefetch/",  # prefetch handled explicitly below (kept, but not via dir walk)
    ".git/",
]
# Precise secret-file markers (must not false-positive on test_secret_scan.py etc.).


def _excluded(rel: str) -> bool:
    return any(sub in rel for sub in EXCLUDE_SUBSTRINGS)


def _iter_source_files() -> list[tuple[Path, str]]:
    items: list[tuple[Path, str]] = []
    for d in INCLUDE_DIRS:
        base = REPO_ROOT / d
        if not base.exists():
            print(f"  (skip missing dir: {d})")
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO_ROOT).as_posix()
            if _excluded(rel):
                continue
            items.append((p, rel))
    for f in INCLUDE_FILES:
        p = REPO_ROOT / f
        if p.exists():
            items.append((p, p.relative_to(REPO_ROOT).as_posix()))
        else:
            print(f"  (skip missing file: {f})")
    return items


def _iter_prefetch_files() -> list[tuple[Path, str]]:
    if not PREFETCH_DIR.exists():
        print("  (no release/prefetch/ — bundle will carry source only; run P17-02 "
              "downloads on a home/dev PC first for a complete bundle)")
        return []
    out: list[tuple[Path, str]] = []
    for p in sorted(PREFETCH_DIR.rglob("*")):
        if p.is_file():
            out.append((p, "release/prefetch/" + p.relative_to(PREFETCH_DIR).as_posix()))
    return out


def _is_secret_file(rel: str) -> bool:
    low = rel.lower()
    name = low.rsplit("/", 1)[-1]
    if name == "lig-api.env":
        return True
    if "/secrets/" in low:                       # a secrets/ directory
        return True
    if name.endswith(".env") and not name.endswith(".env.example"):
        return True
    return False


def _secret_scan(files: list[tuple[Path, str]]) -> list[str]:
    return [rel for _p, rel in files if _is_secret_file(rel)]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build(date: str, out_dir: Path) -> Path:
    source = _iter_source_files()
    prefetch = _iter_prefetch_files()
    all_files = source + prefetch

    secret_hits = _secret_scan(all_files)
    if secret_hits:
        raise SystemExit(f"[ABORT] secret-like files would be bundled: {secret_hits}")

    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"OpenCodeLIG_BUNDLE_{date}.zip"

    # Root-level one-click installer + first-read note (generated, CRLF for Windows).
    installer = ("@echo off\r\n"
                 "chcp 65001 >nul\r\n"
                 "cd /d \"%~dp0\"\r\n"
                 "call release\\setup.bat\r\n")
    first_read = ("OpenCodeLIG 설치 방법 (1분)\r\n"
                  "\r\n"
                  "1. 이 폴더의  설치.bat  을 더블클릭하세요.\r\n"
                  "2. 게이트웨이 주소/API 키를 붙여넣으세요 (모르면 그냥 Enter — 나중에 설정 가능).\r\n"
                  "3. 끝. 바탕화면에 생긴  AI비서  를 실행하면 됩니다.\r\n"
                  "\r\n"
                  "문제가 생기면: workspace-template\\docs\\RUNBOOK.md 또는 워크스페이스의 launch\\diag.bat 실행.\r\n")

    manifest_lines = ["# MANIFEST_SHA256 — every archived file", f"# bundle: {zip_path.name}", ""]
    print(f"packing {len(all_files)} files ({len(source)} source + {len(prefetch)} prefetch) ...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, rel in all_files:
            zf.write(p, rel)
            manifest_lines.append(f"{_sha256(p)}  {rel}")
        for rel, text in (("설치.bat", installer), ("처음_읽어주세요.txt", first_read)):
            data = text.encode("utf-8")
            zf.writestr(rel, data)
            manifest_lines.append(f"{hashlib.sha256(data).hexdigest()}  {rel}")
        manifest_text = "\n".join(manifest_lines) + "\n"
        zf.writestr("MANIFEST_SHA256.txt", manifest_text)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"built {zip_path}  ({size_mb:.1f} MB, {len(all_files)} files + MANIFEST_SHA256.txt)")
    if not prefetch:
        print("NOTE: source-only bundle. Fill release/prefetch/ (P17-02) for the full "
              "offline install, then rebuild.")
    return zip_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="", help="YYYYMMDD (default: passed by caller / build stamp)")
    ap.add_argument("--out", default=str(REPO_ROOT / "release" / "dist"))
    args = ap.parse_args(argv)
    date = args.date or "unstamped"
    build(date, Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
