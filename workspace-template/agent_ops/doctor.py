# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .core import RESULTS, REPORTS, ROOT, platform_info, run_cmd, atomic_write_text, atomic_write_json, read_json, CONFIG, now
from .state_manager import heartbeat, update_checkpoint
from .lig_providers import validate_config as validate_lig_config

def chromedriver_candidates() -> list[str]:
    cfg = read_json(CONFIG / "agentops_config.json", {})
    extra = cfg.get("chromedriver_candidates", []) if isinstance(cfg, dict) else []
    candidates = [os.environ.get("CHROMEDRIVER_PATH") or "", str(ROOT / "drivers" / "chromedriver.exe"), str(ROOT / "chromedriver.exe"), str(Path.home() / "Desktop" / "local_LLM" / "drivers" / "chromedriver.exe"), str(Path.home() / "Desktop" / "local_LLM" / "chromedriver.exe")]
    for item in extra:
        if item not in candidates:
            candidates.append(str(item))
    return candidates

def run_doctor() -> dict:
    heartbeat("doctor")
    checks = {"timestamp": now(), "platform": platform_info(), "env": {"PYTHONUTF8": os.environ.get("PYTHONUTF8"), "PYTHONIOENCODING": os.environ.get("PYTHONIOENCODING"), "CHROMEDRIVER_PATH": os.environ.get("CHROMEDRIVER_PATH")}, "chromedriver": {}, "chrome_9222": {}, "encoding": {}}
    found = ""
    for cand in chromedriver_candidates():
        if cand and Path(cand).exists():
            found = cand; break
    checks["chromedriver"]["candidates"] = chromedriver_candidates()
    checks["chromedriver"]["found"] = found
    if found:
        checks["chromedriver"]["version"] = run_cmd([found, "--version"], timeout=10)
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=2) as r:
            body = r.read(2000).decode("utf-8", errors="replace")
            checks["chrome_9222"] = {"ok": True, "body": body}
    except Exception as exc:
        checks["chrome_9222"] = {"ok": False, "error": repr(exc)}
    sample = "encoding-test: 한글 OK / utf-8"
    test_path = RESULTS / "encoding_test_utf8.txt"
    atomic_write_text(test_path, sample)
    checks["encoding"]["roundtrip_ok"] = test_path.read_text(encoding="utf-8", errors="replace") == sample
    checks["toolchain"] = {
        "python": run_cmd([sys.executable, "--version"], timeout=10),
        "git": run_cmd(["git", "--version"], timeout=10),
        "opencode": run_cmd(["opencode", "--version"], timeout=10),
    }
    try:
        checks["lig_api_config"] = validate_lig_config()  # presence flags only, never secret values
    except Exception as exc:
        checks["lig_api_config"] = {"ready": False, "error": repr(exc)}
    # User-facing agent runtime readiness (secret-free: paths + flags only).
    try:
        from .tool_dispatch import REGISTRY
        from .lig_providers import DIAG_DIR
        try:
            from . import mock_transport  # noqa: F401
            mock_ready = True
        except Exception:
            mock_ready = False
        checks["agent_runtime"] = {
            "py311": run_cmd(["py", "-3.11", "--version"], timeout=10),
            "tools": sorted(REGISTRY.keys()),
            "diagnostics_dir": str(DIAG_DIR),
            "mock_smoke_ready": mock_ready,
            "real_provider_ready": bool(checks["lig_api_config"].get("ready")),
            "company_validation": "pending",
        }
    except Exception as exc:
        checks["agent_runtime"] = {"error": repr(exc)}
    # What kinds of office/engineering work can be handled right now, and
    # which validations are still pending (secret-free inventory).
    try:
        from .capabilities import capability_summary
        checks["capabilities"] = capability_summary()
    except Exception as exc:
        checks["capabilities"] = {"error": repr(exc)}
    # Execution side: which app adapters exist and what each still needs.
    try:
        from .adapters import adapter_summary
        checks["app_adapters"] = adapter_summary()
    except Exception as exc:
        checks["app_adapters"] = {"error": repr(exc)}
    # Planning/generation pipeline: how plans are made, whether the artifact
    # quality validator is importable, and where LLM enrichment stands.
    try:
        try:
            from .artifact_quality import validate_artifact_set  # noqa: F401
            quality_available = True
        except Exception:
            quality_available = False
        from .lig_providers import DIAG_DIR as _diag_dir
        checks["artifact_pipeline"] = {
            "planner_mode": "deterministic_keyword",
            "semantic_planner": "pending — plan_task(task, planner=...) hook ready",
            "quality_validator_available": quality_available,
            "llm_enrichment": ("mock available via generate_artifacts(enrich=True, llm_client=...); "
                               "real LLM fill: company validation pending"),
            "enrich_diagnostics": str(_diag_dir / "artifact-enrich-last.json"),
            "next_commands": [
                'py -3.11 agent_ops\\agentops.py plan --task "작업 설명" --make-artifacts',
                'py -3.11 tests\\test_capability_bench.py',
            ],
        }
    except Exception as exc:
        checks["artifact_pipeline"] = {"error": repr(exc)}
    atomic_write_json(RESULTS / "environment_check.json", checks)
    lines = ["# AgentOps Doctor Report", "", f"- Generated: {checks['timestamp']}", f"- ChromeDriver found: `{found or 'NOT FOUND'}`", f"- Chrome 9222 OK: `{checks['chrome_9222'].get('ok')}`", f"- UTF-8 roundtrip OK: `{checks['encoding']['roundtrip_ok']}`", "", "## Raw", "```json", json.dumps(checks, ensure_ascii=False, indent=2), "```"]
    atomic_write_text(REPORTS / "DOCTOR_REPORT.md", "\n".join(lines))
    update_checkpoint("doctor completed")
    return checks
