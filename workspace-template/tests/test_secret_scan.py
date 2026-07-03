# -*- coding: utf-8 -*-
"""Tests for staged secret pre-commit scanner.

Run: py -3.11 tests\test_secret_scan.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

WS_TEMPLATE = Path(__file__).resolve().parents[1]
SCANNER = WS_TEMPLATE / "scripts" / "precommit_scan.py"
PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def run_git(repo: Path, args: list[str]) -> None:
    result = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def make_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix="secret_scan_repo_"))
    run_git(repo, ["init"])
    return repo


def scan_repo(repo: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    merged = dict(os.environ)
    if env:
        merged.update(env)
    return subprocess.run(["py", "-3.11", str(SCANNER)], cwd=str(repo),
                          env=merged, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def write_stage(repo: Path, name: str, text: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    run_git(repo, ["add", name])


def assert_blocks(label: str, name: str, text: str, needle: str) -> None:
    repo = make_repo()
    write_stage(repo, name, text)
    result = scan_repo(repo)
    check(label, result.returncode == 1 and needle in result.stdout,
          result.stdout + result.stderr)


def main() -> None:
    assert_blocks("blocks LIG_API_KEY real-looking value", "a.env", "LIG_API_KEY=FAKEKEY123456\n", "lig_api_key")
    repo = make_repo()
    write_stage(repo, "placeholder.env", "LIG_API_KEY=PUT_INTERNAL_API_KEY_OR_USE_ENV\n")
    result = scan_repo(repo)
    check("allows placeholder API key", result.returncode == 0, result.stdout + result.stderr)

    assert_blocks("blocks bearer token", "b.txt", "Authorization: Bearer FAKEBEARER123\n", "bearer")
    assert_blocks("blocks generic api key", "c.txt", "api_key = FAKEVALUE12345\n", "key_token_password")
    assert_blocks("blocks generic internal hostname", "d.txt", "url=https://gateway.local/v1\n", "internal_hostname")

    repo = make_repo()
    write_stage(repo, "allowed.txt", "api_key = FAKEVALUE12345  # secret-scan-ok\n")
    result = scan_repo(repo)
    check("allows explicit scan exception comment", result.returncode == 0, result.stdout + result.stderr)

    repo = make_repo()
    write_stage(repo, "한글.txt", "일반 업무 메모\n토큰이라는 단어만 있음\n")
    result = scan_repo(repo)
    check("korean text has no false positive", result.returncode == 0, result.stdout + result.stderr)

    repo = make_repo()
    extra = repo / "patterns.txt"
    extra.write_text(r"custom-forbidden-\d+", encoding="utf-8")
    write_stage(repo, "extra.txt", "custom-forbidden-123\n")
    result = scan_repo(repo, {"LIG_SECRET_EXTRA_PATTERNS": str(extra)})
    check("extra pattern file is honored", result.returncode == 1 and "extra:1" in result.stdout,
          result.stdout + result.stderr)

    install = (WS_TEMPLATE / "scripts" / "install_hooks.bat").read_text(encoding="utf-8")
    check("install hook calls scanner", "precommit_scan.py" in install and "py -3.11" in install
          and "git rev-parse --show-toplevel" in install)
    print(f"\nALL {PASS} CHECKS PASSED (secret scan)")


if __name__ == "__main__":
    main()
