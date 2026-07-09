# -*- coding: utf-8 -*-
"""Regression checks for the OpenCode permission-mode prompt badge patch."""
from __future__ import annotations

from pathlib import Path

PATCH = Path(__file__).resolve().parents[1] / "patches" / "opencode-permission-mode-toggle.patch"

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        raise SystemExit(1)


def main() -> None:
    text = PATCH.read_text(encoding="utf-8")
    check("patch touches prompt footer badge location",
          "packages/tui/src/component/prompt/index.tsx" in text)
    check("patch removes auto-only badge condition",
          '-                      <Show when={store.mode === "normal" && local.permission.mode === "auto"}>' in text and
          '+                      <Show when={store.mode === "normal"}>' in text)
    check("patch renders current permission mode beside agent",
          "local.permission.mode.toUpperCase()" in text)
    check("patch keeps ask visually quiet but visible",
          'local.permission.mode === "ask" ? theme.textMuted' in text)
    print(f"\nALL {PASS} CHECKS PASSED (opencode permission badge patch)")


if __name__ == "__main__":
    main()
