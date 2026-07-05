# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from .core import RESULTS, REPORTS, ROOT, platform_info, run_cmd, atomic_write_text, atomic_write_json, read_json, CONFIG, now
from .state_manager import heartbeat, update_checkpoint
from .lig_providers import build_providers, load_lig_env, validate_config as validate_lig_config


def chromedriver_candidates() -> list[str]:
    cfg = read_json(CONFIG / "agentops_config.json", {})
    extra = cfg.get("chromedriver_candidates", []) if isinstance(cfg, dict) else []
    candidates = [os.environ.get("CHROMEDRIVER_PATH") or "", str(ROOT / "drivers" / "chromedriver.exe"), str(ROOT / "chromedriver.exe"), str(Path.home() / "Desktop" / "local_LLM" / "drivers" / "chromedriver.exe"), str(Path.home() / "Desktop" / "local_LLM" / "chromedriver.exe")]
    for item in extra:
        if item not in candidates:
            candidates.append(str(item))
    return candidates


def _safe_local_base_label(base_url: str) -> str:
    """Return a printable label without leaking a host or full URL.

    127.0.0.1 is allowed by the task because it is the local Ollama default.
    Any other host is reduced to a presence label.
    """
    if not base_url:
        return "not configured"
    try:
        host = (urlsplit(base_url).hostname or "").lower()
    except Exception:
        return "configured"
    if host == "127.0.0.1":
        return "127.0.0.1"
    if host in ("localhost", "::1"):
        return "loopback"
    return "configured"


def _openai_models_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    return base + "/models"


def _probe_openai_models(base_url: str) -> dict:
    """Reachability probe for OpenAI-compatible local endpoints.

    The returned object intentionally contains only booleans/status classes, never
    the raw URL or exception repr because those may include internal hosts.
    """
    if not base_url:
        return {"ok": False, "error_class": "not_configured"}
    try:
        import urllib.request
        with urllib.request.urlopen(_openai_models_url(base_url), timeout=2) as response:
            response.read(256)
            return {"ok": True, "status": getattr(response, "status", 200)}
    except Exception as exc:
        return {"ok": False, "error_class": exc.__class__.__name__}


def llm_endpoints_summary() -> dict:
    """Secret-free inventory for real/local LLM readiness."""
    env = load_lig_env()
    cfg = validate_lig_config(env=env)
    providers = build_providers(env)
    profile = cfg.get("profile", "company_gateway")
    routes = {}
    for name, provider in providers.items():
        routes[name] = {
            "configured": bool(provider.get("base_url")),
            "model_set": bool(provider.get("model")),
            "timeout_set": bool(provider.get("timeout")),
        }
    local_base = providers.get("lig-coding", {}).get("base_url", "") if profile == "local_openai" else ""
    return {
        "profile": profile,
        "ready": bool(cfg.get("ready")),
        "secret_file_found": bool(cfg.get("secret_file_found")),
        "gateway_url_set": bool(cfg.get("gateway_url_set")),
        "api_key_set": bool(cfg.get("api_key_set")),
        "routes": routes,
        "local_base": _safe_local_base_label(local_base),
        "local_reachable": _probe_openai_models(local_base) if profile == "local_openai" else {"ok": False, "skipped": "not local_openai profile"},
    }


def operations_summary() -> dict:
    """Secret-free operational state: audit, schedule, runbook, reports."""
    try:
        from . import audit, schedule_store
        audit_dir = Path(os.environ.get("LIG_AUDIT_DIR") or audit.AUDIT_DIR)
        audit_file = audit_dir / audit.AUDIT_FILE
        last_ts = ""
        if audit_file.exists():
            for line in audit_file.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    last_ts = str(json.loads(line).get("ts") or "")
                except Exception:
                    pass
        reports = sorted(RESULTS.glob("reports/work_*.md"), key=lambda p: p.stat().st_mtime, reverse=True) \
            if (RESULTS / "reports").exists() else []
        return {
            "audit_file": str(audit_file),
            "audit_size_bytes": audit_file.stat().st_size if audit_file.exists() else 0,
            "audit_last_ts": last_ts,
            "audit_rotated": len(list(audit_dir.glob("audit_*.jsonl.bak"))) if audit_dir.exists() else 0,
            "schedule_items": len(schedule_store.list_items("all")),
            # RUNBOOK.md ships with the code (workspace-template/docs/), not the
            # data root; resolve it code-relative so relocated installs
            # (AGENTOPS_ROOT != code dir) do not falsely report it missing.
            "runbook": (Path(__file__).resolve().parents[1] / "docs" / "RUNBOOK.md").exists(),
            "last_work_report": str(reports[0]) if reports else "",
        }
    except Exception as exc:
        return {"error": exc.__class__.__name__}


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
    try:
        checks["llm_endpoints"] = llm_endpoints_summary()
    except Exception as exc:
        checks["llm_endpoints"] = {"ok": False, "error_class": exc.__class__.__name__}
    try:
        checks["operations"] = operations_summary()
    except Exception as exc:
        checks["operations"] = {"error": exc.__class__.__name__}
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
            "local_llm_reachable": bool(checks.get("llm_endpoints", {}).get("local_reachable", {}).get("ok")),
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
        bench_file = RESULTS / "capability_bench" / "last_bench.json"
        bench_info = read_json(bench_file, {}) if bench_file.exists() else {}
        reports_dir = RESULTS / "reports"
        real_floor_reports = sorted(
            [p for p in reports_dir.glob("capability_floor_*.md") if p.name != "capability_floor_mock.md"],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ) if reports_dir.exists() else []
        mock_floor_report = reports_dir / "capability_floor_mock.md"
        legacy_floor_report = reports_dir / "capability_floor.md"
        floor_report = (
            real_floor_reports[0] if real_floor_reports else
            mock_floor_report if mock_floor_report.exists() else
            legacy_floor_report
        )
        try:
            from .input_ingest import SUPPORTED_SUFFIXES
            ingest_available = True
            supported_types = sorted(SUPPORTED_SUFFIXES)
        except Exception:
            ingest_available = False
            supported_types = []
        checks["artifact_pipeline"] = {
            "input_ingest_available": ingest_available,
            "supported_input_types": supported_types,
            "last_work_context": str(_diag_dir / "work-context-last.json"),
            "planner_mode": "deterministic_keyword",
            "semantic_planner": "pending — plan_task(task, planner=...) hook ready",
            "quality_validator_available": quality_available,
            "llm_enrichment": ("mock available via generate_artifacts(enrich=True, llm_client=...); "
                               "real LLM fill: work --mode real 에서 자동 (게이트웨이 설정 시; 실측 2026-07-05)"),
            "enrich_diagnostics": str(_diag_dir / "artifact-enrich-last.json"),
            "last_bench_result": {"path": str(bench_file), "exists": bench_file.exists(),
                                  "checks_passed": bench_info.get("checks_passed"),
                                  "timestamp": bench_info.get("timestamp")},
            "capability_floor_report": (
                {"path": str(floor_report), "timestamp": time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(floor_report.stat().st_mtime))}
                if floor_report.exists() else "not generated"),
            "next_commands": [
                'py -3.11 agent_ops\\agentops.py plan --task "작업 설명" --make-artifacts',
                'py -3.11 tests\\test_capability_bench.py',
            ],
        }
    except Exception as exc:
        checks["artifact_pipeline"] = {"error": repr(exc)}
    atomic_write_json(RESULTS / "environment_check.json", checks)
    lines = ["# AgentOps Doctor Report", "", f"- Generated: {checks['timestamp']}", f"- ChromeDriver found: `{found or 'NOT FOUND'}`", f"- Chrome 9222 OK: `{checks['chrome_9222'].get('ok')}`", f"- UTF-8 roundtrip OK: `{checks['encoding']['roundtrip_ok']}`", f"- LLM profile: `{checks.get('llm_endpoints', {}).get('profile', 'unknown')}`", f"- Local LLM reachable: `{checks.get('llm_endpoints', {}).get('local_reachable', {}).get('ok')}`", "", "## Raw", "```json", json.dumps(checks, ensure_ascii=False, indent=2), "```"]
    atomic_write_text(REPORTS / "DOCTOR_REPORT.md", "\n".join(lines))
    update_checkpoint("doctor completed")
    return checks
