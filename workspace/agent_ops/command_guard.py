# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path.cwd()
AGENT_OPS = ROOT / "agent_ops"
LOGS = AGENT_OPS / "logs"
REPORTS = AGENT_OPS / "reports"

BLOCK = "block"
ASK = "ask"
ALLOW = "allow"

PROSE_MARKERS = [
    "The content contains",
    "Let's write",
    "Let's create",
    "Better to use",
    "Actually the content",
    "JSON error",
    "manual formatting",
    "Use echo for each part",
    "생략",
    "하려고",
    "설명",
    "대안",
    "생각",
]

FAKE_TOOL_MARKERS = [
    'bash {"command"',
    "functions.bash(",
    "<tool_call>",
    '"name":"bash"',
    '"name": "bash"',
]

WRITE_CODE_PATTERNS = [
    r"\bcat\s*>\s*[^&|;]+?\.(py|js|ts|tsx|jsx|bat|cmd|ps1|json|yaml|yml|md)\b",
    r"\bcat\s+<<\s*['\"]?[A-Za-z0-9_]+['\"]?",
    r"<<\s*['\"]?EOF['\"]?",
    r"\becho\b.+>\s*[^&|;]+?\.(py|js|ts|tsx|jsx|bat|cmd|ps1|json|yaml|yml|md)\b",
    r"\bprintf\b.+>\s*[^&|;]+?\.(py|js|ts|tsx|jsx|bat|cmd|ps1|json|yaml|yml|md)\b",
    r"\bpython(?:3)?\s+-c\b",
    r"\bpy\s+-3(?:\.\d+)?\s+-c\b",
]

DANGEROUS_PATTERNS = [
    # rm with both r and f flags in any order/grouping (-rf, -fr, -r -f, ...)
    r"\brm\b(?=.*\s-\w*r)(?=.*\s-\w*f)",
    r"\brm\s+-rf\b",
    r"\bdel\s+/[qsf]\b",
    r"\bdel\s+\S",
    r"\brmdir\b.*\s/s\b",
    r"\brd\b.*\s/s\b",
    r"\bformat\s+[A-Za-z]:",
    r"\bformat\b(?:\s+/\S+)+\s+[A-Za-z]:",
    r"\bpowershell\b.+EncodedCommand",
    r"\b(?:powershell|pwsh)\b.*\s-e(?:n?c?o?d?e?d?c?o?m?m?a?n?d?)?\b",
    r"\bremove-item\b.*-(?:recurse|force)\b",
    r"\bstop-computer\b",
    r"\bshutdown\b(?=.*\s/f\b)(?=.*\s/[sr]\b)",
    r"\bvssadmin\s+delete\s+shadows\b",
    r"\bdiskpart\b",
    r"\breg\s+delete\b.*\s/f\b",
    r"\bbcdedit\b",
    r"\bwmic\b.*\bcall\s+create\b",
    r"\btaskkill\b.*\s/f\b",
    r"\bcipher\b.*/w",
    r"\bnew-object\s+(?:system\.)?net\.webclient\b",
    r"\bdownloadstring\b",
    r"\b(?:iex|invoke-expression)\b.*\b(?:iwr|invoke-webrequest|wget|curl)\b",
    r"\b(?:iwr|invoke-webrequest|wget|curl)\b.*\b(?:iex|invoke-expression)\b",
    r"\bcurl\b.+\|\s*(bash|sh|python)",
    r"\biwr\b.+\|\s*(iex|powershell)",
]

SAFE_PREFIXES = [
    "python agent_ops/agentops.py ",
    "py -3.11 agent_ops/agentops.py ",
    "py -3 agent_ops/agentops.py ",
    "python agent_ops/command_guard.py ",
    "py -3.11 agent_ops/command_guard.py ",
    "python agent_ops/safe_file_writer.py ",
    "py -3.11 agent_ops/safe_file_writer.py ",
    "python -m py_compile ",
    "py -3.11 -m py_compile ",
    "git status",
    "git diff",
    "git log",
    "grep ",
    "findstr ",
    "dir",
    "type ",
]

def _matches_safe_prefix(cmd: str, prefix: str) -> bool:
    # Prefixes ending in a space are already token-bounded ("grep ", "type ").
    # Bare prefixes ("dir", "git log") must match the whole token exactly or be
    # followed by a space — otherwise "dir" would auto-allow "dirty.bat".
    if prefix.endswith(" "):
        return cmd.startswith(prefix)
    return cmd == prefix or cmd.startswith(prefix + " ")

def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

def ensure_dirs() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

def append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    ensure_dirs()
    with path.open("a", encoding="utf-8", errors="replace") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def _line_count(text: str) -> int:
    return len((text or "").splitlines())

def _detect_heredoc_issue(text: str) -> List[str]:
    reasons: List[str] = []
    if "<<" not in text:
        return reasons
    matches = re.findall(r"<<\s*['\"]?([A-Za-z0-9_]+)['\"]?", text)
    for delim in matches:
        own = re.search(rf"(?m)^{re.escape(delim)}\s*$", text)
        if not own:
            reasons.append(f"heredoc delimiter `{delim}` does not close on its own line")
    if re.search(r"\bcat\s*>\s*[^&|;]+?\.(py|js|ts|tsx|jsx|bat|cmd|ps1|json|yaml|yml|md)\b", text, re.I):
        reasons.append("heredoc/cat writes a source/config/document file; use write/apply_patch/safe_file_writer instead")
    if ('"' * 3) in text or ("'" * 3) in text:
        reasons.append("heredoc contains triple quotes; high risk of JSON/shell escaping failure")
    if "\\n" in text and _line_count(text) < 5:
        reasons.append("escaped newlines inside one-line command; high risk of broken file content")
    return reasons

def analyze(text: str) -> Dict[str, Any]:
    command = text or ""
    lower = command.lower()
    reasons: List[str] = []
    warnings: List[str] = []

    if not command.strip():
        return {"decision": BLOCK, "reasons": ["empty command"], "warnings": [], "command_tail": ""}

    for marker in PROSE_MARKERS:
        if marker.lower() in lower:
            reasons.append(f"prose/reasoning marker in command: {marker}")

    for marker in FAKE_TOOL_MARKERS:
        if marker.lower() in lower:
            reasons.append(f"fake tool-call/textual tool marker: {marker}")

    for pat in WRITE_CODE_PATTERNS:
        if re.search(pat, command, re.I | re.S):
            reasons.append(f"unsafe long-file/write command pattern: {pat}")

    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, command, re.I | re.S):
            reasons.append(f"dangerous shell pattern: {pat}")

    reasons.extend(_detect_heredoc_issue(command))

    if _line_count(command) > 25 and ("cat" in lower or "echo" in lower or "printf" in lower):
        reasons.append("long multi-line shell file generation; use OpenCode write/apply_patch/safe_file_writer")

    if len(command) > 4000:
        reasons.append("command too long; split into real file + verification")

    if "`" in command and ("```" in command or "bash" in lower):
        warnings.append("markdown fence/backticks inside command-like text")

    if "portal_autonomous_research_runner.py" in command and ("while true" in lower or "runs indefinitely" in lower or "indefinitely" in lower):
        reasons.append("portal autonomous runner appears indefinite; long loops must run outside OpenCode bash with checkpoints and explicit stop file")

    normalized = command.strip().replace("\\", "/")
    safe_prefix = any(_matches_safe_prefix(normalized, p) for p in SAFE_PREFIXES)
    # A command that begins with a safe prefix but chains another command via a
    # separator (&& ; | & newline), redirects output (> <), or uses cmd/PS
    # escapes (^ `) must not be auto-allowed — force it to ASK. Redirection in
    # particular would let "type nul > file.py" truncate files under ALLOW.
    if safe_prefix and re.search(r"[;&|<>^`\r\n]", command):
        safe_prefix = False
    # P2-1: the orchestrator starts a long-running loop inside OpenCode bash.
    # Long loops must be launched by the external BAT only, so never auto-allow it.
    if "agentops.py orchestrator" in normalized:
        safe_prefix = False

    if reasons:
        decision = BLOCK
    elif safe_prefix:
        decision = ALLOW
    else:
        decision = ASK

    return {
        "decision": decision,
        "reasons": reasons,
        "warnings": warnings,
        "line_count": _line_count(command),
        "length": len(command),
        "safe_prefix": safe_prefix,
        "command_tail": command[-1000:],
    }

def check_command(text: str, source: str = "cli") -> Dict[str, Any]:
    result = analyze(text)
    result["timestamp"] = now()
    result["source"] = source
    append_jsonl(LOGS / "command_guard.jsonl", result)
    (REPORTS / "COMMAND_GUARD_LAST.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result

def guarded_run(command: str, timeout: int = 120) -> int:
    result = check_command(command, source="guarded_run")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["decision"] == BLOCK:
        print("\nBLOCKED by AgentOps command guard. Do not approve or execute this command.", file=sys.stderr)
        return 20
    if result["decision"] == ASK:
        print("\nASK decision: run manually only if the approval window contains pure command text.", file=sys.stderr)
        return 10
    cp = subprocess.run(command, cwd=str(ROOT), shell=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return cp.returncode

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AgentOps command guard")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("check")
    p.add_argument("text", nargs="*")
    p.add_argument("--stdin", action="store_true")

    p = sub.add_parser("run")
    p.add_argument("text", nargs="*")
    p.add_argument("--timeout", type=int, default=120)

    sub.add_parser("explain")

    args = parser.parse_args(argv)

    if args.cmd == "check":
        text = sys.stdin.read() if args.stdin else " ".join(args.text)
        result = check_command(text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] == ALLOW else (10 if result["decision"] == ASK else 20)

    if args.cmd == "run":
        text = " ".join(args.text)
        return guarded_run(text, timeout=args.timeout)

    if args.cmd == "explain":
        print(
            "AgentOps command guard blocks approval-window corruption patterns:\n"
            "- reasoning/prose mixed into bash\n"
            "- fake tool calls\n"
            "- cat/heredoc/echo/printf writing code files\n"
            "- long python -c\n"
            "- unclosed heredoc\n"
            "Use OpenCode write/apply_patch or agent_ops/safe_file_writer.py instead."
        )
        return 0

    parser.print_help()
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
