# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, List

from .core import CONFIG, read_json

def load_llm_config() -> Dict[str, Any]:
    cfg = read_json(CONFIG / "llm_config.json", {})
    if not isinstance(cfg, dict):
        cfg = {}
    return {
        "base_url": os.environ.get("AGENTOPS_LLM_BASE_URL") or cfg.get("base_url", ""),
        "api_key": os.environ.get("AGENTOPS_LLM_API_KEY") or cfg.get("api_key", ""),
        "model": os.environ.get("AGENTOPS_LLM_MODEL") or cfg.get("model", ""),
        "timeout": int(os.environ.get("AGENTOPS_LLM_TIMEOUT") or cfg.get("timeout", 120)),
    }

def is_configured() -> bool:
    cfg = load_llm_config()
    if not cfg["base_url"] or not cfg["model"]:
        return False
    no_auth = os.environ.get("AGENTOPS_LLM_NO_AUTH", "").strip() in {"1", "true", "yes"} \
        or bool(read_json(CONFIG / "llm_config.json", {}).get("no_auth"))
    return bool(cfg["api_key"]) or no_auth

def chat(messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
    cfg = load_llm_config()
    if not is_configured():
        raise RuntimeError("LLM not configured: set AGENTOPS_LLM_BASE_URL/MODEL (+API_KEY or AGENTOPS_LLM_NO_AUTH=1)")
    url = cfg["base_url"].rstrip("/")
    if not url.endswith("/chat/completions"):
        url = url + "/chat/completions"
    payload = {"model": cfg["model"], "messages": messages, "temperature": temperature}
    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = "Bearer " + cfg["api_key"]
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as r:
            body = r.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(f"LLM request failed: {exc!r}")
    try:
        obj = json.loads(body)
    except Exception:
        return body  # some gateways return raw text
    # OpenAI shape
    try:
        choice = obj["choices"][0]
        msg = choice.get("message") or {}
        if isinstance(msg.get("content"), str):
            return msg["content"]
        if isinstance(choice.get("text"), str):  # legacy completion shape
            return choice["text"]
    except Exception:
        pass
    # Other common shapes
    for key in ("content", "output", "response", "text"):
        if isinstance(obj.get(key), str):
            return obj[key]
    return json.dumps(obj, ensure_ascii=False)  # last resort: don't crash
