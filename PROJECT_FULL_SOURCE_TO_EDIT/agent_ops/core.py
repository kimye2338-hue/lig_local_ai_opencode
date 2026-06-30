# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
AGENT_OPS = ROOT / "agent_ops"
STATE = AGENT_OPS / "state"
LOGS = AGENT_OPS / "logs"
REPORTS = AGENT_OPS / "reports"
RESULTS = AGENT_OPS / "results"
CONTROL = AGENT_OPS / "control"
POLICIES = AGENT_OPS / "policies"
CONFIG = AGENT_OPS / "config"
ARCHIVE = AGENT_OPS / "archive"
LOCKS = AGENT_OPS / "locks"
MEMORY = ROOT / ".agent-memory"
PORTAL = ROOT / "portal_research"

def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

def ensure_dirs() -> None:
    for path in [
        AGENT_OPS, STATE, LOGS, REPORTS, RESULTS, CONTROL, POLICIES, CONFIG, ARCHIVE, LOCKS,
        MEMORY, MEMORY / "archive",
        PORTAL / "reports", PORTAL / "results", PORTAL / "logs",
        PORTAL / "screenshots", PORTAL / "html_snapshots",
        RESULTS / "llm_responses",
    ]:
        path.mkdir(parents=True, exist_ok=True)

def read_text(path: Path) -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return ""

def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = str(content).replace("\r\n", "\n")
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="replace", newline="\n") as f:
            f.write(text)
        os.replace(str(tmp_path), str(path))
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass

def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(read_text(path))
    except Exception:
        return default
    return default

def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))

def append_jsonl(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", errors="replace") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

def read_jsonl(path: Path) -> List[Any]:
    out: List[Any] = []
    if not path.exists():
        return out
    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            out.append({"raw": line, "parse_error": True})
    return out

def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    if text:
        text += "\n"
    atomic_write_text(path, text)

def tail_jsonl(path: Path, n: int) -> List[Any]:
    return read_jsonl(path)[-n:]

def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False
    except Exception:
        return False

def _lock_is_stale(lock_path: Path, max_age_seconds: int = 900) -> bool:
    try:
        text = read_text(lock_path).strip()
        parts = text.split()
        pid = int(parts[0]) if parts else -1
        timestamp = parts[1] if len(parts) > 1 else ""
        if pid > 0 and not _pid_alive(pid):
            return True
        if timestamp:
            t = datetime.fromisoformat(timestamp)
            age = (datetime.now(t.tzinfo) - t).total_seconds()
            if age > max_age_seconds:
                return True
    except Exception:
        # If lock is unreadable or malformed, treat as stale after timeout path.
        return True
    return False

@contextmanager
def file_lock(name: str, timeout: float = 10.0, stale_after_seconds: int = 900):
    ensure_dirs()
    lock_path = LOCKS / (name + ".lock")
    start = time.time()
    fd = None
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {now()}".encode("utf-8", errors="replace"))
            break
        except FileExistsError:
            if time.time() - start > timeout:
                if _lock_is_stale(lock_path, stale_after_seconds):
                    try:
                        lock_path.unlink()
                        start = time.time()
                        continue
                    except Exception:
                        pass
                raise TimeoutError(f"lock timeout: {lock_path}")
            time.sleep(0.1)
    try:
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        try:
            lock_path.unlink()
        except Exception:
            pass

def run_cmd(args: List[str], timeout: int = 30) -> Dict[str, Any]:
    try:
        cp = subprocess.run(
            args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "ok": cp.returncode == 0,
            "returncode": cp.returncode,
            "stdout": cp.stdout[-5000:],
            "stderr": cp.stderr[-5000:],
            "args": args,
        }
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "error": "TIMEOUT", "args": args, "timeout": timeout, "stdout": str(exc.stdout or "")[-2000:], "stderr": str(exc.stderr or "")[-2000:]}
    except Exception as exc:
        return {"ok": False, "error": repr(exc), "args": args}

def backup_file(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        rel = path.relative_to(ROOT)
    except Exception:
        rel = Path(path.name)
    backup = ARCHIVE / "backups" / stamp / rel
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(path), str(backup))
    return backup

def validate_written_file(path: Path) -> Dict[str, Any]:
    info: Dict[str, Any] = {"path": str(path), "exists": path.exists(), "ok": True, "errors": []}
    if not path.exists():
        info["ok"] = False
        info["errors"].append("missing")
        return info
    try:
        text = path.read_text(encoding="utf-8")
        info["chars"] = len(text)
    except Exception as exc:
        info["ok"] = False
        info["errors"].append("utf8_read_failed:" + repr(exc))
        return info
    if path.suffix.lower() == ".json":
        try:
            json.loads(text)
        except Exception as exc:
            info["ok"] = False
            info["errors"].append("json_parse_failed:" + repr(exc))
    if path.suffix.lower() == ".py":
        r = run_cmd([sys.executable, "-m", "py_compile", str(path)], timeout=30)
        if not r.get("ok"):
            info["ok"] = False
            info["errors"].append("py_compile_failed")
            info["py_compile"] = r
    return info

def is_stop_requested() -> bool:
    return (CONTROL / "STOP").exists()

def platform_info() -> Dict[str, Any]:
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "cwd": str(ROOT),
        "python_executable": sys.executable,
    }
