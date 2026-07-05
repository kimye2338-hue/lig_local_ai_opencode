# -*- coding: utf-8 -*-
"""Chrome DevTools Protocol adapter using only stdlib helpers."""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from ..core import RESULTS, now
from .ws_min import WsClient, WsTimeout

CDP_BASE_URL = "http://127.0.0.1:9222"
CHROME_GUIDE = "chrome-debug.bat을 먼저 실행하세요"
ACTIONS = ("open_url", "get_title", "extract_text", "screenshot", "list_tabs")


def execute(action: str, options: Optional[dict] = None) -> dict:
    """Run a small browser action through local Chrome CDP.

    All failures are returned as ok=False so app automation never crashes the
    caller when Chrome is absent or mid-action CDP behavior differs by version.
    """
    opts = options or {}
    if action == "list_tabs":
        try:
            tabs = _json_get("/json")
            pages = [{"index": i, "title": tab.get("title", ""), "url": tab.get("url", "")}
                     for i, tab in enumerate(t for t in tabs if t.get("type") == "page")]
            return {"ok": True, "action": action, "data": {"tabs": pages}}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "action": action, "error": _friendly_error(exc)}
    if action not in ACTIONS:
        return {
            "ok": False,
            "action": action,
            "data": {"available_actions": list(ACTIONS)},
            "error": f"unsupported browser action: {action}",
        }
    try:
        with _connect(opts) as cdp:
            data = _run_action(cdp, action, opts)
            return {"ok": True, "action": action, "data": data, "error": ""}
    except Exception as exc:
        return {"ok": False, "action": action, "data": {}, "error": _friendly_error(exc)}


class _CdpClient:
    def __init__(self, ws_url: str, timeout: float = 5):
        self.ws = WsClient(ws_url, timeout=timeout)
        self.timeout = timeout
        self._next_id = 1

    def __enter__(self) -> "_CdpClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def close(self) -> None:
        self.ws.close()

    def call(self, method: str, params: Optional[dict] = None, timeout: Optional[float] = None) -> dict:
        msg_id = self._next_id
        self._next_id += 1
        self.ws.send_json({"id": msg_id, "method": method, "params": params or {}})
        deadline = time.monotonic() + (timeout or self.timeout)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"CDP response timed out: {method}")
            event = self.ws.recv_json(timeout=remaining)
            if event.get("id") != msg_id:
                continue
            if "error" in event:
                raise RuntimeError(f"CDP {method} failed: {event['error']}")
            return event.get("result", {})


def _connect(options: dict) -> _CdpClient:
    tabs = _json_get("/json")
    if not isinstance(tabs, list):
        raise RuntimeError("Chrome CDP tab list response was not a list")
    # 사용자가 '열어 둔' 특정 탭을 지정: index(정수) 또는 url/title 부분일치 문자열
    want = options.get("tab")
    if want not in (None, ""):
        pages = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        picked = None
        try:
            picked = pages[int(want)]
        except (ValueError, TypeError, IndexError):
            needle = str(want).lower()
            for t2 in pages:
                if needle in str(t2.get("url", "")).lower() or needle in str(t2.get("title", "")).lower():
                    picked = t2
                    break
        if picked is None:
            raise RuntimeError(f"열린 탭에서 '{want}' 을 찾지 못했습니다 — list_tabs로 확인하세요")
        return _CdpClient(picked["webSocketDebuggerUrl"])
    tab = _pick_tab(tabs)
    if tab is None:
        tab = _new_tab()
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        raise RuntimeError("Chrome CDP tab has no webSocketDebuggerUrl")
    return _CdpClient(ws_url, timeout=float(options.get("timeout", 5)))


def _pick_tab(tabs: list[dict]) -> Optional[dict]:
    for tab in tabs:
        if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
            return tab
    return None


def _new_tab() -> dict:
    encoded = urllib.parse.quote("about:blank", safe="")
    try:
        return _json_get(f"/json/new?{encoded}", method="PUT")
    except Exception:
        return _json_get(f"/json/new?{encoded}")


def _json_get(path: str, method: str = "GET") -> Any:
    request = urllib.request.Request(CDP_BASE_URL + path, method=method)
    with urllib.request.urlopen(request, timeout=2) as res:
        return json.loads(res.read().decode("utf-8", errors="replace"))


def _run_action(cdp: _CdpClient, action: str, options: dict) -> dict:
    if action == "open_url":
        url = str(options.get("url") or "")
        if not url.startswith(("http://", "https://", "file://")):
            raise ValueError("open_url requires http(s):// or file:// url")
        cdp.call("Page.enable")
        cdp.call("Page.navigate", {"url": url})
        _wait_ready(cdp, float(options.get("load_timeout", 10)))
        return {"url": url, "status": "loaded"}
    if action == "get_title":
        title = _eval(cdp, "document.title")
        return {"title": title or ""}
    if action == "extract_text":
        max_length = int(options.get("max_length", 4000))
        text = _eval(cdp, "document.body ? document.body.innerText : ''") or ""
        return {"text": text[:max_length], "truncated": len(text) > max_length}
    if action == "screenshot":
        cdp.call("Page.enable")
        result = cdp.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True}, timeout=10)
        data = result.get("data")
        if not isinstance(data, str) or not data:
            raise RuntimeError("CDP screenshot returned no image data")
        out_path = _screenshot_path(options.get("filename"))
        out_path.write_bytes(base64.b64decode(data))
        return {"path": str(out_path)}
    raise AssertionError(f"unhandled action: {action}")


def _eval(cdp: _CdpClient, expression: str) -> Any:
    result = cdp.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
    return result.get("result", {}).get("value")


def _wait_ready(cdp: _CdpClient, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while True:
        state = _eval(cdp, "document.readyState")
        if state in ("interactive", "complete"):
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("page load timed out")
        time.sleep(0.2)


def _screenshot_path(filename: object) -> Path:
    screenshots = RESULTS / "browser_screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    name = str(filename or f"browser_{now().replace(':', '').replace('-', '').replace('T', '_')}.png")
    if not name.lower().endswith(".png"):
        name += ".png"
    return screenshots / Path(name).name


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, (ConnectionRefusedError, urllib.error.URLError, TimeoutError, WsTimeout)):
        return f"{CHROME_GUIDE} ({exc})"
    text = str(exc) or repr(exc)
    if "WinError 10061" in text or "Connection refused" in text:
        return f"{CHROME_GUIDE} ({text})"
    return text
