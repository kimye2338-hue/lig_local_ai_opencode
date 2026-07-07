# -*- coding: utf-8 -*-
"""Chrome DevTools Protocol adapter using only stdlib helpers."""
from __future__ import annotations

import base64
import html
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from ..core import RESULTS, now
from .ws_min import WsClient, WsTimeout

CDP_BASE_URL = "http://127.0.0.1:9222"
CHROME_GUIDE = "chrome-debug.bat을 먼저 실행하세요"
ACTIONS = (
    "open_url",
    "get_title",
    "extract_text",
    "snapshot",
    "find_clickables",
    "click",
    "fill",
    "screenshot",
    "wait_for_selector",
    "list_tabs",
    "select_tab",
    "new_tab",
    "spa_map",
)

# 마지막으로 작업한 탭 id — 액션마다 새로 접속해도 같은 탭을 계속 본다.
# 이게 없으면 open_url 한 탭과 click/snapshot 이 보는 탭이 달라질 수 있다
# (탭 순서는 크롬이 임의로 바꾼다 — 2026-07-05 헤드리스 실측에서 재현).
_ACTIVE_TAB_ID: Optional[str] = None


JS_CLICKABLES = r"""
(() => {
  function cssPath(el) {
    if (!el || !el.tagName) return '';
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    while (el && el.nodeType === Node.ELEMENT_NODE && parts.length < 5) {
      let part = el.tagName.toLowerCase();
      if (el.classList && el.classList.length) {
        part += '.' + Array.from(el.classList).slice(0, 2).map(c => CSS.escape(c)).join('.');
      }
      const parent = el.parentElement;
      if (parent) {
        const same = Array.from(parent.children).filter(x => x.tagName === el.tagName);
        if (same.length > 1) part += ':nth-of-type(' + (same.indexOf(el) + 1) + ')';
      }
      parts.unshift(part);
      el = parent;
    }
    return parts.join(' > ');
  }
  const selector = [
    'a[href]', 'button', 'input[type=button]', 'input[type=submit]',
    '[role=button]', '[role=link]', '[onclick]', '[tabindex]'
  ].join(',');
  return Array.from(document.querySelectorAll(selector)).map((el, index) => {
    const rect = el.getBoundingClientRect();
    const text = (el.innerText || el.value || el.getAttribute('aria-label') ||
                  el.getAttribute('title') || '').replace(/\s+/g, ' ').trim();
    return {
      index,
      text,
      tag: (el.tagName || '').toLowerCase(),
      id: el.id || '',
      name: el.getAttribute('name') || '',
      role: el.getAttribute('role') || '',
      href: el.getAttribute('href') || '',
      selector: cssPath(el),
      visible: rect.width > 0 && rect.height > 0,
      x: Math.round(rect.left + rect.width / 2),
      y: Math.round(rect.top + rect.height / 2)
    };
  }).filter(x => x.visible || x.text || x.href);
})()
"""


def execute(action: str, options: Optional[dict] = None) -> dict:
    """Run a browser action through local Chrome CDP.

    All failures are returned as ok=False so app automation never crashes the
    caller when Chrome is absent or mid-action CDP behavior differs by version.
    """
    opts = options or {}
    try:
        if action == "list_tabs":
            return {"ok": True, "action": action, "data": {"tabs": _list_pages()}, "error": ""}
        if action == "new_tab":
            url = str(opts.get("url") or "about:blank")
            return {"ok": True, "action": action, "data": _new_tab(url), "error": ""}
        if action == "select_tab":
            return {"ok": True, "action": action, "data": _select_tab(opts), "error": ""}
        if action not in ACTIONS:
            return {
                "ok": False,
                "action": action,
                "data": {"available_actions": list(ACTIONS)},
                "error": f"unsupported browser action: {action}",
            }
        with _connect(opts) as cdp:
            data = _run_action(cdp, action, opts)
            return {"ok": True, "action": action, "data": data, "error": ""}
    except Exception as exc:  # noqa: BLE001
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


def _remember_tab(tab: Optional[dict]) -> None:
    global _ACTIVE_TAB_ID
    if isinstance(tab, dict) and tab.get("id"):
        _ACTIVE_TAB_ID = str(tab["id"])


def _connect(options: dict) -> _CdpClient:
    tabs = _json_get("/json")
    if not isinstance(tabs, list):
        raise RuntimeError("Chrome CDP tab list response was not a list")
    want = options.get("tab")
    if want not in (None, ""):
        picked = _pick_matching_tab(tabs, want)
        if picked is None:
            raise RuntimeError(f"열린 탭에서 '{want}' 을 찾지 못했습니다 — list_tabs로 확인하세요")
        _remember_tab(picked)
        return _CdpClient(picked["webSocketDebuggerUrl"], timeout=float(options.get("timeout", 5)))
    tab = None
    if _ACTIVE_TAB_ID:  # 직전에 쓰던 탭이 아직 열려 있으면 그 탭으로 (호출 간 일관성)
        tab = next((t for t in tabs if t.get("id") == _ACTIVE_TAB_ID
                    and t.get("type") == "page" and t.get("webSocketDebuggerUrl")), None)
    if tab is None:
        tab = _pick_tab(tabs)
    if tab is None:
        tab = _new_tab()
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        raise RuntimeError("Chrome CDP tab has no webSocketDebuggerUrl")
    _remember_tab(tab)
    return _CdpClient(ws_url, timeout=float(options.get("timeout", 5)))


def _list_pages() -> list[dict]:
    tabs = _json_get("/json")
    if not isinstance(tabs, list):
        raise RuntimeError("Chrome CDP tab list response was not a list")
    pages = []
    for i, tab in enumerate(t for t in tabs if t.get("type") == "page"):
        pages.append({
            "index": i,
            "id": tab.get("id", ""),
            "title": tab.get("title", ""),
            "url": tab.get("url", ""),
        })
    return pages


def _pick_matching_tab(tabs: list[dict], want: object) -> Optional[dict]:
    pages = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    try:
        return pages[int(want)]
    except (ValueError, TypeError, IndexError):
        needle = str(want).lower()
        for tab in pages:
            if needle in str(tab.get("url", "")).lower() or needle in str(tab.get("title", "")).lower():
                return tab
    return None


def _pick_tab(tabs: list[dict]) -> Optional[dict]:
    for tab in tabs:
        if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
            return tab
    return None


def _new_tab(url: str = "about:blank") -> dict:
    encoded = urllib.parse.quote(url, safe="")
    try:
        tab = _json_get(f"/json/new?{encoded}", method="PUT")
    except Exception:
        tab = _json_get(f"/json/new?{encoded}")
    _remember_tab(tab)
    return tab


def _select_tab(options: dict) -> dict:
    tabs = _json_get("/json")
    if not isinstance(tabs, list):
        raise RuntimeError("Chrome CDP tab list response was not a list")
    want = options.get("tab", options.get("index", options.get("target")))
    if want in (None, ""):
        raise ValueError("select_tab requires tab/index/target")
    picked = _pick_matching_tab(tabs, want)
    if picked is None:
        raise RuntimeError(f"열린 탭에서 '{want}' 을 찾지 못했습니다 — list_tabs로 확인하세요")
    tab_id = picked.get("id")
    if not tab_id:
        raise RuntimeError("Chrome CDP tab has no id")
    _json_get("/json/activate/" + urllib.parse.quote(str(tab_id), safe=""))
    _remember_tab(picked)
    return {"selected": {"id": tab_id, "title": picked.get("title", ""), "url": picked.get("url", "")}}


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
        # SPA는 readyState 이후에 JS가 그린다 — 본문 텍스트가 생길 때까지 잠깐 대기.
        rendered = _wait_rendered(cdp, float(options.get("render_timeout", 3)))
        return {"url": url, "status": "loaded", "rendered": rendered}
    if action == "get_title":
        title = _eval(cdp, "document.title")
        return {"title": title or ""}
    if action == "extract_text":
        max_length = int(options.get("max_length", 4000))
        text = _extract_text(cdp)
        return {"text": text[:max_length], "truncated": len(text) > max_length, "length": len(text)}
    if action == "snapshot":
        return _snapshot(cdp, options)
    if action == "find_clickables":
        return _find_clickables(cdp, options)
    if action == "click":
        return _click(cdp, options)
    if action == "fill":
        return _fill(cdp, options)
    if action == "screenshot":
        return _screenshot(cdp, options)
    if action == "wait_for_selector":
        return _wait_for_selector(cdp, options)
    if action == "spa_map":
        return _spa_map(cdp, options)
    raise AssertionError(f"unhandled action: {action}")


def _eval(cdp: _CdpClient, expression: str, timeout: Optional[float] = None) -> Any:
    result = cdp.call("Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": True,
    }, timeout=timeout)
    value = result.get("result", {}).get("value")
    if value is None and result.get("exceptionDetails"):
        raise RuntimeError("Runtime.evaluate failed: " + json.dumps(result.get("exceptionDetails"), ensure_ascii=False)[:300])
    return value


JS_RENDERED_TEXT = r"""
(() => {
  const body = document.body;
  if (!body) return '';
  let text = body.innerText || '';
  if (!String(text).trim()) {
    // \ub80c\ub354 \uc804/\uc228\uae40 \uc0c1\ud0dc \ud3f4\ubc31: script/style \uc18c\uc2a4\uac00 \uc0c8\uc9c0 \uc54a\uac8c \uc81c\uac70 \ud6c4 textContent.
    const clone = body.cloneNode(true);
    clone.querySelectorAll('script,style,noscript,template').forEach(n => n.remove());
    text = clone.textContent || '';
  }
  return String(text).replace(/\u00a0/g, ' ').replace(/[ \t]+\n/g, '\n').trim();
})()
"""


def _extract_text(cdp: _CdpClient, wait_seconds: float = 2.0) -> str:
    text = _eval(cdp, JS_RENDERED_TEXT) or ""
    if isinstance(text, str) and text.strip():
        return text
    # SPA\uac00 \uc544\uc9c1 \uc548 \uadf8\ub838\uc744 \uc218 \uc788\ub2e4 \u2014 \ubcf8\ubb38\uc774 \uc0dd\uae38 \ub54c\uae4c\uc9c0 \uc9e7\uac8c \ud3f4\ub9c1 (\ube60\ub978 \ud398\uc774\uc9c0 \ubb34\uc601\ud5a5).
    deadline = time.monotonic() + max(0.0, wait_seconds)
    while time.monotonic() < deadline:
        time.sleep(0.15)
        text = _eval(cdp, JS_RENDERED_TEXT) or ""
        if isinstance(text, str) and text.strip():
            return text
    html_text = _outer_html(cdp)
    return _html_to_text(html_text)


def _wait_rendered(cdp: _CdpClient, timeout: float) -> bool:
    """\ubcf8\ubb38\uc5d0 \ub80c\ub354\ub41c \ud14d\uc2a4\ud2b8\uac00 \ub098\ud0c0\ub0a0 \ub54c\uae4c\uc9c0 \ub300\uae30. \uc2e4\ud328\ud574\ub3c4 \uc608\uc678 \uc5c6\uc774 False."""
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        try:
            text = _eval(cdp, JS_RENDERED_TEXT) or ""
        except Exception:
            text = ""
        if isinstance(text, str) and text.strip():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.15)


def _outer_html(cdp: _CdpClient) -> str:
    try:
        doc = cdp.call("DOM.getDocument", {"depth": -1, "pierce": True})
        node_id = doc.get("root", {}).get("nodeId")
        if node_id:
            result = cdp.call("DOM.getOuterHTML", {"nodeId": node_id}, timeout=10)
            outer = result.get("outerHTML") or ""
            if isinstance(outer, str):
                return outer
    except Exception:
        pass
    outer = _eval(cdp, "document.documentElement ? document.documentElement.outerHTML : ''", timeout=10)
    return outer if isinstance(outer, str) else ""


def _html_to_text(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = re.sub(r"(?is)<(script|style|noscript|template)[^>]*>.*?</\1>", " ", raw_html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h[1-6]|section|article|header|footer|nav)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _snapshot(cdp: _CdpClient, options: dict) -> dict:
    max_text = int(options.get("max_text_length", options.get("max_length", 8000)))
    max_html = int(options.get("max_html_length", 0))
    title = _eval(cdp, "document.title") or ""
    url = _eval(cdp, "location.href") or ""
    ready_state = _eval(cdp, "document.readyState") or ""
    text = _extract_text(cdp)
    data: Dict[str, Any] = {
        "title": title,
        "url": url,
        "ready_state": ready_state,
        "text": text[:max_text],
        "text_length": len(text),
        "text_truncated": len(text) > max_text,
    }
    if max_html > 0:
        outer = _outer_html(cdp)
        data.update({"html": outer[:max_html], "html_length": len(outer), "html_truncated": len(outer) > max_html})
    if options.get("include_clickables", True):
        data["clickables"] = _find_clickables(cdp, {"limit": int(options.get("clickable_limit", 80))}).get("clickables", [])
    return data


def _find_clickables(cdp: _CdpClient, options: dict) -> dict:
    limit = int(options.get("limit", 100))
    items = _eval(cdp, JS_CLICKABLES, timeout=float(options.get("timeout", 10))) or []
    if not isinstance(items, list):
        items = []
    return {"clickables": items[:limit], "count": len(items), "truncated": len(items) > limit}


def _click(cdp: _CdpClient, options: dict) -> dict:
    selector = options.get("selector")
    text = options.get("text")
    index = options.get("index")
    if selector in (None, "") and text in (None, "") and index in (None, ""):
        raise ValueError("click requires selector, text, or index")
    payload = json.dumps({"selector": selector, "text": text, "index": index}, ensure_ascii=False)
    expr = r"""
((payload) => {
  const args = JSON.parse(payload);
  const clickableSelector = [
    'a[href]', 'button', 'input[type=button]', 'input[type=submit]',
    '[role=button]', '[role=link]', '[onclick]', '[tabindex]'
  ].join(',');
  const list = Array.from(document.querySelectorAll(clickableSelector));
  let el = null;
  if (args.selector) el = document.querySelector(args.selector);
  if (!el && args.index !== null && args.index !== undefined && args.index !== '') el = list[Number(args.index)];
  if (!el && args.text) {
    const needle = String(args.text).toLowerCase();
    el = list.find(x => ((x.innerText || x.value || x.getAttribute('aria-label') || x.getAttribute('title') || '')
      .replace(/\s+/g, ' ').trim().toLowerCase()).includes(needle));
  }
  if (!el) return {ok: false, error: 'element not found'};
  const before = location.href;
  el.scrollIntoView({block: 'center', inline: 'center'});
  const label = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || '').replace(/\s+/g, ' ').trim();
  el.click();
  return {ok: true, text: label, tag: (el.tagName || '').toLowerCase(), before_url: before, after_url: location.href};
})('PAYLOAD')
""".replace("'PAYLOAD'", json.dumps(payload, ensure_ascii=False))
    result = _eval(cdp, expr, timeout=float(options.get("timeout", 10)))
    if not isinstance(result, dict) or not result.get("ok"):
        raise RuntimeError(str((result or {}).get("error", "element click failed")))
    if options.get("wait_after", True):
        time.sleep(float(options.get("wait_seconds", 0.5)))
    return result


def _fill(cdp: _CdpClient, options: dict) -> dict:
    """입력창 채우기 — 포털 검색창/로그인 폼 탐색용. React 등 프레임워크 호환
    (네이티브 value setter + input/change 이벤트). enter=True 면 Enter 전송."""
    selector = options.get("selector")
    text = options.get("text")  # placeholder/label/name 부분일치로 입력창 찾기
    value = options.get("value")
    if value is None:
        raise ValueError("fill requires value")
    if selector in (None, "") and text in (None, ""):
        raise ValueError("fill requires selector or text")
    payload = json.dumps({"selector": selector, "text": text, "value": str(value),
                          "enter": bool(options.get("enter"))}, ensure_ascii=False)
    expr = r"""
((payload) => {
  const args = JSON.parse(payload);
  let el = null;
  if (args.selector) el = document.querySelector(args.selector);
  if (!el && args.text) {
    const needle = String(args.text).toLowerCase();
    const fields = Array.from(document.querySelectorAll('input, textarea, select, [contenteditable]'));
    el = fields.find(x => ((x.placeholder || '') + ' ' + (x.name || '') + ' ' +
      (x.getAttribute('aria-label') || '') + ' ' + (x.id || '') + ' ' +
      ((x.labels && x.labels[0]) ? x.labels[0].innerText : '')).toLowerCase().includes(needle));
  }
  if (!el) return {ok: false, error: 'input element not found'};
  el.focus();
  if (el.isContentEditable) {
    el.innerText = args.value;
  } else {
    const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype
                : el.tagName === 'SELECT' ? window.HTMLSelectElement.prototype
                : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value');
    if (setter && setter.set) setter.set.call(el, args.value); else el.value = args.value;
  }
  el.dispatchEvent(new Event('input', {bubbles: true}));
  el.dispatchEvent(new Event('change', {bubbles: true}));
  if (args.enter) {
    for (const type of ['keydown', 'keypress', 'keyup']) {
      el.dispatchEvent(new KeyboardEvent(type, {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    }
    if (el.form && typeof el.form.requestSubmit === 'function') el.form.requestSubmit();
  }
  return {ok: true, tag: (el.tagName || '').toLowerCase(), id: el.id || '',
          name: el.getAttribute('name') || '', value_length: String(args.value).length};
})('PAYLOAD')
""".replace("'PAYLOAD'", json.dumps(payload, ensure_ascii=False))
    result = _eval(cdp, expr, timeout=float(options.get("timeout", 10)))
    if not isinstance(result, dict) or not result.get("ok"):
        raise RuntimeError(str((result or {}).get("error", "fill failed")))
    if options.get("enter") and options.get("wait_after", True):
        time.sleep(float(options.get("wait_seconds", 0.5)))
    return result


def _screenshot(cdp: _CdpClient, options: dict) -> dict:
    out_path = _screenshot_path(options.get("filename"))
    _capture_screenshot(cdp, out_path, options)
    return {"path": str(out_path)}


def _capture_screenshot(cdp: _CdpClient, out_path: Path, options: dict) -> None:
    cdp.call("Page.enable")
    params = {"format": "png", "captureBeyondViewport": bool(options.get("captureBeyondViewport", True))}
    result = cdp.call("Page.captureScreenshot", params, timeout=float(options.get("timeout", 10)))
    data = result.get("data")
    if not isinstance(data, str) or not data:
        raise RuntimeError("CDP screenshot returned no image data")
    _ensure_dir(out_path.parent)
    out_path.write_bytes(base64.b64decode(data))


def _spa_map(cdp: _CdpClient, options: dict) -> dict:
    out_dir = Path(str(options.get("output_dir") or (RESULTS / "site_maps")))
    _ensure_dir(out_dir)
    shots_dir = out_dir / "screenshots"
    _ensure_dir(shots_dir)
    stamp = now().replace(":", "").replace("-", "").replace("T", "_").replace("+", "_")
    max_clicks = int(options.get("max_clicks", 20))
    wait_seconds = float(options.get("wait_seconds", 0.7))

    root_snapshot = _snapshot(cdp, {"max_text_length": int(options.get("max_text_length", 4000)),
                                   "clickable_limit": max_clicks,
                                   "include_clickables": True})
    first_shot = shots_dir / f"{stamp}_00_initial.png"
    try:
        _capture_screenshot(cdp, first_shot, options)
    except Exception as exc:  # noqa: BLE001
        first_shot = Path(str(exc))

    root_url = str(root_snapshot.get("url") or "")
    clickables = list(root_snapshot.get("clickables") or [])[:max_clicks]
    pages = []
    for i, item in enumerate(clickables, start=1):
        selector = item.get("selector") or ""
        label = str(item.get("text") or item.get("href") or item.get("tag") or f"item_{i}")[:80]
        entry: Dict[str, Any] = {"index": item.get("index", i - 1), "label": label, "selector": selector}
        if not selector:
            entry.update({"ok": False, "error": "missing selector"})
            pages.append(entry)
            continue
        try:
            # 이전 클릭이 다른 페이지로 이동시켰다면 루트로 복귀 — 루트 페이지의
            # 셀렉터 목록이 계속 유효하도록 (SPA 해시 이동은 그대로 둔다).
            current = _eval(cdp, "location.href") or ""
            if root_url and str(current).split("#", 1)[0] != root_url.split("#", 1)[0]:
                cdp.call("Page.navigate", {"url": root_url})
                _wait_ready(cdp, 10)
                _wait_rendered(cdp, 3)
            clicked = _click(cdp, {"selector": selector, "wait_after": False})
            time.sleep(wait_seconds)
            snap = _snapshot(cdp, {"max_text_length": int(options.get("max_text_length", 3000)),
                                   "clickable_limit": 30,
                                   "include_clickables": True})
            shot_name = f"{stamp}_{i:02d}_{_safe_slug(label)}.png"
            shot_path = shots_dir / shot_name
            try:
                _capture_screenshot(cdp, shot_path, options)
                screenshot_value = str(shot_path)
            except Exception as exc:  # noqa: BLE001
                screenshot_value = "screenshot failed: " + str(exc)
            entry.update({
                "ok": True,
                "clicked": clicked,
                "title": snap.get("title", ""),
                "url": snap.get("url", ""),
                "text_sample": str(snap.get("text", ""))[:1000],
                "clickable_count": len(snap.get("clickables") or []),
                "screenshot": screenshot_value,
            })
        except Exception as exc:  # noqa: BLE001
            entry.update({"ok": False, "error": str(exc)})
        pages.append(entry)
        if isinstance(cdp.ws, WsClient) and cdp.ws.closed:
            # 수신 타임아웃 등으로 연결이 죽으면 이후 항목도 전부 실패한다 — 중단.
            break

    result = {
        "created_at": now(),
        "root": root_snapshot,
        "initial_screenshot": str(first_shot),
        "pages": pages,
    }
    json_path = out_dir / f"site_map_{stamp}.json"
    md_path = out_dir / f"site_map_{stamp}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_lines = ["# Browser SPA map", "", f"- Title: {root_snapshot.get('title', '')}",
                f"- URL: {root_snapshot.get('url', '')}", f"- Clickables: {len(clickables)}", ""]
    for page in pages:
        status = "OK" if page.get("ok") else "FAIL"
        md_lines.append(f"## {status} {page.get('index')}: {page.get('label', '')}")
        md_lines.append(f"- Selector: `{page.get('selector', '')}`")
        if page.get("url"):
            md_lines.append(f"- URL: {page.get('url')}")
        if page.get("screenshot"):
            md_lines.append(f"- Screenshot: {page.get('screenshot')}")
        if page.get("error"):
            md_lines.append(f"- Error: {page.get('error')}")
        md_lines.append("")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path), "initial_screenshot": result["initial_screenshot"],
            "pages": pages, "count": len(pages)}


def _wait_for_selector(cdp: _CdpClient, options: dict) -> dict:
    selector = options.get("selector")
    text = options.get("text")
    if selector in (None, "") and text in (None, ""):
        raise ValueError("wait_for_selector requires selector or text")
    timeout = float(options.get("timeout", 10))
    deadline = time.monotonic() + timeout
    payload = json.dumps({"selector": selector, "text": text}, ensure_ascii=False)
    expr = r"""
((payload) => {
  const args = JSON.parse(payload);
  if (args.selector && document.querySelector(args.selector)) return true;
  if (args.text) return (document.body ? document.body.innerText : '').includes(args.text);
  return false;
})('PAYLOAD')
""".replace("'PAYLOAD'", json.dumps(payload, ensure_ascii=False))
    while True:
        if _eval(cdp, expr):
            return {"found": True, "selector": selector or "", "text": text or ""}
        if time.monotonic() >= deadline:
            raise TimeoutError(f"wait_for_selector timed out: {selector or text}")
        time.sleep(float(options.get("poll_seconds", 0.2)))


def _wait_ready(cdp: _CdpClient, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            state = _eval(cdp, "document.readyState")
        except Exception:
            # 내비게이션 직후 Runtime.evaluate 는 'Execution context was destroyed'
            # 오류를 흔히 낸다 — 정상 로딩 중이므로 deadline 까지 재시도(_wait_rendered 와 동일).
            state = None
        if state in ("interactive", "complete"):
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("page load timed out")
        time.sleep(0.2)


def _ensure_dir(path: Path) -> None:
    # 동명 파일을 삭제하면 사용자가 output_dir 를 오지정했을 때 데이터가 파괴된다.
    # 삭제 대신 명확한 오류를 던진다(execute 의 상위 가드가 ok=False 로 변환).
    if path.exists() and not path.is_dir():
        raise NotADirectoryError(f"디렉터리를 만들 수 없음 — 같은 경로에 파일이 있음: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _screenshot_path(filename: object) -> Path:
    screenshots = RESULTS / "browser_screenshots"
    _ensure_dir(screenshots)
    name = str(filename or f"browser_{now().replace(':', '').replace('-', '').replace('T', '_')}.png")
    if not name.lower().endswith(".png"):
        name += ".png"
    return screenshots / _safe_ascii_filename(Path(name).name)


def _safe_slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name).strip("._")
    return (ascii_name or "item")[:80]


def _safe_ascii_filename(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name).strip("._")
    if not ascii_name:
        ascii_name = "browser_screenshot.png"
    if not ascii_name.lower().endswith(".png"):
        ascii_name += ".png"
    return ascii_name[:120]


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, (ConnectionRefusedError, urllib.error.URLError, TimeoutError, WsTimeout)):
        return f"{CHROME_GUIDE} ({exc})"
    text = str(exc) or repr(exc)
    if "WinError 10061" in text or "Connection refused" in text:
        return f"{CHROME_GUIDE} ({text})"
    return text
