# -*- coding: utf-8 -*-
"""Resilient LLM call loop for LIG providers.

This is the runtime integration point that ties together:
  lig_providers   route config + fallback policy (decide_fallback)
  toolcall_parser malformed tool-call detection/repair

The transport is injectable so every fallback path is testable offline with
mocks. Real company gateway calls remain company-validation-pending.

Diagnostics (secret-safe: gateway host and api key are redacted) go to
%USERPROFILE%\\OpenCodeLIG_USERDATA\\diagnostics\\runtime-last.json plus the
provider-fallback records written by lig_providers.record_fallback.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .lig_providers import DIAG_DIR, build_providers, decide_fallback, get_profile, load_lig_env, record_fallback, route_reason, select_route
from .toolcall_parser import parse_tool_calls

Transport = Callable[[str, Dict[str, Any], Dict[str, str], int], Dict[str, Any]]

SIMPLIFY_INSTRUCTION = (
    "IMPORTANT: Your previous reply could not be parsed. "
    'Respond with ONLY one JSON object, no prose, no code fences: '
    '{"name": "<tool_name>", "arguments": { ... }}'
)


class TransportError(Exception):
    """Raised by transports; trigger must be a FALLBACK_POLICY key."""

    def __init__(self, trigger: str, detail: str = ""):
        super().__init__(detail or trigger)
        self.trigger = trigger


def _chat_completions_url(url: str) -> str:
    """Normalize OpenAI-compatible base URLs to chat completions endpoint."""
    base = str(url or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def default_transport(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: int) -> Dict[str, Any]:
    req = urllib.request.Request(_chat_completions_url(url), data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        trigger = "http_4xx" if 400 <= exc.code < 500 else "http_5xx"
        raise TransportError(trigger, f"HTTP {exc.code}")
    except TimeoutError:
        raise TransportError("http_timeout", "timeout")
    except urllib.error.URLError as exc:
        if isinstance(getattr(exc, "reason", None), TimeoutError) or "timed out" in str(exc.reason).lower():
            raise TransportError("http_timeout", "timeout")
        raise TransportError("provider_unreachable", str(exc.reason)[:120])
    except OSError as exc:
        raise TransportError("provider_unreachable", repr(exc)[:120])
    try:
        return json.loads(body)
    except Exception:
        return {"choices": [{"message": {"content": body}}]}


def _redact(text: str, env: Dict[str, str]) -> str:
    for key in ("LIG_GATEWAY_BASE_URL", "LIG_API_KEY"):
        val = env.get(key, "")
        if val and len(val) > 4:
            text = text.replace(val, f"<{key}>")
    return text


def call_llm(
    messages: List[Dict[str, str]],
    tools: Optional[List[Dict[str, Any]]] = None,
    provider: str = "",
    require_tool_call: bool = False,
    env: Optional[Dict[str, str]] = None,
    transport: Optional[Transport] = None,
    max_steps: int = 8,
    diag_dir: Optional[Path] = None,
    capability_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Call the LIG gateway with retry / simplify / provider-fallback handling.

    Returns a dict with: ok, outcome (ok|local_fallback|stop), content,
    tool_calls, parse_status, provider_initial, provider_final,
    fallback_trigger, attempts, trail.
    """
    env = env if env is not None else load_lig_env()
    transport = transport or default_transport
    providers = build_providers(env)
    if provider:
        selected = provider
        reason = "explicit_provider"
    elif capability_ids is not None:
        selected = select_route(capability_ids)
        reason = route_reason(capability_ids)
    else:
        selected = env.get("LIG_DEFAULT_PROVIDER", "lig-coding")
        reason = "env_default"
    current = selected or env.get("LIG_DEFAULT_PROVIDER", "lig-coding")
    if current not in providers:
        current = "lig-coding"
        selected = "lig-coding"
        reason = "default"
    initial = current

    available_tool_names = [t.get("function", {}).get("name") or t.get("name", "") for t in (tools or [])]
    attempts: Dict[str, int] = {}
    trail: List[Dict[str, Any]] = []
    simplified = False
    outcome, last_trigger, parse = "stop", "", {}
    content = ""

    for _ in range(max_steps):
        cfg = providers[current]
        msgs = list(messages)
        if simplified:
            msgs = msgs + [{"role": "system", "content": SIMPLIFY_INSTRUCTION}]
        payload: Dict[str, Any] = {"model": cfg["model"], "messages": msgs, "temperature": 0.2}
        if tools:
            payload["tools"] = tools
        headers = {"Content-Type": "application/json"}
        if env.get("LIG_API_KEY"):
            headers["Authorization"] = "Bearer " + env["LIG_API_KEY"]

        trigger = ""
        try:
            response = transport(cfg["base_url"], payload, headers, int(cfg.get("timeout") or 120))
            parse = parse_tool_calls(response, available_tools=available_tool_names or None)
            try:
                msg = (response.get("choices") or [{}])[0].get("message") or {}
                content = msg.get("content") or ""
            except Exception:
                content = parse.get("raw_excerpt", "")
            status = parse["parse_status"]
            if status == "failed":
                trigger = "malformed_tool_call"
            elif status == "none" and require_tool_call:
                trigger = "text_instead_of_tool_call" if content.strip() else "empty_response"
            elif parse["unavailable_tools"]:
                trigger = "unavailable_tool_repeat"
            elif status == "none" and not content.strip() and not parse["tool_calls"]:
                trigger = "empty_response"
        except TransportError as exc:
            trigger = exc.trigger
            trail.append({"provider": current, "event": "transport_error", "trigger": trigger, "detail": _redact(str(exc), env)})

        if not trigger:
            outcome = "ok"
            break

        last_trigger = trigger
        attempts[trigger] = attempts.get(trigger, 0) + 1
        decision = decide_fallback(trigger, attempts[trigger], current)
        trail.append({"provider": current, "trigger": trigger, "attempt": attempts[trigger], "action": decision["action"]})
        action = decision["action"]
        if action == "retry":
            continue
        if action == "simplify_retry":
            simplified = True
            continue
        if action == "switch_fallback":
            current = "lig-fallback"
            simplified = False
            continue
        outcome = action  # local_fallback or stop
        break
    else:
        outcome = "stop"
        last_trigger = last_trigger or "max_steps_exceeded"

    tool_call_mode = {"ok": "native", "repaired": "text_fallback"}.get(
        parse.get("parse_status", ""), "none")
    result = {
        "ok": outcome == "ok",
        "outcome": outcome,
        "content": content,
        "tool_calls": parse.get("tool_calls", []),
        "parse_status": parse.get("parse_status", ""),
        "tool_call_mode": tool_call_mode,
        "repaired": parse.get("repaired", False),
        "provider_initial": initial,
        "provider_final": current,
        "route_selected": selected,
        "route_reason": reason,
        "profile": get_profile(env),
        "fallback_trigger": last_trigger,
        "attempts": sum(attempts.values()),
        "trail": trail,
    }
    diag = diag_dir or DIAG_DIR
    try:
        diag.mkdir(parents=True, exist_ok=True)
        safe = dict(result)
        safe["content"] = _redact(str(safe["content"]), env)[:400]
        safe["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        (diag / "runtime-last.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
        if last_trigger:
            record_fallback(initial, current, last_trigger, result["attempts"], outcome, diag_dir=diag)
    except Exception:
        pass  # diagnostics must never break the call path
    return result


def chat_with_fallback(messages: List[Dict[str, str]], **kwargs: Any) -> str:
    """Text-only convenience wrapper. Uses the LIG resilient path when the
    secret env file is configured; otherwise falls back to the legacy
    single-provider client so existing setups keep working."""
    env = load_lig_env()
    if env.get("LIG_GATEWAY_BASE_URL") and env.get("LIG_API_KEY"):
        result = call_llm(messages, env=env, **kwargs)
        if result["ok"]:
            return result["content"]
        raise RuntimeError(f"LLM call failed: outcome={result['outcome']} trigger={result['fallback_trigger']} (see diagnostics/runtime-last.json)")
    from .llm_client import chat  # legacy path
    return chat(messages)
