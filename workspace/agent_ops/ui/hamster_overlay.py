# -*- coding: utf-8 -*-
r"""Animated hamster pet overlay for OpenCodeLIG.

Complete version:
- topmost draggable pet window
- speech bubble briefing
- 3-frame animated state sprites
- Windows system tray icon with Show / Hide / Details / Exit
- position save / restore
- double-click details
- right-click menu
- no external Python dependencies required for tray; tray uses stdlib ctypes on Windows

State sources:
1. %LIG_STATE_DIR%\\current_status.json
2. %LIG_DIAG_DIR%\\agent-loop-last.json
3. %LIG_DIAG_DIR%\\tool-dispatch-last.json
"""
from __future__ import annotations

import ctypes
import json
import os
import platform
import textwrap
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import SimpleQueue, Empty
from typing import Any, Dict, List, Optional

APP_NAME = "OpenCodeLIG Hamster Pet"
INSTALL_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_USERDATA = INSTALL_ROOT / "userdata"
DEFAULT_STATE_DIR = Path(os.environ.get("LIG_STATE_DIR") or (DEFAULT_USERDATA / "state"))
DEFAULT_DIAG_DIR = Path(os.environ.get("LIG_DIAG_DIR") or (DEFAULT_USERDATA / "diagnostics"))
STALE_SECONDS = int(os.environ.get("LIG_HAMSTER_STALE_SECONDS") or "900")
POLL_MS = int(os.environ.get("LIG_HAMSTER_POLL_MS") or "1000")
ANIM_MS = int(os.environ.get("LIG_HAMSTER_ANIM_MS") or "210")
WATCH_PROCESS = (os.environ.get("LIG_HAMSTER_WATCH_PROCESS") or "opencode.exe").strip()
ASSET_DIR = Path(__file__).resolve().parent / "assets" / "hamster_pet"
ICON_PATH = ASSET_DIR / "hamster_pet.ico"
SETTINGS_PATH = DEFAULT_STATE_DIR / "hamster_pet_settings.json"

STATUS_LABELS = {
    "idle": "대기 중",
    "working": "작업 중...",
    "done": "완료",
    "needs_user": "확인 필요",
    "error": "오류 발생",
    "stalled": "멈춤 의심",
}
ATTENTION_STATES = {"done", "needs_user", "error", "stalled"}
FRAME_STATES = ("idle", "working", "done", "needs_user", "error", "stalled")


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


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


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
    if status not in FRAME_STATES:
        status = "working"
    task = _clean_text(data.get("task"), 64)
    message = _clean_text(data.get("message"), 150) or STATUS_LABELS.get(status, status)
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
        message = _clean_text(data.get("final_content"), 130) or "작업이 완료되었습니다."
    elif outcome in {"llm_failed", "tool_loop_cutoff", "max_turns_exceeded"}:
        status = "needs_user" if outcome in {"tool_loop_cutoff", "max_turns_exceeded"} else "error"
        message = {
            "llm_failed": "LLM 호출이 실패했습니다. 설정 또는 네트워크를 확인해야 합니다.",
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
    snap = _snapshot_from_current_status(state_dir)
    if snap:
        candidates.append(snap)
    for maker in (_snapshot_from_agent_loop, _snapshot_from_tool_dispatch):
        snap = maker(diag_dir)
        if snap:
            candidates.append(snap)
    if not candidates:
        return Snapshot()

    def sort_key(s: Snapshot) -> float:
        try:
            return Path(s.source).stat().st_mtime
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

def _opencode_running() -> bool:
    try:
        import subprocess
        cp = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {WATCH_PROCESS}"], capture_output=True, text=True, timeout=4)
        return WATCH_PROCESS.lower() in (cp.stdout or "").lower()
    except Exception:
        return True


def _default_geometry(width: int = 245, height: int = 245) -> str:
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.destroy()
        x = max(8, sw - width - 28)
        y = max(8, sh - height - 68)
        return f"{width}x{height}+{x}+{y}"
    except Exception:
        return f"{width}x{height}+60+60"



class SpriteSet:
    def __init__(self, tk_mod: Any) -> None:
        self.tk = tk_mod
        self.frames: Dict[str, List[Any]] = {}
        self._load()

    def _load(self) -> None:
        missing: List[str] = []
        for state in FRAME_STATES:
            frames: List[Any] = []
            paths = sorted(
                ASSET_DIR.glob(f"{state}_*.png"),
                key=lambda p: int(p.stem.split("_")[-1]) if p.stem.split("_")[-1].isdigit() else 9999,
            )
            if not paths:
                missing.append(str(ASSET_DIR / f"{state}_0.png"))
                continue
            for path in paths:
                frames.append(self.tk.PhotoImage(file=str(path)))
            self.frames[state] = frames
        if "idle" not in self.frames:
            self.frames["idle"] = self.frames.get("done") or self.frames.get("stalled") or []
        if missing and not self.frames.get("idle"):
            raise FileNotFoundError("Hamster frame assets missing: " + ", ".join(missing[:3]))

    def count(self, state: str) -> int:
        state = state if state in self.frames else "idle"
        frames = self.frames.get(state) or self.frames.get("idle") or []
        return len(frames)

    def get(self, state: str, index: int) -> Any:
        state = state if state in self.frames else "idle"
        frames = self.frames.get(state) or self.frames.get("idle") or []
        if not frames:
            raise RuntimeError("No hamster frames loaded")
        return frames[index % len(frames)]


class WindowsTrayIcon:
    """Small stdlib Windows tray icon. No pystray/pywin32 dependency."""

    def __init__(self, queue: SimpleQueue) -> None:
        self.queue = queue
        self.available = False
        self._thread: Optional[threading.Thread] = None
        self._hwnd = None
        self._nid = None
        self._class_atom = None
        self._run = True
        self._start()

    def _start(self) -> None:
        if platform.system().lower() != "windows" or not ICON_PATH.exists():
            return
        self._thread = threading.Thread(target=self._run_thread, daemon=True)
        self._thread.start()
        time.sleep(0.2)

    def _run_thread(self) -> None:
        try:
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            shell32 = ctypes.windll.shell32
            kernel32 = ctypes.windll.kernel32

            WM_DESTROY = 0x0002
            WM_COMMAND = 0x0111
            WM_USER = 0x0400
            WM_TRAY = WM_USER + 20
            WM_RBUTTONUP = 0x0205
            WM_LBUTTONDBLCLK = 0x0203
            NIF_MESSAGE = 0x00000001
            NIF_ICON = 0x00000002
            NIF_TIP = 0x00000004
            NIM_ADD = 0x00000000
            NIM_MODIFY = 0x00000001
            NIM_DELETE = 0x00000002
            NIM_SETVERSION = 0x00000004
            NOTIFYICON_VERSION_4 = 4
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x00000010
            TPM_RETURNCMD = 0x0100
            TPM_RIGHTBUTTON = 0x0002
            MF_STRING = 0x0000
            MF_SEPARATOR = 0x0800

            CMD_SHOW = 1001
            CMD_HIDE = 1002
            CMD_DETAILS = 1003
            CMD_EXIT = 1004

            WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

            class WNDCLASS(ctypes.Structure):
                _fields_ = [
                    ("style", wintypes.UINT),
                    ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HCURSOR),
                    ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR),
                    ("lpszClassName", wintypes.LPCWSTR),
                ]

            class NOTIFYICONDATA(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("hWnd", wintypes.HWND),
                    ("uID", wintypes.UINT),
                    ("uFlags", wintypes.UINT),
                    ("uCallbackMessage", wintypes.UINT),
                    ("hIcon", wintypes.HICON),
                    ("szTip", wintypes.WCHAR * 128),
                    ("dwState", wintypes.DWORD),
                    ("dwStateMask", wintypes.DWORD),
                    ("szInfo", wintypes.WCHAR * 256),
                    ("uTimeoutOrVersion", wintypes.UINT),
                    ("szInfoTitle", wintypes.WCHAR * 64),
                    ("dwInfoFlags", wintypes.DWORD),
                    ("guidItem", ctypes.c_byte * 16),
                    ("hBalloonIcon", wintypes.HICON),
                ]

            class POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

            def wnd_proc(hwnd, msg, wparam, lparam):
                if msg == WM_TRAY:
                    if int(lparam) == WM_RBUTTONUP:
                        self._show_menu(hwnd, user32, int(wparam), CMD_SHOW, CMD_HIDE, CMD_DETAILS, CMD_EXIT,
                                        TPM_RETURNCMD, TPM_RIGHTBUTTON, MF_STRING, MF_SEPARATOR)
                    elif int(lparam) == WM_LBUTTONDBLCLK:
                        self.queue.put("toggle")
                    return 0
                if msg == WM_COMMAND:
                    cmd = int(wparam) & 0xffff
                    if cmd == CMD_SHOW:
                        self.queue.put("show")
                    elif cmd == CMD_HIDE:
                        self.queue.put("hide")
                    elif cmd == CMD_DETAILS:
                        self.queue.put("details")
                    elif cmd == CMD_EXIT:
                        self.queue.put("exit")
                    return 0
                if msg == WM_DESTROY:
                    user32.PostQuitMessage(0)
                    return 0
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            self._wnd_proc = WNDPROC(wnd_proc)  # keep ref
            hinst = kernel32.GetModuleHandleW(None)
            class_name = "OpenCodeLIGHamsterPetTrayWindow"
            wc = WNDCLASS()
            wc.lpfnWndProc = self._wnd_proc
            wc.hInstance = hinst
            wc.lpszClassName = class_name
            self._class_atom = user32.RegisterClassW(ctypes.byref(wc))
            hwnd = user32.CreateWindowExW(0, class_name, APP_NAME, 0, 0, 0, 0, 0, None, None, hinst, None)
            self._hwnd = hwnd

            hicon = user32.LoadImageW(None, str(ICON_PATH), IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
            nid = NOTIFYICONDATA()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
            nid.hWnd = hwnd
            nid.uID = 1
            nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
            nid.uCallbackMessage = WM_TRAY
            nid.hIcon = hicon
            nid.szTip = APP_NAME
            nid.uTimeoutOrVersion = NOTIFYICON_VERSION_4
            if shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
                shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(nid))
                self._nid = nid
                self.available = True

            msg = wintypes.MSG()
            while self._run and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            if self._nid is not None:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
        except Exception:
            self.available = False

    def _show_menu(self, hwnd, user32, uid, CMD_SHOW, CMD_HIDE, CMD_DETAILS, CMD_EXIT,
                   TPM_RETURNCMD, TPM_RIGHTBUTTON, MF_STRING, MF_SEPARATOR) -> None:
        from ctypes import wintypes
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, CMD_SHOW, "Show")
        user32.AppendMenuW(menu, MF_STRING, CMD_HIDE, "Hide")
        user32.AppendMenuW(menu, MF_STRING, CMD_DETAILS, "Details")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, CMD_EXIT, "Exit")
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(hwnd)
        cmd = user32.TrackPopupMenu(menu, TPM_RETURNCMD | TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
        if cmd:
            user32.PostMessageW(hwnd, 0x0111, cmd, 0)
        user32.DestroyMenu(menu)

    def stop(self) -> None:
        self._run = False
        try:
            if self._hwnd:
                ctypes.windll.user32.PostMessageW(self._hwnd, 0x0010, 0, 0)
        except Exception:
            pass


class HamsterPetOverlay:
    def __init__(self, root: Any) -> None:
        import tkinter as tk

        self.tk = tk
        self.root = root
        self.root.title(APP_NAME)
        self.bg = "#ff00ff"
        self.root.configure(bg=self.bg)
        self.root.attributes("-topmost", True)
        try:
            self.root.overrideredirect(True)
            if platform.system().lower() == "windows":
                self.root.wm_attributes("-transparentcolor", self.bg)
        except Exception:
            pass

        settings = _read_json(SETTINGS_PATH) or {}
        geom = settings.get("geometry")
        if not geom:
            try:
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                x = max(8, sw - 245 - 28)
                y = max(8, sh - 245 - 68)
                geom = f"245x245+{x}+{y}"
            except Exception:
                geom = "245x245+60+60"
        self.root.geometry(str(geom))

        self.queue: SimpleQueue = SimpleQueue()
        self.tray = WindowsTrayIcon(self.queue)

        self.canvas = tk.Canvas(root, width=245, height=245, bg=self.bg, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.sprites = SpriteSet(tk)
        self.snapshot = Snapshot()
        self.frame_index = 0
        self.frame_step = 1
        self._last_status = ""
        self._last_attention_key = ""
        self._drag_x = 0
        self._drag_y = 0
        self._visible = True
        self._process_absence = 0
        self._started_at = time.time()

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._save_position)
        self.canvas.bind("<Double-Button-1>", self._show_details)
        self.canvas.bind("<Button-3>", self._show_menu)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        self._menu = tk.Menu(root, tearoff=False)
        self._menu.add_command(label="상세 보기", command=self._show_details)
        self._menu.add_command(label="보이기", command=self.show)
        self._menu.add_command(label="숨기기", command=self.hide)
        self._menu.add_command(label="새로고침", command=self.refresh_once)
        self._menu.add_separator()
        self._menu.add_command(label="종료", command=self.exit_app)

        self.refresh_once()
        self._animate()
        self._process_queue()
        self._watch_process()

    def _start_drag(self, event: Any) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag(self, event: Any) -> None:
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _save_position(self, event: Any = None) -> None:
        _write_json(SETTINGS_PATH, {"geometry": self.root.geometry(), "updated": datetime.now().astimezone().isoformat(timespec="seconds")})

    def _show_menu(self, event: Any) -> None:
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _process_queue(self) -> None:
        while True:
            try:
                cmd = self.queue.get_nowait()
            except Empty:
                break
            if cmd == "show":
                self.show()
            elif cmd == "hide":
                self.hide()
            elif cmd == "toggle":
                self.toggle_visibility()
            elif cmd == "details":
                self._show_details()
            elif cmd == "exit":
                self.exit_app()
        self.root.after(250, self._process_queue)

    def toggle_visibility(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()

    def show(self) -> None:
        self._visible = True
        self._process_absence = 0
        self._started_at = time.time()
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)

    def hide(self) -> None:
        self._visible = False
        self.root.withdraw()

    def exit_app(self) -> None:
        self._save_position()
        try:
            self.tray.stop()
        finally:
            self.root.destroy()

    def refresh_once(self) -> None:
        old_status = self.snapshot.status
        self.snapshot = load_snapshot()
        if self.snapshot.status != old_status:
            self.frame_index = 0
            self.frame_step = 1
            self.frame_step = 1
        attention_key = f"{self.snapshot.status}:{self.snapshot.last_update}:{self.snapshot.message}"
        if self.snapshot.status in ATTENTION_STATES and attention_key != self._last_attention_key:
            self._last_attention_key = attention_key
            if not self._visible:
                self.show()
        self._draw()
        self.root.after(POLL_MS, self.refresh_once)

    def _watch_process(self) -> None:
        if WATCH_PROCESS:
            if _opencode_running():
                self._process_absence = 0
            else:
                self._process_absence += 1
                # Run launcher starts the pet just before OpenCode.
                # Give OpenCode enough time to appear before auto-exiting the pet.
                if time.time() - self._started_at > 20 and self._process_absence >= 4:
                    self.exit_app()
                    return
        self.root.after(1500, self._watch_process)

    def _show_details(self, event: Any = None) -> None:
        tk = self.tk
        win = tk.Toplevel(self.root)
        win.title("OpenCodeLIG Hamster Pet - 최근 브리핑")
        win.geometry("780x470")
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
            f"트레이: {'enabled' if self.tray.available else 'disabled'}",
            "",
            "최근 이벤트:",
        ]
        events = read_recent_events()
        detail.extend(events if events else ["- 아직 기록된 이벤트가 없습니다."])
        text.insert("1.0", "\n".join(detail))
        text.configure(state="disabled")

    def _animate(self) -> None:
        count = max(1, self.sprites.count(self.snapshot.status))
        if count <= 1:
            self.frame_index = 0
        elif count == 2:
            self.frame_index = 1 - self.frame_index
        else:
            nxt = self.frame_index + self.frame_step
            if nxt >= count or nxt < 0:
                self.frame_step *= -1
                nxt = self.frame_index + self.frame_step
            self.frame_index = nxt
        self._draw()
        self.root.after(ANIM_MS, self._animate)

    def _draw(self) -> None:
        c = self.canvas
        c.delete("all")
        status = self.snapshot.status
        label = STATUS_LABELS.get(status, status)

        # Speech bubble removed. This is a compact sticker-style pet:
        # status text above, hamster animation below.
        self._draw_status_header(status, label)

        image = self.sprites.get(status, self.frame_index)
        c.create_image(122, 142, image=image)
        c.image_ref = image

        # Small hide button. Close means hide, not exit.
        c.create_oval(216, 10, 240, 34, fill="#ffffff", outline="#d6c1a1", width=2, tags=("hide",))
        c.create_text(228, 21, text="×", fill="#5f4525", font=("Arial", 12, "bold"), tags=("hide",))
        c.tag_bind("hide", "<Button-1>", lambda e: self.hide())

    def _draw_status_header(self, status: str, label: str) -> None:
        c = self.canvas
        center_x = 122
        y = 26
        icon_x = center_x - 58

        # Original-sheet-like bold title with white outline.
        for dx, dy in [(-2,0),(2,0),(0,-2),(0,2),(-1,-1),(1,1)]:
            c.create_text(center_x + dx + 10, y + dy, text=label, fill="#ffffff", font=("Malgun Gothic", 18, "bold"))
        c.create_text(center_x + 10, y, text=label, fill="#111111", font=("Malgun Gothic", 18, "bold"))

        if status == "done":
            self._round_rect(icon_x-15, y-15, icon_x+15, y+15, 6, fill="#22c55e", outline="#15803d", width=2)
            c.create_line(icon_x-8, y, icon_x-2, y+7, icon_x+10, y-8, fill="#ffffff", width=4, smooth=True)
        elif status == "needs_user":
            c.create_polygon(icon_x, y-17, icon_x-17, y+14, icon_x+17, y+14, fill="#facc15", outline="#ca8a04", width=2)
            c.create_text(icon_x, y+1, text="!", fill="#111111", font=("Arial", 18, "bold"))
        elif status == "working":
            c.create_oval(icon_x-14, y-14, icon_x+14, y+14, fill="#3b82f6", outline="#1d4ed8", width=2)
            for i in range(3):
                fill = "#ffffff" if (self.frame_index + i) % 3 == 0 else "#bfdbfe"
                c.create_oval(icon_x-8 + i*8, y-2, icon_x-3 + i*8, y+3, fill=fill, outline="")
        elif status == "error":
            c.create_polygon(icon_x, y-17, icon_x-17, y+14, icon_x+17, y+14, fill="#fbbf24", outline="#b45309", width=2)
            c.create_text(icon_x, y+1, text="!", fill="#7f1d1d", font=("Arial", 18, "bold"))
        elif status == "stalled":
            points = [
                icon_x-10, y-16, icon_x+10, y-16, icon_x+17, y-9, icon_x+17, y+9,
                icon_x+10, y+16, icon_x-10, y+16, icon_x-17, y+9, icon_x-17, y-9,
            ]
            c.create_polygon(points, fill="#ef4444", outline="#991b1b", width=2)
            c.create_text(icon_x, y, text="STOP", fill="#ffffff", font=("Arial", 6, "bold"))
        else:
            c.create_oval(icon_x-13, y-13, icon_x+13, y+13, fill="#9ca3af", outline="#4b5563", width=2)
            c.create_text(icon_x, y, text="Z", fill="#ffffff", font=("Arial", 11, "bold"))

    def _round_rect(self, x1: int, y1: int, x2: int, y2: int, r: int, **kw: Any) -> None:
        c = self.canvas
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
                  x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        c.create_polygon(points, smooth=True, **kw)


def run_app() -> None:
    import tkinter as tk
    if platform.system().lower() == "windows":
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "OpenCodeLIG_Hamster_Pet_Mutex")
        if ctypes.windll.kernel32.GetLastError() == 183:
            return
    root = tk.Tk()
    HamsterPetOverlay(root)
    root.mainloop()


if __name__ == "__main__":
    run_app()
