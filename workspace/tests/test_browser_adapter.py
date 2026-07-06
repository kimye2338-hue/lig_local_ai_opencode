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
    check("browser adapter is locally validated", browser_spec["available"] is True
          and browser_spec.get("validated", "").startswith("local Chrome CDP, "))
    check("browser adapter keeps company login pending",
          "company validation pending" in browser_spec["pending"])
    check("browser adapter exposes execute", browser_spec["execute"] is browser_cdp.execute)
    # PR #10 expanded ACTIONS with SPA tools; the original five must stay and the
    # SPA set must be declared (declared-but-unexposed was the company-PC lesson).
    check("declared actions include required five",
          {"open_url", "get_title", "extract_text", "screenshot", "list_tabs"}.issubset(browser_cdp.ACTIONS))
    check("declared actions include SPA set",
          {"snapshot", "find_clickables", "click", "wait_for_selector", "select_tab",
           "new_tab", "spa_map", "fill"}.issubset(browser_cdp.ACTIONS))
    check("rendered-text fallback strips script/style",
          "script,style,noscript,template" in browser_cdp.JS_RENDERED_TEXT)
    bat = (WS_TEMPLATE / "launch" / "chrome-debug.bat").read_text(encoding="utf-8")
    check("chrome-debug.bat uses remote debugging port", "--remote-debugging-port=9222" in bat)
    check("chrome-debug.bat uses separate temp profile", "--user-data-dir=\"%OPEN_CODE_LIG_CHROME_PROFILE%\"" in bat
          and "%TEMP%\\opencodelig_chrome" in bat)

    bad = browser_cdp.execute("type_password", {})
    check("unknown action returns ok false", bad["ok"] is False)
    check("unknown action reports available actions", "open_url" in bad["data"]["available_actions"])

    # --- 신규: 열린 탭 크롤링 계약 (정적 — chrome 불필요) ---
    from agent_ops.adapters.browser_cdp import ACTIONS
    check("list_tabs action registered", "list_tabs" in ACTIONS, str(ACTIONS))
    from agent_ops.tool_dispatch import tool_definitions
    names = [d["function"]["name"] for d in tool_definitions()]
    check("agent exposes browse_tabs tool", "browse_tabs" in names, str(names))
    check("agent exposes read_web_page tool", "read_web_page" in names, str(names))
    from agent_ops.tool_dispatch import ToolDispatcher
    disp = ToolDispatcher(WS_TEMPLATE)
    bad = disp.dispatch({"name": "read_web_page", "arguments": {}})
    check("read_web_page requires url or tab", bad["ok"] is False and "url 또는 tab" in bad["error"], str(bad))

    if not chrome_9222_available():
        result = browser_cdp.execute("get_title", {})
        check("missing chrome returns ok false", result["ok"] is False)
        check("missing chrome gives chrome-debug guidance", "chrome-debug.bat을 먼저 실행하세요" in result["error"])
        check("missing chrome preserves action name", result["action"] == "get_title")
        print(f"\nSKIP Chrome CDP live checks - skipped, not failed; ALL {PASS} STATIC CHECKS PASSED (browser adapter)")
        return

    # 오프라인 결정성: 외부(example.com) 대신 임시 file:// 페이지 — 집/회사/CI 어디서든 동일.
    import tempfile
    live_page = Path(tempfile.mkdtemp(prefix="cdp_")) / "live.html"
    live_page.write_text("<html><head><title>CDP Live OK</title></head>"
                         "<body><p>LIVE_MARKER_BODY 텍스트</p></body></html>", encoding="utf-8")
    opened = browser_cdp.execute("open_url", {"url": live_page.as_uri(), "load_timeout": 15})
    check("open_url succeeds on local page", opened["ok"] is True, opened.get("error", ""))
    title = browser_cdp.execute("get_title", {})
    check("get_title returns live title", title["ok"] is True and "CDP Live OK" in title["data"].get("title", ""),
          str(title))
    text = browser_cdp.execute("extract_text", {"max_length": 500})
    check("extract_text returns live body",
          text["ok"] is True and "LIVE_MARKER_BODY" in text["data"].get("text", ""), str(text))
    shot = browser_cdp.execute("screenshot", {"filename": "example.png"})
    shot_path = Path(shot.get("data", {}).get("path", ""))
    check("screenshot writes png under results",
          shot["ok"] is True and shot_path.exists() and shot_path.suffix.lower() == ".png",
          str(shot))

        # 신규: 열린 탭 나열 + 부분일치 attach (live)
    tabs_res = browser_cdp.execute("list_tabs", {})
    check("live list_tabs ok", tabs_res["ok"] and isinstance(tabs_res["data"]["tabs"], list), str(tabs_res)[:200])
    if tabs_res["data"]["tabs"]:
        first_title = tabs_res["data"]["tabs"][0]["title"]
        att = browser_cdp.execute("get_title", {"tab": 0})
        check("live attach by index", att["ok"], str(att)[:200])

    # --- SPA live: 늦은 JS 렌더 + 텍스트 클릭 + fill (2026-07-05 헤드리스 실측 회귀화) ---
    spa_page = live_page.parent / "spa.html"
    spa_page.write_text(
        "<html><head><meta charset='utf-8'><title>SPA Live</title></head>"
        "<body><div id='app'></div><script>"
        "setTimeout(() => {"
        "  document.getElementById('app').innerHTML ="
        "    '<button id=b>SPA_MENU_BTN</button><input id=q placeholder=SPA_SEARCH />"
        "<div id=c>SPA_INITIAL_VIEW</div>';"
        "  document.getElementById('b').addEventListener('click', () => {"
        "    document.getElementById('c').innerText = 'SPA_AFTER_CLICK';});"
        "}, 250);"
        "</script></body></html>", encoding="utf-8")
    opened = browser_cdp.execute("open_url", {"url": spa_page.as_uri(), "load_timeout": 15})
    check("SPA open_url waits for render", opened["ok"] and opened["data"].get("rendered") is True, str(opened))
    snap = browser_cdp.execute("snapshot", {})
    spa_text = snap["data"].get("text", "")
    check("SPA rendered text, no script leak",
          snap["ok"] and "SPA_INITIAL_VIEW" in spa_text and "setTimeout" not in spa_text, spa_text[:120])
    clicked = browser_cdp.execute("click", {"text": "SPA_MENU_BTN"})
    check("SPA click by text", clicked["ok"], str(clicked)[:200])
    waited = browser_cdp.execute("wait_for_selector", {"text": "SPA_AFTER_CLICK"})
    check("SPA click switched view", waited["ok"], str(waited)[:200])
    filled = browser_cdp.execute("fill", {"text": "SPA_SEARCH", "value": "쿼리123"})
    check("SPA fill by placeholder", filled["ok"], str(filled)[:200])
    got = browser_cdp.execute("get_title", {})
    check("sticky tab keeps SPA page", got["ok"] and "SPA Live" in got["data"].get("title", ""), str(got))

    print(f"\nALL {PASS} CHECKS PASSED (browser adapter)")


if __name__ == "__main__":
    main()
