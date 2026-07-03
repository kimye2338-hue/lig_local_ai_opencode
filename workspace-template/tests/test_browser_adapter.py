# -*- coding: utf-8 -*-
"""Browser CDP adapter tests.

Run: py -3.11 tests\test_browser_adapter.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

tmp_root = Path(tempfile.mkdtemp(prefix="browser_adapter_test_"))
os.environ["AGENTOPS_ROOT"] = str(tmp_root)

WS_TEMPLATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS_TEMPLATE))

from agent_ops.adapters import ADAPTERS  # noqa: E402
from agent_ops.adapters import browser_cdp  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def chrome_9222_available() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=1) as res:
            json.loads(res.read().decode("utf-8", errors="replace"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


def main() -> None:
    browser_spec = ADAPTERS["browser"]
    check("browser adapter keeps available false", browser_spec["available"] is False)
    check("browser adapter exposes execute", browser_spec["execute"] is browser_cdp.execute)
    check("declared actions include required four",
          set(browser_cdp.ACTIONS) == {"open_url", "get_title", "extract_text", "screenshot"})
    bat = (WS_TEMPLATE / "launch" / "chrome-debug.bat").read_text(encoding="utf-8")
    check("chrome-debug.bat uses remote debugging port", "--remote-debugging-port=9222" in bat)
    check("chrome-debug.bat uses separate temp profile", "--user-data-dir=\"%OPEN_CODE_LIG_CHROME_PROFILE%\"" in bat
          and "%TEMP%\\opencodelig_chrome" in bat)

    bad = browser_cdp.execute("type_password", {})
    check("unknown action returns ok false", bad["ok"] is False)
    check("unknown action reports available actions", "open_url" in bad["data"]["available_actions"])

    if not chrome_9222_available():
        result = browser_cdp.execute("get_title", {})
        check("missing chrome returns ok false", result["ok"] is False)
        check("missing chrome gives chrome-debug guidance", "chrome-debug.bat을 먼저 실행하세요" in result["error"])
        check("missing chrome preserves action name", result["action"] == "get_title")
        print(f"\nSKIP Chrome CDP live checks - skipped, not failed; ALL {PASS} STATIC CHECKS PASSED (browser adapter)")
        return

    opened = browser_cdp.execute("open_url", {"url": "https://example.com", "load_timeout": 15})
    check("open_url succeeds on example.com", opened["ok"] is True, opened.get("error", ""))
    title = browser_cdp.execute("get_title", {})
    check("get_title returns example title", title["ok"] is True and "Example" in title["data"].get("title", ""),
          str(title))
    text = browser_cdp.execute("extract_text", {"max_length": 500})
    check("extract_text returns example domain body",
          text["ok"] is True and "Example Domain" in text["data"].get("text", ""), str(text))
    shot = browser_cdp.execute("screenshot", {"filename": "example.png"})
    shot_path = Path(shot.get("data", {}).get("path", ""))
    check("screenshot writes png under results",
          shot["ok"] is True and shot_path.exists() and shot_path.suffix.lower() == ".png",
          str(shot))

    print(f"\nALL {PASS} CHECKS PASSED (browser adapter)")


if __name__ == "__main__":
    main()
