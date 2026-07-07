# -*- coding: utf-8 -*-
"""Secret/hostname staged-file scanner for the git pre-commit hook."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Pattern

ALLOW_MARKER = "# secret-scan-ok"
TEXT_EXTENSIONS = {
    ".bat", ".bas", ".cfg", ".cmd", ".env", ".ini", ".json", ".md", ".ps1",
    ".py", ".txt", ".yaml", ".yml",
}
BASE_PATTERNS = [
    # 플레이스홀더(PUT_/REPLACE_WITH_)만 통과 — 그 외 값은 첫 글자와 무관하게 전부 탐지
    ("lig_api_key", re.compile(r"LIG_API_KEY\s*=\s*(?!PUT_|REPLACE_WITH_)\S", re.IGNORECASE)),
    ("bearer", re.compile(r"Bearer\s+[A-Za-z0-9]", re.IGNORECASE)),
    ("key_token_password", re.compile(r"(api[_-]?key|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9]{8,}", re.IGNORECASE)),
    ("internal_hostname", re.compile(r"\b[a-z0-9-]+\.(?:local|internal|corp)\b", re.IGNORECASE)),
]


def _git(args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace")


def staged_files(cwd: Path) -> List[str]:
    result = _git(["diff", "--cached", "--name-only", "--diff-filter=ACMRT"], cwd)
    if result.returncode != 0:
        print(result.stderr.strip() or "git diff --cached failed", file=sys.stderr)
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _extra_patterns() -> List[tuple[str, Pattern[str]]]:
    raw = os.environ.get("LIG_SECRET_EXTRA_PATTERNS", "").strip()
    if not raw:
        return []
    path = Path(raw)
    if not path.exists():
        return []
    patterns = []
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        patterns.append((f"extra:{idx}", re.compile(text, re.IGNORECASE)))
    return patterns


def _staged_text(cwd: Path, name: str) -> str | None:
    if Path(name).suffix.lower() not in TEXT_EXTENSIONS:
        return None
    result = _git(["show", f":{name}"], cwd)
    if result.returncode != 0 or "\x00" in result.stdout[:2000]:
        return None
    return result.stdout


def scan(cwd: Path, names: Iterable[str]) -> List[str]:
    patterns = BASE_PATTERNS + _extra_patterns()
    findings: List[str] = []
    for name in names:
        text = _staged_text(cwd, name)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if ALLOW_MARKER in line:
                continue
            for label, pattern in patterns:
                if pattern.search(line):
                    findings.append(f"{name}:{lineno}: {label}")
    return findings


def main(argv: List[str] | None = None) -> int:
    cwd = Path.cwd()
    names = staged_files(cwd)
    findings = scan(cwd, names)
    if findings:
        print("Secret scan failed:")
        for item in findings:
            print(f"  {item}")
        return 1
    print("Secret scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
