# Validation TODO on Windows

These checks could **not** be run in the Linux implementation environment and must
be run on the target Windows 망분리 PC. Everything else was verified on
Python 3.11.15 (see `IMPLEMENTATION_REPORT.md`).

## 1. Windows-only lock liveness path (P0-1)
The `os.name == "nt"` branch (`ctypes.windll.kernel32.OpenProcess` +
`tasklist` fallback) only executes on Windows. On Linux the POSIX branch ran.
```bat
py -3.11 -c "from agent_ops.core import _pid_alive,_lock_is_stale; import os; print('self', _pid_alive(os.getpid())); print('fake', _pid_alive(999999))"
```
Expected: `self True`, `fake False` (or `True` only if PID 999999 really exists —
that just means "do not delete the lock", which is the safe outcome).

## 2. Live OpenCode plugin behavior (P0-2, P1-5) — VERIFY-ON-MACHINE
The TS plugins were transpile-checked with `bun build` but their **runtime** hooks
only fire inside OpenCode. Run review tests **T9** (guard blocks corrupted heredoc
in the autopilot exec path) and **T8** (compaction adds the durable handoff block).
Also confirm both plugins load with no Bun install (zero npm imports).

## 3. Windows launcher form
All commands were run as `python …` on Linux. On Windows confirm the `py -3.11 …`
launcher resolves to Python 3.11 and that `agent_ops\…` backslash paths work
(they do via `pathlib`, but re-confirm on the real shell).

## 4. Console encoding for Korean output
`status --ko` / `fix --ko` print Korean. The runner BATs set `PYTHONUTF8=1` and
`PYTHONIOENCODING=utf-8`; confirm the Korean renders in the actual console code
page. The Markdown artifacts (`agent_ops/reports/STATUS_KO.md`) are UTF-8 and are
the reliable fallback if the console code page mangles output.

## 5. `.bat.txt` → `.bat` rename runners
The one-click runners ship as `.bat.txt` (ASCII-validated). Rename to `.bat` to
execute. Confirm they run init/resume/status and doctor/fix respectively.
