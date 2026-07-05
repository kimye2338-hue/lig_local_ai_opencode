# -*- coding: utf-8 -*-
"""Always-on-top OpenCodeLIG hamster status overlay.

Stdlib-only by design: tkinter + JSON files.  It does not embed any stock image
or copyrighted asset.  The hamster is drawn procedurally on a Tk canvas so it is
safe to ship inside the company/offline bundle.

Data sources, in priority order:
  1. %LIG_STATE_DIR%/current_status.json      (future explicit status writer)
  2. %LIG_DIAG_DIR%/agent-loop-last.json      (existing run_agent_loop result)
  3. %LIG_DIAG_DIR%/tool-dispatch-last.json   (existing tool dispatch result)

Launch on Windows:
  launch\\hamster.bat
"""
from __future__ import annotations

import json
import os
import platform
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

APP_NAME = "OpenCodeLIG Hamster"
DEFAULT_STATE_DIR = Path(os.environ.get("LIG_STATE_DIR") or (Path.home() / "OpenCodeLIG_USERDATA" / "state"))
DEFAULT_DIAG_DIR = Path(os.environ.get("LIG_DIAG_DIR") or (Path.home() / "OpenCodeLIG_USERDATA" / "diagnostics"))
STALE_SECONDS = int(os.environ.get("LIG_HAMSTER_STALE_SECONDS") or "900")
POLL_MS = int(os.environ.get("LIG_HAMSTER_POLL_MS") or "1000")

STATUS_LABELS = {
    "idle": "대기 중",
    "working": "작업 중",
    "done": "완료",
    "needs_user": "확인 필요",
    "error": "오류",
    "stalled": "멈춤 의심",
}

@dataclass
class Snapshot:
    status: str = "idle"
    task: str = ""
    message: str = "대기 중입니다. 작업이 시작되면 여기에서 알려드릴게요."
    last_update: str = ""
    source: str = "none"
    raw: Optional[Dict[str, Any]] = None


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not path.exists() or not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        return None


def _mtime_iso(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    except Exception:
        return ""


def _age_seconds(path: Path) -> float:
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except Exception:
        return 10**9


def _clean_text(value: Any, limit: int = 96) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _status_from_category(category: str) -> str:
    category = (category or "").lower()
    if category in {"missing_argument", "approval_required", "needs_user", "permission_required"}:
        return "needs_user"
    if category in {"browser_unavailable", "unknown_tool", "invalid_argument", "path_escape", "io_error", "not_found"}:
        return "error"
    return "working"


def _snapshot_from_current_status(state_dir: Path) -> Optional[Snapshot]:
    path = state_dir / "current_status.json"
    data = _read_json(path)
    if not data:
        return None
    status = _clean_text(data.get("status"), 24) or "idle"
    task = _clean_text(data.get("task"), 64)
    message = _clean_text(data.get("message"), 140) or STATUS_LABELS.get(status, status)
    if status == "working" and _age_seconds(path) > STALE_SECONDS:
        status = "stalled"
        message = "한동안 상태 변화가 없습니다. 에이전트가 멈췄을 수 있습니다."
    return Snapshot(status=status, task=task, message=message,
                    last_update=str(data.get("last_update") or _mtime_iso(path)), source=str(path), raw=data)


def _snapshot_from_agent_loop(diag_dir: Path) -> Optional[Snapshot]:
    path = diag_dir / "agent-loop-last.json"
    data = _read_json(path)
    if not data:
        return None
    outcome = str(data.get("outcome") or "")
    if outcome == "completed" or data.get("ok") is True:
        status = "done"
        message = _clean_text(data.get("final_content"), 120) or "작업이 완료되었습니다."
    elif outcome in {"llm_failed", "tool_loop_cutoff", "max_turns_exceeded"}:
        status = "needs_user" if outcome in {"tool_loop_cutoff", "max_turns_exceeded"} else "error"
        message = {
            "llm_failed": "LLM 호출이 실패했습니다. 설정/네트워크를 확인해야 합니다.",
            "tool_loop_cutoff": "같은 도구 호출이 반복 실패해서 멈췄습니다.",
            "max_turns_exceeded": "최대 진행 턴을 넘었습니다. 사용자의 판단이 필요합니다.",
        }.get(outcome, "작업 확인이 필요합니다.")
    else:
        status = "working"
        message = "에이전트 작업 진행 중입니다."
    if status == "working" and _age_seconds(path) > STALE_SECONDS:
        status = "stalled"
        message = "작업 로그가 오래 갱신되지 않았습니다. 멈춤 여부를 확인해 주세요."
    return Snapshot(status=status, task="agent loop", message=message,
                    last_update=str(data.get("timestamp") or _mtime_iso(path)), source=str(path), raw=data)


def _snapshot_from_tool_dispatch(diag_dir: Path) -> Optional[Snapshot]:
    path = diag_dir / "tool-dispatch-last.json"
    data = _read_json(path)
    if not data:
        return None
    tool = _clean_text(data.get("tool"), 64) or "tool"
    if data.get("ok") is True:
        status = "working"
        message = f"{tool} 실행을 완료하고 다음 단계를 진행 중입니다."
    else:
        category = str(data.get("root_cause_category") or "")
        status = _status_from_category(category)
        err = _clean_text(data.get("error"), 100)
        message = err or f"{tool} 실행에서 확인이 필요합니다."
    if status == "working" and _age_seconds(path) > STALE_SECONDS:
        status = "stalled"
        message = "최근 도구 실행 후 한동안 갱신이 없습니다. 멈춤 여부를 확인해 주세요."
    return Snapshot(status=status, task=tool, message=message,
                    last_update=str(data.get("timestamp") or _mtime_iso(path)), source=str(path), raw=data)


def load_snapshot(state_dir: Path = DEFAULT_STATE_DIR, diag_dir: Path = DEFAULT_DIAG_DIR) -> Snapshot:
    candidates: List[Snapshot] = []
    for maker in (_snapshot_from_current_status,):
        snap = maker(state_dir)
        if snap:
            candidates.append(snap)
    for maker in (_snapshot_from_agent_loop, _snapshot_from_tool_dispatch):
        snap = maker(diag_dir)
        if snap:
            candidates.append(snap)
    if not candidates:
        return Snapshot()

    def sort_key(snap: Snapshot) -> float:
        try:
            p = Path(snap.source)
            return p.stat().st_mtime
        except Exception:
            return 0.0

    return max(candidates, key=sort_key)


def read_recent_events(state_dir: Path = DEFAULT_STATE_DIR, diag_dir: Path = DEFAULT_DIAG_DIR, limit: int = 18) -> List[str]:
    lines: List[str] = []
    files = [state_dir / "events.ndjson", diag_dir / "tool-dispatch-history.jsonl"]
    for path in files:
        try:
            if not path.exists():
                continue
            raw_lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[-limit:]
            for raw in raw_lines:
                try:
                    item = json.loads(raw)
                except Exception:
                    continue
                ts = _clean_text(item.get("timestamp") or item.get("last_update"), 22)
                name = _clean_text(item.get("kind") or item.get("tool") or item.get("status"), 32)
                ok = item.get("ok")
                prefix = "OK" if ok is True else ("!!" if ok is False else "--")
                msg = _clean_text(item.get("message") or item.get("error") or item.get("root_cause_category"), 90)
                lines.append(f"{ts} {prefix} {name} {msg}".strip())
        except Exception:
            continue
    return lines[-limit:]


class HamsterOverlay:
    def __init__(self, root: Any) -> None:
        import tkinter as tk

        self.tk = tk
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("330x168+40+40")
        self.root.attributes("-topmost", True)
        self.bg = "#ff00ff"
        self.root.configure(bg=self.bg)
        try:
            self.root.overrideredirect(True)
            if platform.system().lower() == "windows":
                self.root.wm_attributes("-transparentcolor", self.bg)
        except Exception:
            pass
        self.canvas = tk.Canvas(root, width=330, height=168, bg=self.bg, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self._drag_x = 0
        self._drag_y = 0
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<Double-Button-1>", self._show_details)
        self.canvas.bind("<Button-3>", self._show_menu)
        self.snapshot = Snapshot()
        self._menu = tk.Menu(root, tearoff=False)
        self._menu.add_command(label="상세 보기", command=self._show_details)
        self._menu.add_command(label="새로고침", command=self._refresh)
        self._menu.add_separator()
        self._menu.add_command(label="닫기", command=root.destroy)
        self._refresh()

    def _start_drag(self, event: Any) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag(self, event: Any) -> None:
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _show_menu(self, event: Any) -> None:
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _refresh(self) -> None:
        self.snapshot = load_snapshot()
        self._draw()
        self.root.after(POLL_MS, self._refresh)

    def _show_details(self, event: Any = None) -> None:
        tk = self.tk
        win = tk.Toplevel(self.root)
        win.title("OpenCodeLIG Hamster - 최근 브리핑")
        win.geometry("720x420")
        win.attributes("-topmost", True)
        text = tk.Text(win, wrap="word")
        text.pack(fill="both", expand=True, padx=10, pady=10)
        snap = load_snapshot()
        detail = [
            f"상태: {STATUS_LABELS.get(snap.status, snap.status)}",
            f"작업: {snap.task or '-'}",
            f"메시지: {snap.message}",
            f"갱신: {snap.last_update or '-'}",
            f"출처: {snap.source or '-'}",
            "",
            "최근 이벤트:",
        ]
        events = read_recent_events()
        detail.extend(events if events else ["- 아직 기록된 이벤트가 없습니다."])
        text.insert("1.0", "\n".join(detail))
        text.configure(state="disabled")

    def _draw(self) -> None:
        c = self.canvas
        c.delete("all")
        status = self.snapshot.status
        label = STATUS_LABELS.get(status, status)
        message = self.snapshot.message
        task = self.snapshot.task

        # Speech bubble.
        self._round_rect(112, 12, 320, 118, 18, fill="#fff9ea", outline="#9a7a52", width=2)
        c.create_polygon(122, 92, 96, 105, 118, 75, fill="#fff9ea", outline="#9a7a52")
        c.create_text(128, 28, anchor="nw", text=label, fill="#5b3a1e", font=("Malgun Gothic", 11, "bold"))
        wrapped = "\n".join(textwrap.wrap(message, width=20))
        c.create_text(128, 52, anchor="nw", text=wrapped, fill="#2f2418", font=("Malgun Gothic", 9))
        if task:
            c.create_text(128, 98, anchor="nw", text=_clean_text(task, 34), fill="#6f675d", font=("Malgun Gothic", 8))

        # Close button.
        c.create_oval(300, 125, 322, 147, fill="#fff9ea", outline="#9a7a52", tags=("close",))
        c.create_text(311, 136, text="x", fill="#5b3a1e", font=("Arial", 10, "bold"), tags=("close",))
        c.tag_bind("close", "<Button-1>", lambda e: self.root.destroy())

        self._draw_hamster(status)

    def _round_rect(self, x1: int, y1: int, x2: int, y2: int, r: int, **kw: Any) -> None:
        c = self.canvas
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
                  x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        c.create_polygon(points, smooth=True, **kw)

    def _draw_hamster(self, status: str) -> None:
        c = self.canvas
        beige = "#d7b38a"
        dark = "#5b3a1e"
        belly = "#f1dfc5"
        blush = "#e8a8a0"

        # Body and ears: beige real-hamster direction, not a copied photo asset.
        c.create_oval(18, 62, 111, 154, fill=beige, outline=dark, width=2)
        c.create_oval(28, 38, 62, 72, fill=beige, outline=dark, width=2)
        c.create_oval(63, 38, 97, 72, fill=beige, outline=dark, width=2)
        c.create_oval(52, 48, 112, 119, fill=beige, outline=dark, width=2)
        c.create_oval(68, 78, 105, 118, fill=belly, outline="")
        c.create_oval(39, 82, 87, 140, fill=belly, outline="")

        # Face.
        if status == "idle":
            c.create_arc(70, 72, 78, 78, start=180, extent=180, style="arc", outline=dark, width=2)
            c.create_arc(91, 72, 99, 78, start=180, extent=180, style="arc", outline=dark, width=2)
            c.create_text(83, 65, text="z", fill=dark, font=("Arial", 9, "bold"))
        else:
            c.create_oval(70, 70, 77, 77, fill=dark, outline=dark)
            c.create_oval(92, 70, 99, 77, fill=dark, outline=dark)
        c.create_oval(82, 81, 90, 88, fill="#8a5a38", outline=dark)
        c.create_line(86, 88, 84, 94, fill=dark, width=1)
        c.create_arc(76, 90, 86, 101, start=200, extent=120, style="arc", outline=dark, width=1)
        c.create_arc(86, 90, 97, 101, start=220, extent=120, style="arc", outline=dark, width=1)
        c.create_oval(58, 84, 69, 94, fill=blush, outline="")
        c.create_oval(99, 84, 110, 94, fill=blush, outline="")

        # Paws.
        c.create_oval(38, 118, 56, 138, fill=beige, outline=dark, width=1)
        c.create_oval(87, 118, 105, 138, fill=beige, outline=dark, width=1)

        if status == "working":
            c.create_rectangle(38, 126, 108, 149, fill="#6e7781", outline=dark, width=2)
            c.create_rectangle(48, 132, 98, 145, fill="#dbeafe", outline="")
            c.create_text(73, 137, text="...", fill=dark, font=("Arial", 10, "bold"))
        elif status == "done":
            c.create_rectangle(43, 112, 94, 149, fill="#ffffff", outline=dark, width=2)
            c.create_line(51, 124, 86, 124, fill="#4d7c0f", width=2)
            c.create_line(51, 134, 80, 134, fill="#4d7c0f", width=2)
        elif status == "needs_user":
            c.create_oval(47, 110, 100, 154, fill="#fff3bf", outline=dark, width=2)
            c.create_text(74, 133, text="!", fill="#a16207", font=("Arial", 24, "bold"))
        elif status == "error":
            c.create_text(72, 130, text="?", fill="#b91c1c", font=("Arial", 24, "bold"))
            c.create_oval(102, 72, 110, 88, fill="#93c5fd", outline="#1d4ed8")
        elif status == "stalled":
            c.create_rectangle(42, 124, 102, 148, fill="#e5e7eb", outline=dark, width=2)
            c.create_text(72, 136, text="STOP", fill="#7f1d1d", font=("Arial", 9, "bold"))


def run_app() -> None:
    import tkinter as tk

    root = tk.Tk()
    HamsterOverlay(root)
    root.mainloop()


if __name__ == "__main__":
    run_app()
