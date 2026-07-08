# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

ROOT = Path.cwd()
LOGS = ROOT / "agent_ops" / "logs"

def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

def is_inside_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except Exception:
        return False

def atomic_write(path: Path, data: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding=encoding, errors="replace", newline="\n") as f:
            f.write(data.replace("\r\n", "\n"))
        os.replace(str(tmp_path), str(path))
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass

def validate(path: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {"path": str(path), "ok": True, "errors": []}
    if not path.exists():
        result["ok"] = False
        result["errors"].append("missing")
        return result
    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        result["chars"] = len(text)
        result["lines"] = len(text.splitlines())
    except Exception as exc:
        result["ok"] = False
        result["errors"].append("utf8_read_failed:" + repr(exc))
        return result
    if suffix == ".json":
        try:
            json.loads(text)
        except Exception as exc:
            result["ok"] = False
            result["errors"].append("json_parse_failed:" + repr(exc))
    if suffix == ".py":
        cp = subprocess.run([sys.executable, "-m", "py_compile", str(path)], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
        result["py_compile_returncode"] = cp.returncode
        if cp.returncode != 0:
            result["ok"] = False
            result["errors"].append("py_compile_failed")
            result["stderr"] = cp.stderr[-2000:]
    name_lower = path.name.lower()
    if suffix in {".bat", ".cmd"} or name_lower.endswith(".bat.txt") or name_lower.endswith(".cmd.txt"):
        try:
            path.read_text(encoding="ascii")
        except Exception:
            result["ok"] = False
            result["errors"].append("bat_cmd_must_be_ascii")
    return result

def log(item: Dict[str, Any]) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / "safe_file_writer.jsonl").open("a", encoding="utf-8", errors="replace") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Safe file writer for AgentOps")
    parser.add_argument("path", help="Project-relative output path")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--content-file")
    src.add_argument("--b64")
    src.add_argument("--stdin", action="store_true")
    parser.add_argument("--no-validate", action="store_true")
    args = parser.parse_args(argv)

    target = (ROOT / args.path).resolve()
    if not is_inside_root(target):
        print("Refusing to write outside project root.", file=sys.stderr)
        return 30

    if args.content_file:
        content = Path(args.content_file).read_text(encoding="utf-8", errors="replace")
    elif args.b64:
        content = base64.b64decode(args.b64).decode("utf-8", errors="replace")
    else:
        content = sys.stdin.read()

    backup = None
    if target.exists():
        backup = target.with_suffix(target.suffix + ".bak")
        backup.write_text(target.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

    atomic_write(target, content)
    result = validate(target) if not args.no_validate else {"ok": True, "path": str(target), "validation_skipped": True}
    item = {"timestamp": now(), "target": str(target), "backup": str(backup) if backup else None, "result": result}
    log(item)
    print(json.dumps(item, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 40

if __name__ == "__main__":
    raise SystemExit(main())
