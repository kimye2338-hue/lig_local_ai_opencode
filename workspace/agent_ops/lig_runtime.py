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
from typing import Any, Callable, Dict, List, Optional, Tuple

from .lig_providers import DIAG_DIR, build_providers, decide_fallback, get_profile, load_lig_env, parse_timeout, record_fallback, route_reason, select_route
from .toolcall_parser import parse_tool_calls, strip_reasoning

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


def _message_content_text(message: Dict[str, Any], fallback: str = "") -> str:
    """Normalize OpenAI-compatible content variants to plain text.

    Some gateways return multipart content lists even for chat completions.
    The tool-call parser already tolerates that shape; the runtime must use
    the same normalization before checking `.strip()` or writing diagnostics.

    reasoning_content 키는 content로 취급하지 않고 무시한다. 최종 텍스트는
    strip_reasoning을 통과시켜 <think> 블록이 답변으로 새지 않게 한다
    (라우트가 think_off라 평상시엔 no-op — 방어용).
    """
    raw = message.get("content")
    if isinstance(raw, str):
        return strip_reasoning(raw)
    if isinstance(raw, list):
        parts: List[str] = []
        for item in raw:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return strip_reasoning("\n".join(parts))
    if raw is None:
        return fallback
    return strip_reasoning(str(raw))


def default_transport(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: int) -> Dict[str, Any]:
    req = urllib.request.Request(_chat_completions_url(url), data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            trigger = "http_429"  # rate limit: 재시도/폴백이 유효
        elif 400 <= exc.code < 500:
            trigger = "http_4xx"
        else:
            trigger = "http_5xx"
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
        # 200 응답이라도 JSON이 아니면(프록시 점검 HTML 페이지 등) 정상 답변으로
        # 승격하지 않고 재시도/폴백 정책을 태운다.
        raise TransportError("invalid_response", body[:120])


def _f(env: Dict[str, str], key: str, default: float) -> float:
    try:
        return float(str(env.get(key)).strip())
    except (TypeError, ValueError):
        return default


def _sampling_params(env: Dict[str, str]) -> Dict[str, Any]:
    """사내 모델(EXAONE-4.5-33B / Qwen3.6-27B) 공식 권장 샘플링. env로 튜닝 가능.

    두 모델 공식 코딩/문서 프리셋이 temperature 0.6 / top_p 0.95 / top_k 20 으로
    수렴한다(모델카드·Qwen docs). 극저온(0.0~0.2)은 thinking 모델에서 반복/루프
    위험이 보고돼 기본을 0.6으로 둔다 — 사내망 실측 후 env로 조정.
    표준 파라미터(temperature/top_p/presence_penalty)만 기본 전송하고, 비표준
    (top_k/enable_thinking)은 게이트웨이 호환 확인 후 env 설정 시에만 보낸다."""
    p: Dict[str, Any] = {
        "temperature": _f(env, "LIG_TEMPERATURE", 0.6),
        "top_p": _f(env, "LIG_TOP_P", 0.95),
    }
    pp = env.get("LIG_PRESENCE_PENALTY")
    if pp not in (None, ""):
        p["presence_penalty"] = _f(env, "LIG_PRESENCE_PENALTY", 0.0)
    # 비표준(vLLM 확장) — 게이트웨이가 받는지 확인 후 env로 opt-in.
    tk = env.get("LIG_TOP_K")
    if tk not in (None, ""):
        try:
            p["top_k"] = int(str(tk).strip())
        except ValueError:
            pass
    think = env.get("LIG_ENABLE_THINKING")
    if think not in (None, ""):
        p["extra_body"] = {"chat_template_kwargs": {"enable_thinking": str(think).strip().lower() in ("1", "true", "on", "yes")}}
    return p


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
    # (provider, trigger)별로 시도 횟수를 센다 — lig-coding → lig-fallback로
    # provider가 바뀌면 새 provider는 같은 trigger에 대해 자신만의 재시도 예산을
    # 다시 얻는다(이전 provider의 소진분이 이월돼 즉시 포기하지 않도록).
    attempts: Dict[Tuple[str, str], int] = {}
    trail: List[Dict[str, Any]] = []
    simplified = False
    outcome, last_trigger, parse = "stop", "", {}
    content = ""
    emergency_local = False

    sampling = _sampling_params(env)
    for _ in range(max_steps):
        cfg = providers[current]
        msgs = list(messages)
        if simplified:
            msgs = msgs + [{"role": "system", "content": SIMPLIFY_INSTRUCTION}]
        payload: Dict[str, Any] = {"model": cfg["model"], "messages": msgs, **sampling}
        if tools:
            payload["tools"] = tools
        headers = {"Content-Type": "application/json"}
        if env.get("LIG_API_KEY"):
            headers["Authorization"] = "Bearer " + env["LIG_API_KEY"]

        trigger = ""
        try:
            response = transport(cfg["base_url"], payload, headers, parse_timeout(cfg.get("timeout")))
            parse = parse_tool_calls(response, available_tools=available_tool_names or None)
            try:
                msg = (response.get("choices") or [{}])[0].get("message") or {}
                content = _message_content_text(msg, parse.get("raw_excerpt", ""))
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
        key = (current, trigger)
        attempts[key] = attempts.get(key, 0) + 1
        attempt_n = attempts[key]
        decision = decide_fallback(trigger, attempt_n, current)
        trail.append({"provider": current, "trigger": trigger, "attempt": attempt_n, "action": decision["action"]})
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

    # 비상 로컬 폴백(옵트인): 사내 게이트웨이가 전부 실패했을 때, LIG_EMERGENCY_LOCAL_BASE_URL
    # 이 설정돼 있으면(예: llamafile/Ollama/LM Studio 로컬 OpenAI 호환) 로컬 모델로 한 번
    # 시도해 비서가 멈추지 않게 한다. env 미설정 시 완전 무동작(기존 동작 유지).
    if outcome != "ok":
        emerg_url = (env.get("LIG_EMERGENCY_LOCAL_BASE_URL") or "").rstrip("/")
        if emerg_url:
            emerg_model = env.get("LIG_EMERGENCY_LOCAL_MODEL") or "qwen2.5:7b-instruct"
            emerg_headers = {"Content-Type": "application/json"}
            if env.get("LIG_EMERGENCY_LOCAL_KEY"):
                emerg_headers["Authorization"] = "Bearer " + env["LIG_EMERGENCY_LOCAL_KEY"]
            try:
                epayload: Dict[str, Any] = {"model": emerg_model, "messages": list(messages),
                                            **sampling}
                if tools:
                    epayload["tools"] = tools
                response = transport(emerg_url, epayload, emerg_headers, 180)
                parse = parse_tool_calls(response, available_tools=available_tool_names or None)
                try:
                    msg = ((response.get("choices") or [{}])[0].get("message") or {})
                    content = _message_content_text(msg, parse.get("raw_excerpt", ""))
                except Exception:
                    content = parse.get("raw_excerpt", "")
                emergency_ok = (
                    parse.get("parse_status") != "failed"
                    and not parse.get("unavailable_tools")
                    and ((bool(parse.get("tool_calls"))) if require_tool_call
                         else (bool(content.strip()) or bool(parse.get("tool_calls"))))
                )
                if emergency_ok:
                    outcome = "ok"
                    emergency_local = True
                    trail.append({"provider": "emergency_local", "event": "used", "model": emerg_model})
                else:
                    trail.append({"provider": "emergency_local", "event": "rejected",
                                  "parse_status": parse.get("parse_status"),
                                  "unavailable_tools": parse.get("unavailable_tools", []),
                                  "require_tool_call": require_tool_call})
            except Exception as exc:  # noqa: BLE001
                trail.append({"provider": "emergency_local", "event": "failed",
                              "detail": _redact(str(exc), env)})

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
        "emergency_local": emergency_local,
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
