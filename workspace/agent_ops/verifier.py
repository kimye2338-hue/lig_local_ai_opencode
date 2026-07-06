# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import sys
import py_compile

from .core import ROOT, AGENT_OPS, REPORTS, RESULTS, run_cmd, atomic_write_text, atomic_write_json, read_text, read_json
from .state_manager import heartbeat, update_checkpoint, mark_last_known_good

def scan_agents() -> list[dict]:
    issues = []
    agents_dir = ROOT / ".opencode" / "agents"
    for path in agents_dir.glob("*.md") if agents_dir.exists() else []:
        text = read_text(path)
        if "\ntools:" in text:
            issues.append({"file": str(path), "issue": "deprecated tools frontmatter present"})
        if "patch:" in text:
            issues.append({"file": str(path), "issue": "patch key present; use edit permission"})
        if "permission:" not in text:
            issues.append({"file": str(path), "issue": "permission block missing"})
        # Regression guard: an agent must not grant broad bash allow. Flag either a
        # direct `bash: allow` or a wildcard `"*": allow` inside the permission block.
        if re.search(r'(?mi)^\s*bash\s*:\s*"?allow"?\s*$', text) or \
                re.search(r'(?mi)^\s*"?\*"?\s*:\s*"?allow"?\s*$', text):
            issues.append({"file": str(path), "issue": "broad bash allow permission; require ask or scoped allow"})
    return issues

def verify() -> dict:
    heartbeat("verify")
    py_files = sorted(AGENT_OPS.glob("*.py"))
    compile_results = []
    for p in py_files:
        try:
            py_compile.compile(str(p), doraise=True)
            compile_results.append({"ok": True, "file": str(p)})
        except Exception as exc:
            compile_results.append({"ok": False, "file": str(p), "error": repr(exc)})
    opencode = read_json(ROOT / "opencode.json", {})
    instructions = opencode.get("instructions", []) if isinstance(opencode, dict) else []
    instruction_issues = [x for x in instructions if isinstance(x, str) and x.startswith(".agent-memory")]
    required = [AGENT_OPS / "AGENTOPS_RULES.md", AGENT_OPS / "agentops.py", ROOT / ".opencode" / "agents" / "agent.md", ROOT / ".opencode" / "commands" / "continue.md", ROOT / ".agent-memory" / "memory.jsonl"]
    missing = [str(p) for p in required if not p.exists()]
    agent_issues = scan_agents()
    ok = all(r.get("ok") for r in compile_results) and not missing and not instruction_issues and not agent_issues
    report = {"ok": ok, "py_compile": compile_results, "missing": missing, "instruction_issues": instruction_issues, "agent_issues": agent_issues}
    atomic_write_json(RESULTS / "verification_result.json", report)
    atomic_write_text(REPORTS / "VERIFICATION_REPORT.md", "# Verification Report\n\n- OK: `" + str(ok) + "`\n\n```json\n" + json.dumps(report, ensure_ascii=False, indent=2) + "\n```\n")
    update_checkpoint("verify completed")
    if ok:
        mark_last_known_good("verify passed")
    return report
