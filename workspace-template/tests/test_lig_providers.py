# -*- coding: utf-8 -*-
"""Tests for LIG provider config loading + fallback policy (stdlib only).

Run: py -3.11 tests\\test_lig_providers.py
Uses a temp env file — never touches or prints real secrets.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_ops.lig_providers import build_providers, decide_fallback, load_lig_env, record_fallback, validate_config  # noqa: E402

PASS = 0
ENV_OVERRIDE_KEYS = ("LIG_PROVIDER_PROFILE", "LIG_LOCAL_BASE_URL", "LIG_LOCAL_MODEL")


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    saved_env = {key: os.environ.pop(key, None) for key in ENV_OVERRIDE_KEYS}

    # 1. Missing secret file -> not ready, no crash
    rep = validate_config(path=tmp / "absent.env")
    check("missing file -> not ready", rep["ready"] is False and rep["secret_file_found"] is False, str(rep))

    # 2. Placeholder values -> not ready
    env_file = tmp / "lig-api.env"
    env_file.write_text("LIG_GATEWAY_BASE_URL=http://REPLACE_WITH_INTERNAL_GATEWAY\nLIG_API_KEY=REPLACE_WITH_LOCAL_SECRET_ONLY\n", encoding="utf-8")
    rep = validate_config(path=env_file)
    check("placeholder -> not ready", rep["ready"] is False and rep["gateway_url_set"] is False and rep["api_key_set"] is False, str(rep))

    # 3. Real-looking values (fake) -> ready; report contains no secret value
    secret = "FAKE_DO_NOT_LEAK_12345"
    env_file.write_text(f"# comment\nLIG_GATEWAY_BASE_URL=http://10.0.0.1/gw\nLIG_API_KEY={secret}\nLIG_DEFAULT_PROVIDER=lig-coding\n", encoding="utf-8")
    rep = validate_config(path=env_file)
    check("configured -> ready", rep["ready"] is True, str(rep))
    check("no secret in report", secret not in json.dumps(rep) and "10.0.0.1" not in json.dumps(rep), str(rep))

    # 4. BOM tolerance
    env_file.write_bytes(b"\xef\xbb\xbfLIG_GATEWAY_BASE_URL=http://10.0.0.1/gw\nLIG_API_KEY=abc\n")
    check("BOM tolerated", load_lig_env(env_file)["LIG_GATEWAY_BASE_URL"] == "http://10.0.0.1/gw")

    # 5. Three providers with default routes and models
    provs = build_providers(load_lig_env(env_file))
    check("3 providers", set(provs) == {"lig-coding", "lig-chat", "lig-fallback"}, str(provs.keys()))
    check("fallback is qwen", provs["lig-fallback"]["model"] == "Qwen3.6-27B" and "Qwen3.6-27B-vibe_coding_think_off" in provs["lig-fallback"]["base_url"], str(provs["lig-fallback"]))

    # 6. Route/model env overrides are honored without code changes
    override_env = {
        "LIG_GATEWAY_BASE_URL": "http://10.0.0.2/gw",
        "LIG_ROUTE_CODING": "/custom-coding/v1",
        "LIG_MODEL_CODING": "custom-coding-model",
        "LIG_API_TIMEOUT_SEC": "45",
    }
    provs = build_providers(override_env)
    check("route and model overrides", provs["lig-coding"]["base_url"].endswith("/custom-coding/v1") and provs["lig-coding"]["model"] == "custom-coding-model" and provs["lig-coding"]["timeout"] == "45", str(provs["lig-coding"]))

    # 7. local_openai profile is ready without api_key
    local_env = {"LIG_PROVIDER_PROFILE": "local_openai"}
    rep = validate_config(env=local_env, path=tmp / "missing-local.env")
    check("local_openai ready without secret", rep["ready"] is True and rep["profile"] == "local_openai" and rep["api_key_set"] is False, str(rep))

    # 8. Unknown profile falls back safely and reports a warning
    rep = validate_config(env={"LIG_PROVIDER_PROFILE": "typo_profile"}, path=tmp / "absent.env")
    check("bad profile -> company fallback", rep["profile"] == "company_gateway" and "profile_warning" in rep and rep["ready"] is False, str(rep))

    # 9. Validation report stays secret-free even with local/company hosts configured
    local_env = {"LIG_PROVIDER_PROFILE": "local_openai", "LIG_LOCAL_BASE_URL": "http://127.0.0.1:11434/v1", "LIG_LOCAL_MODEL": "qwen-local"}
    rep = validate_config(env=local_env, path=tmp / "missing-local.env")
    report_text = json.dumps(rep)
    check("validate report omits host strings", "127.0.0.1" not in report_text and "11434" not in report_text and "10.0.0.2" not in report_text, str(rep))

    # 10. Shell env overrides file/local profile keys
    env_file.write_text(
        "LIG_PROVIDER_PROFILE=company_gateway\n"
        "LIG_GATEWAY_BASE_URL=http://10.0.0.3/gw\n"
        "LIG_API_KEY=abc\n",
        encoding="utf-8",
    )
    os.environ["LIG_PROVIDER_PROFILE"] = "local_openai"
    os.environ["LIG_LOCAL_BASE_URL"] = "http://127.0.0.1:9999/v1"
    os.environ["LIG_LOCAL_MODEL"] = "env-local-model"
    rep = validate_config(path=env_file)
    provs = build_providers(load_lig_env(env_file))
    check("shell env overrides file profile", rep["profile"] == "local_openai" and rep["ready"] is True and provs["lig-coding"]["model"] == "env-local-model", str(rep))
    for key in ENV_OVERRIDE_KEYS:
        os.environ.pop(key, None)

    # 11. Fallback policy decisions
    check("timeout first -> retry", decide_fallback("http_timeout", 1, "lig-coding")["action"] == "retry")
    check("timeout exhausted -> switch", decide_fallback("http_timeout", 2, "lig-coding")["action"] == "switch_fallback")
    check("4xx -> stop", decide_fallback("http_4xx", 1, "lig-coding")["action"] == "stop")
    check("malformed -> simplify_retry", decide_fallback("malformed_tool_call", 1, "lig-coding")["action"] == "simplify_retry")
    check("malformed exhausted -> local", decide_fallback("malformed_tool_call", 3, "lig-coding")["action"] == "local_fallback")
    check("no loop on last provider", decide_fallback("provider_unreachable", 1, "lig-fallback")["action"] == "local_fallback")
    check("unknown trigger -> stop", decide_fallback("weird_new_error", 1, "lig-coding")["action"] == "stop")

    # 12. Fallback record written with required fields
    out = record_fallback("lig-coding", "lig-fallback", "http_timeout", 2, "recovered", diag_dir=tmp / "diag")
    data = json.loads(out.read_text(encoding="utf-8"))
    need = {"provider_initial", "provider_final", "fallback_trigger", "fallback_attempts", "fallback_result"}
    check("fallback record fields", need.issubset(data) and (tmp / "diag" / "provider-fallback-history.jsonl").exists(), str(data))

    for key, value in saved_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

print(f"\n{PASS} checks passed")
