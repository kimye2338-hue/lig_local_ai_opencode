# -*- coding: utf-8 -*-
"""User-facing documentation sanity checks."""
from __future__ import annotations

import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
DOCS = WS / "docs"


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def read(rel: str) -> str:
    return (DOCS / rel).read_text(encoding="utf-8")


def main() -> None:
    guide = read("사용법/GUIDE.md")
    install = read("사용법/INSTALL.md")
    runbook = read("사용법/RUNBOOK.md")
    docs_readme = read("README.md")
    obsidian = read("기능/OBSIDIAN_WIKI.md")

    check("README points to single user guide", "사용법/GUIDE.md" in docs_readme)
    check("guide covers install/run/memory/troubleshooting",
          all(s in guide for s in ("설치와 첫 실행", "실행 방법", "기억, 지식책, LLM Wiki", "문제가 생기면")))
    check("guide lists actual main launchers",
          "RUN_OPENCODE_LIG.bat" in guide and "launch\\menu.bat" in guide and "launch\\wiki.bat" in guide)
    check("guide explains auto pages are regenerated",
          "자동 페이지는 다음 정리 때" in guide and "manual\\" in guide)
    check("install is a short summary", len(install.splitlines()) < 80)
    check("runbook is a short response table", len(runbook.splitlines()) < 90 and "빠른 대응" in runbook)

    stale_phrases = [
        "A. agent_ops 번들",
        "B. OpenCode TUI",
        "workspace-template",
        "docs\\RUNBOOK.md",
        "직접 수정하면 다음 정리에 반영",
    ]
    combined = "\n".join([guide, install, runbook, docs_readme, obsidian])
    check("user docs have no stale packaging or wiki-edit promises",
          not any(p in combined for p in stale_phrases),
          ", ".join(p for p in stale_phrases if p in combined))
    check("verify command is documented as stable fallback",
          "python agent_ops\\agentops.py verify" in guide
          and "python agent_ops\\agentops.py verify" in install
          and "python agent_ops\\agentops.py verify" in runbook)

    print("\nALL CHECKS PASSED (user docs)")


if __name__ == "__main__":
    main()
