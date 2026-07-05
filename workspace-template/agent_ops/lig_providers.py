# -*- coding: utf-8 -*-
"""LIG provider config loading, validation, and fallback policy.

Secrets stay local-only in %USERPROFILE%\\OpenCodeLIG_USERDATA\\secrets\\lig-api.env
(template: config/lig-api.env.example). This module never returns or logs the
API key or gateway host in validation/diagnostic output — only presence flags.

Provider intent:
  lig-coding   default coding / file / terminal work (EXAONE-4.5-33B)
  lig-chat     analysis / document / translation      (EXAONE-4.5-33B)
  lig-fallback coding fallback when EXAONE unsuitable (Qwen3.6-27B)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

SECRET_ENV_PATH = Path(os.environ.get("LIG_API_ENV_FILE") or (Path.home() / "OpenCodeLIG_USERDATA" / "secrets" / "lig-api.env"))
DIAG_DIR = Path(os.environ.get("LIG_DIAG_DIR") or (Path.home() / "OpenCodeLIG_USERDATA" / "diagnostics"))

# 실측(2026-07-03): 라우트에는 "/gateway/" 접두가 필요하다 — 없으면 리버스 프록시가
# 백엔드로 넘기지 않고 80포트 웹서버가 404를 반환한다 (probe/results/ 2차 실측 +
# 옛 저장 설정 실증). default_think_off 형태가 원본 실증이며, vibe_coding/Qwen 라우트
# 존재 여부는 회사 재실측으로 확인한다 (다르면 lig-api.env에서 오버라이드).
_ROUTE_DEFAULTS = {
    "lig-coding": ("LIG_ROUTE_CODING", "/gateway/EXAONE-4.5-33B-vibe_coding_think_off/v1", "LIG_MODEL_CODING", "EXAONE-4.5-33B"),
    "lig-chat": ("LIG_ROUTE_CHAT", "/gateway/EXAONE-4.5-33B-default_think_off/v1", "LIG_MODEL_CHAT", "EXAONE-4.5-33B"),
    "lig-fallback": ("LIG_ROUTE_FALLBACK", "/gateway/Qwen3.6-27B-vibe_coding_think_off/v1", "LIG_MODEL_FALLBACK", "Qwen3.6-27B"),
}

_PLACEHOLDER_MARKERS = ("REPLACE_WITH", "PUT_INTERNAL", "CHANGEME")
_VALID_PROFILES = ("company_gateway", "local_openai")
_SHELL_OVERRIDE_KEYS = ("LIG_PROVIDER_PROFILE", "LIG_LOCAL_BASE_URL", "LIG_LOCAL_MODEL")
_ROUTE_CAPABILITY_MAP = {
    "lig-coding": {
        "macro_generation",
        "office_cad_automation",
        "browser_automation",
        "file_ops",
        "spreadsheet_generation",
    },
    "lig-chat": {
        "document_generation",
        "presentation_generation",
        "web_mail_assistant",
        "meeting_minutes",
        "mail_report",
    },
}


def load_lig_env(path: Optional[Path] = None) -> Dict[str, str]:
    """Parse KEY=VALUE env file. Tolerates BOM, blank lines, # comments."""
    path = path or SECRET_ENV_PATH
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def _is_real(value: str) -> bool:
    return bool(value) and not any(m in value for m in _PLACEHOLDER_MARKERS)


def _with_shell_overrides(env: Dict[str, str]) -> Dict[str, str]:
    values = dict(env)
    for key in _SHELL_OVERRIDE_KEYS:
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def get_profile(env: Optional[Dict[str, str]] = None) -> str:
    """Return the selected provider profile, falling back safely on typos."""
    env = env if env is not None else load_lig_env()
    env = _with_shell_overrides(env)
    profile = (env.get("LIG_PROVIDER_PROFILE") or "company_gateway").strip()
    return profile if profile in _VALID_PROFILES else "company_gateway"


def route_reason(capability_ids: list) -> str:
    caps = [str(c) for c in (capability_ids or [])]
    for route, known in _ROUTE_CAPABILITY_MAP.items():
        for cap_id in caps:
            if cap_id in known:
                return cap_id
    return "default"


def select_route(capability_ids: list) -> str:
    """Map planned capability ids to the provider route used for the first call."""
    reason = route_reason(capability_ids)
    if reason == "default":
        return "lig-coding"
    for route, known in _ROUTE_CAPABILITY_MAP.items():
        if reason in known:
            return route
    return "lig-coding"


def build_providers(env: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, str]]:
    """Build the three provider routes. base_url may contain the internal host
    — treat returned dict as sensitive; do not print it."""
    env = env if env is not None else load_lig_env()
    env = _with_shell_overrides(env)
    profile = get_profile(env)
    providers: Dict[str, Dict[str, str]] = {}
    if profile == "local_openai":
        base_url = env.get("LIG_LOCAL_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
        model = env.get("LIG_LOCAL_MODEL", "qwen2.5:7b-instruct")
        for name in _ROUTE_DEFAULTS:
            providers[name] = {
                "base_url": base_url,
                "model": model,
                "timeout": env.get("LIG_API_TIMEOUT_SEC", "120"),
            }
        return providers

    gateway = env.get("LIG_GATEWAY_BASE_URL", "").rstrip("/")
    for name, (route_key, route_default, model_key, model_default) in _ROUTE_DEFAULTS.items():
        route = env.get(route_key, route_default)
        providers[name] = {
            "base_url": gateway + route if gateway else "",
            "model": env.get(model_key, model_default),
            "timeout": env.get("LIG_API_TIMEOUT_SEC", "120"),
        }
    return providers


def validate_config(env: Optional[Dict[str, str]] = None, path: Optional[Path] = None) -> Dict[str, Any]:
    """Presence/shape validation only — safe to print and to write to diagnostics."""
    src = path or SECRET_ENV_PATH
    env = env if env is not None else load_lig_env(src)
    env = _with_shell_overrides(env)
    raw_profile = (env.get("LIG_PROVIDER_PROFILE") or "company_gateway").strip()
    profile = get_profile(env)
    providers = build_providers(env)
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "profile": profile,
        "secret_file_found": src.exists(),
        "gateway_url_set": _is_real(env.get("LIG_GATEWAY_BASE_URL", "")),
        "api_key_set": _is_real(env.get("LIG_API_KEY", "")),
        "default_provider": env.get("LIG_DEFAULT_PROVIDER", "lig-coding"),
        "providers": {name: {"route_set": bool(p["base_url"]), "model": p["model"]} for name, p in providers.items()},
    }
    if raw_profile and raw_profile not in _VALID_PROFILES:
        report["profile_warning"] = "알 수 없는 프로필입니다. company_gateway를 사용합니다."
    if profile == "local_openai":
        report["ready"] = all(_is_real(p["base_url"]) and _is_real(p["model"]) for p in providers.values())
    else:
        report["ready"] = bool(report["secret_file_found"] and report["gateway_url_set"] and report["api_key_set"])
    missing = []
    if profile == "company_gateway":
        if not report["secret_file_found"]:
            missing.append(f"secret file not found: {src}")
        if not report["gateway_url_set"]:
            missing.append("LIG_GATEWAY_BASE_URL missing or placeholder")
        if not report["api_key_set"]:
            missing.append("LIG_API_KEY missing or placeholder")
    else:
        if not report["ready"]:
            missing.append("LIG_LOCAL_BASE_URL or LIG_LOCAL_MODEL missing or placeholder")
    report["missing"] = missing
    return report


# --- Fallback policy -------------------------------------------------------
# action values:
#   retry           retry same provider (bounded by max_retries)
#   simplify_retry  retry same provider with tighter/simpler instruction
#   switch_fallback switch provider to lig-fallback
#   local_fallback  abandon native tool call, use safe local file operation
#   stop            stop with precise diagnostic
FALLBACK_POLICY: Dict[str, Dict[str, Any]] = {
    "http_timeout": {"action": "retry", "max_retries": 1, "then": "switch_fallback"},
    "http_4xx": {"action": "stop", "max_retries": 0, "then": "stop"},  # auth/route error: retry won't help
    "http_5xx": {"action": "retry", "max_retries": 1, "then": "switch_fallback"},
    "provider_unreachable": {"action": "switch_fallback", "max_retries": 0, "then": "stop"},
    "empty_response": {"action": "retry", "max_retries": 1, "then": "switch_fallback"},
    "malformed_tool_call": {"action": "simplify_retry", "max_retries": 2, "then": "local_fallback"},
    "repeated_parse_failure": {"action": "switch_fallback", "max_retries": 0, "then": "local_fallback"},
    "unavailable_tool_repeat": {"action": "simplify_retry", "max_retries": 1, "then": "local_fallback"},
    "repeated_tool_failure": {"action": "simplify_retry", "max_retries": 1, "then": "switch_fallback"},
    "context_length": {"action": "simplify_retry", "max_retries": 1, "then": "stop"},
    "model_refusal": {"action": "simplify_retry", "max_retries": 1, "then": "switch_fallback"},
    "text_instead_of_tool_call": {"action": "simplify_retry", "max_retries": 2, "then": "local_fallback"},
}


def decide_fallback(trigger: str, attempt: int, provider: str) -> Dict[str, Any]:
    """Return the next action for a failure trigger at a given attempt count."""
    policy = FALLBACK_POLICY.get(trigger, {"action": "stop", "max_retries": 0, "then": "stop"})
    # retry-type actions are bounded by max_retries; non-retry actions apply
    # on the first occurrence and escalate to "then" afterwards.
    if policy["action"] in ("retry", "simplify_retry"):
        action = policy["action"] if attempt <= policy["max_retries"] else policy["then"]
    else:
        action = policy["action"] if attempt <= 1 else policy["then"]
    if action == "switch_fallback" and provider == "lig-fallback":
        action = "local_fallback"  # already on last provider; don't loop
    return {"trigger": trigger, "attempt": attempt, "provider": provider, "action": action, "known_trigger": trigger in FALLBACK_POLICY}


def record_fallback(provider_initial: str, provider_final: str, trigger: str, attempts: int, result: str, diag_dir: Optional[Path] = None) -> Path:
    """Write the fallback decision trail (safe fields only) for diagnostics."""
    diag = diag_dir or DIAG_DIR
    diag.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "provider_initial": provider_initial,
        "provider_final": provider_final,
        "fallback_trigger": trigger,
        "fallback_attempts": attempts,
        "fallback_result": result,
    }
    last = diag / "provider-fallback-last.json"
    last.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    with (diag / "provider-fallback-history.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return last


if __name__ == "__main__":
    print(json.dumps(validate_config(), ensure_ascii=False, indent=2))
