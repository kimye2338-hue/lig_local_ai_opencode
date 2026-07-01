# -*- coding: utf-8 -*-
"""Local single-file HTML dashboard for AgentOps (read-only render).

Reads RUN_STATE / CHECKPOINT / ACTIVE_TASK / TASK_QUEUE / done_log / failure_log
and writes agent_ops/reports/dashboard.html. No external CDN, inline CSS only,
so it opens offline in any browser. Pure render: it never mutates state.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List

from .core import STATE, LOGS, REPORTS, now, read_json, tail_jsonl, is_stop_requested, atomic_write_text
from .queue_manager import load_tasks, summary as queue_summary

_STATUS_CLASS = {
    "pending": "s-pending", "active": "s-active", "done": "s-done",
    "failed": "s-failed", "blocked": "s-blocked",
}

def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))

def _rows_queue(tasks: List[Dict[str, Any]]) -> str:
    if not tasks:
        return '<tr><td colspan="6" class="muted">No tasks.</td></tr>'
    out = []
    for t in sorted(tasks, key=lambda x: (int(x.get("priority", 5)), str(x.get("created_at", "")))):
        cls = _STATUS_CLASS.get(str(t.get("status")), "")
        out.append(
            "<tr>"
            f"<td class='mono'>{_esc(t.get('task_id'))}</td>"
            f"<td>{_esc(t.get('title'))}</td>"
            f"<td>{_esc(t.get('kind'))}</td>"
            f"<td class='{cls}'>{_esc(t.get('status'))}</td>"
            f"<td class='num'>{_esc(t.get('attempt_count'))}</td>"
            f"<td class='num'>{_esc(t.get('priority'))}</td>"
            "</tr>"
        )
    return "\n".join(out)

def _rows_log(rows: List[Any], fields: List[str]) -> str:
    if not rows:
        return f'<tr><td colspan="{len(fields)}" class="muted">None.</td></tr>'
    out = []
    for r in reversed(rows):
        if not isinstance(r, dict):
            r = {"message": r}
        cells = "".join(f"<td>{_esc(r.get(f))}</td>" for f in fields)
        out.append(f"<tr>{cells}</tr>")
    return "\n".join(out)

def build_html() -> str:
    run_state = read_json(STATE / "RUN_STATE.json", {})
    checkpoint = read_json(STATE / "CHECKPOINT.json", {})
    active = read_json(STATE / "ACTIVE_TASK.json", {})
    tasks = load_tasks()
    summary = queue_summary()
    counts = summary.get("counts", {}) or {}
    done = tail_jsonl(LOGS / "done_log.jsonl", 15)
    failures = tail_jsonl(LOGS / "failure_log.jsonl", 15)
    stop = is_stop_requested()

    count_badges = " ".join(
        f'<span class="badge {_STATUS_CLASS.get(k, "")}">{_esc(k)}: {_esc(v)}</span>'
        for k, v in counts.items()
    ) or '<span class="muted">none</span>'

    active_block = (
        f"<b>{_esc(active.get('title'))}</b> "
        f"<span class='mono'>({_esc(active.get('kind'))} / {_esc(active.get('status'))})</span>"
        if active else '<span class="muted">No active task.</span>'
    )

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AgentOps Dashboard</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, "Malgun Gothic", sans-serif;
         margin: 0; background: #0f172a; color: #e2e8f0; }}
  header {{ padding: 16px 24px; background: #1e293b; border-bottom: 1px solid #334155; }}
  h1 {{ font-size: 18px; margin: 0; }}
  .sub {{ color: #94a3b8; font-size: 12px; margin-top: 4px; }}
  main {{ padding: 16px 24px; max-width: 1100px; }}
  section {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
            padding: 12px 16px; margin-bottom: 16px; }}
  h2 {{ font-size: 14px; margin: 0 0 8px; color: #cbd5e1; text-transform: uppercase; letter-spacing: .04em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid #334155; vertical-align: top; }}
  th {{ color: #94a3b8; font-weight: 600; }}
  .mono {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; }}
  .num {{ text-align: right; }}
  .muted {{ color: #64748b; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px;
           font-size: 12px; background: #334155; margin-right: 4px; }}
  .s-pending {{ color: #fbbf24; }} .s-active {{ color: #38bdf8; }}
  .s-done {{ color: #4ade80; }} .s-failed {{ color: #f87171; }} .s-blocked {{ color: #f472b6; }}
  .stop-on {{ color: #f87171; font-weight: 700; }} .stop-off {{ color: #4ade80; }}
</style></head>
<body>
<header>
  <h1>AgentOps Dashboard</h1>
  <div class="sub">Generated {_esc(now())} &middot; run: {_esc(run_state.get('run_id'))} &middot;
    stop flag: <span class="{'stop-on' if stop else 'stop-off'}">{'ON' if stop else 'OFF'}</span></div>
</header>
<main>
  <section>
    <h2>Queue</h2>
    <div>Total {_esc(summary.get('total', 0))} &nbsp; {count_badges}</div>
  </section>
  <section>
    <h2>Active task</h2>
    <div>{active_block}</div>
    <div class="sub">Last checkpoint note: {_esc(checkpoint.get('note'))}</div>
  </section>
  <section>
    <h2>Tasks</h2>
    <table>
      <tr><th>task_id</th><th>title</th><th>kind</th><th>status</th><th class="num">attempts</th><th class="num">prio</th></tr>
      {_rows_queue(tasks)}
    </table>
  </section>
  <section>
    <h2>Recent done</h2>
    <table>
      <tr><th>timestamp</th><th>message</th></tr>
      {_rows_log(done, ["timestamp", "message"])}
    </table>
  </section>
  <section>
    <h2>Recent failures</h2>
    <table>
      <tr><th>timestamp</th><th>type</th><th>source</th></tr>
      {_rows_log(failures, ["timestamp", "type", "source"])}
    </table>
  </section>
</main>
</body></html>
"""

def write_dashboard() -> str:
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "dashboard.html"
    atomic_write_text(out, build_html())
    return str(out)
