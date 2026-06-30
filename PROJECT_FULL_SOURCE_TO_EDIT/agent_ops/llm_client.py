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
    return bool(cfg["base_url"] and cfg["api_key"] and cfg["model"])

def chat(messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
    cfg = load_llm_config()
    if not is_configured():
        raise RuntimeError("LLM not configured: set AGENTOPS_LLM_BASE_URL/API_KEY/MODEL or agent_ops/config/llm_config.json")
    url = cfg["base_url"].rstrip("/")
    if not url.endswith("/chat/completions"):
        url = url + "/chat/completions"
    payload = {"model": cfg["model"], "messages": messages, "temperature": temperature}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + cfg["api_key"],
    }, method="POST")
    with urllib.request.urlopen(req, timeout=cfg["timeout"]) as r:
        body = r.read().decode("utf-8", errors="replace")
    obj = json.loads(body)
    return obj["choices"][0]["message"]["content"]
