# -*- coding: utf-8 -*-
"""Obsidian vault seed regression tests."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def main() -> None:
    from agent_ops.wiki_vault import seed_obsidian_vault

    vault = Path(tempfile.mkdtemp(prefix="wiki_vault_")) / "wiki"
    result = seed_obsidian_vault(vault)
    welcome = (vault / "0-위키-안내.md").read_text(encoding="utf-8")

    check("core plugins seeded", (vault / ".obsidian" / "core-plugins.json").is_file())
    check("welcome points humans to manual or remember",
          "`manual/`" in welcome and "`remember`" in welcome, welcome)
    check("welcome does not promise direct edits persist",
          "직접 수정하면 다음 정리에 반영" not in welcome, welcome)
    check("welcome states auto pages are regenerated",
          "자동 생성 페이지는 원장에서 재생성" in welcome, welcome)

    app_json = vault / ".obsidian" / "app.json"
    app_json.write_text('{"custom": true}', encoding="utf-8")
    second = seed_obsidian_vault(vault)
    check("second seed is idempotent for user settings",
          second["already_ready"] and app_json.read_text(encoding="utf-8") == '{"custom": true}',
          str(second))
    check("first seed reports welcome note", "0-위키-안내.md" in result["seeded"], str(result))

    print("\nALL CHECKS PASSED (wiki vault)")


if __name__ == "__main__":
    main()
