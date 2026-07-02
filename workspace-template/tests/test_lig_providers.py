# -*- coding: utf-8 -*-
"""Tests for LIG provider config loading + fallback policy (stdlib only).

Run: py -3.11 tests\\test_lig_providers.py
Uses a temp env file — never touches or prints real secrets.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_ops.lig_providers import build_providers, decide_fallback, load_lig_env, record_fallback, validate_config  # noqa: E402

PASS = 0


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

    # 1. Missing secret file -> not ready, no crash
    rep = validate_config(path=tmp / "absent.env")
    check("missing file -> not ready", rep["ready"] is False and rep["secret_file_found"] is False, str(rep))

    # 2. Placeholder values -> not ready
    env_file = tmp / "lig-api.env"
    env_file.write_text("LIG_GATEWAY_BASE_URL=http://REPLACE_WITH_INTERNAL_GATEWAY\nLIG_API_KEY=REPLACE_WITH_LOCAL_SECRET_ONLY\n", encoding="utf-8")
    rep = validate_config(path=env_file)
    check("placeholder -> not ready", rep["ready"] is False and rep["gateway_url_set"] is False and rep["api_key_set"] is False, str(rep))

    # 3. Real-looking values (fake) -> ready; report contains no secret value
    secret = "sk-test-DO-NOT-LEAK-12345"
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

    # 6. Fallback policy decisions
    check("timeout first -> retry", decide_fallback("http_timeout", 1, "lig-coding")["action"] == "retry")
    check("timeout exhausted -> switch", decide_fallback("http_timeout", 2, "lig-coding")["action"] == "switch_fallback")
    check("4xx -> stop", decide_fallback("http_4xx", 1, "lig-coding")["action"] == "stop")
    check("malformed -> simplify_retry", decide_fallback("malformed_tool_call", 1, "lig-coding")["action"] == "simplify_retry")
    check("malformed exhausted -> local", decide_fallback("malformed_tool_call", 3, "lig-coding")["action"] == "local_fallback")
    check("no loop on last provider", decide_fallback("provider_unreachable", 1, "lig-fallback")["action"] == "local_fallback")
    check("unknown trigger -> stop", decide_fallback("weird_new_error", 1, "lig-coding")["action"] == "stop")

    # 7. Fallback record written with required fields
    out = record_fallback("lig-coding", "lig-fallback", "http_timeout", 2, "recovered", diag_dir=tmp / "diag")
    data = json.loads(out.read_text(encoding="utf-8"))
    need = {"provider_initial", "provider_final", "fallback_trigger", "fallback_attempts", "fallback_result"}
    check("fallback record fields", need.issubset(data) and (tmp / "diag" / "provider-fallback-history.jsonl").exists(), str(data))

print(f"\n{PASS} checks passed")
