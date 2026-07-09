# -*- coding: utf-8 -*-
"""OpenCode memory injection plugin structure checks.

WS-3 마지막 조각: TUI compaction 요약이 장기기억을 오염시키지 않는지 검증.
- memory-inject.ts 의 compaction 훅이 더 이상 `remember`(preference/high/user)를
  쓰지 않고 `log-activity`(activity/low/agent + 같은날 같은제목 1회 캡)를 쓴다.
- agentops.py `log-activity` CLI 는 tmp 격리(AGENTOPS_MEMORY_DIR)로 실검증 —
  실제 USERDATA 미접촉. TS 는 Node 실행 없이 문자열/정규식으로 정적 검증.

Run: py -3.11 tests\test_memory_inject_plugin.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
PLUGIN = WS / ".opencode" / "plugins" / "memory-inject.ts"
START = WS / ".opencode" / "commands" / "start.md"
AGENT = WS / ".opencode" / "agents" / "agent.md"
PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def run_cli(env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(WS / "agent_ops" / "agentops.py"), *args],
        cwd=str(WS), env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=120)


def main() -> None:
    text = PLUGIN.read_text(encoding="utf-8")
    start = START.read_text(encoding="utf-8")
    agent = AGENT.read_text(encoding="utf-8")

    # --- 플러그인 구조(기존 계약 유지) ---
    check("memory plugin exists", PLUGIN.exists())
    check("plugin is node-parseable JS syntax",
          subprocess.run(["node", "--check", str(PLUGIN)], cwd=WS).returncode == 0)
    check("plugin prefers AGENTOPS_HOME", "process.env.AGENTOPS_HOME" in text)
    check("plugin calls recall pinned", '["recall", "--pinned"]' in text)
    check("plugin writes SESSION_RECALL fallback", "SESSION_RECALL.md" in text)
    check("plugin injects during compaction",
          "experimental.session.compacting" in text and "pushContext" in text)
    check("/start runs recall pinned first",
          "python agent_ops/agentops.py recall --pinned" in start)
    check("agent instructions mention SESSION_RECALL fallback", "SESSION_RECALL.md" in agent)
    check("agent instructions ask to remember useful lesson", "agentops.py remember" in agent)

    # --- compaction 요약은 remember(규칙) 아닌 log-activity(활동)로 ---
    check("compaction path no longer calls remember CLI",
          '"remember"' not in text and "'remember'" not in text
          and "rememberCompaction" not in text)
    check("compaction records via log-activity",
          re.search(r'runAgentOpsAsync\(\s*base,\s*\[\s*"log-activity"', text) is not None)
    check("pinned recall refresh is asynchronous",
          "execFileSync" not in text and "runAgentOpsAsync" in text)
    check("fixed title enables same-day dedupe", '"OpenCode TUI 세션 요약"' in text)
    check("compacting hook calls logCompactionActivity",
          re.search(r'session\.compacting[\s\S]{0,400}logCompactionActivity\(', text) is not None)
    check("summary length cap retained", "MAX_SUMMARY_CHARS = 1200" in text
          and "MAX_SUMMARY_CHARS" in text.split("function compactSummary", 1)[1])

    # --- agentops.py log-activity CLI 실검증 (tmp 격리, USERDATA 미접촉) ---
    tmp = Path(tempfile.mkdtemp(prefix="memplugin_"))
    env = dict(os.environ)
    env.update({
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "AGENTOPS_ROOT": str(tmp / "workspace"),
        "AGENTOPS_MEMORY_DIR": str(tmp / "memory"),
        "LIG_DIAG_DIR": str(tmp / "diag"),
    })
    mem_jsonl = tmp / "memory" / "memory.jsonl"

    cp = run_cli(env, "log-activity", "compaction 요약 본문 1", "--title", "OpenCode TUI 세션 요약")
    check("log-activity exits 0", cp.returncode == 0, (cp.stderr or "")[:300])
    out = json.loads(cp.stdout)
    check("log-activity reports activity logged",
          out.get("logged") is True and out.get("kind") == "activity", cp.stdout[:300])

    rows = [json.loads(l) for l in mem_jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    acts = [r for r in rows if r.get("kind") == "activity"]
    check("exactly one activity stored", len(acts) == 1, str(len(acts)))
    a = acts[0]
    check("stored as low priority agent activity (no rule pollution)",
          a.get("priority") == "low" and a.get("source") == "agent",
          json.dumps(a, ensure_ascii=False)[:200])
    check("no preference(high/user) created",
          not any(r.get("kind") == "preference" for r in rows))
    check("summary body stored", "compaction 요약 본문 1" in str(a.get("body", "")),
          str(a.get("body"))[:200])

    # 같은 날 같은 title 재호출 → add_activity 일 1회 캡으로 중복 미적재
    cp2 = run_cli(env, "log-activity", "compaction 요약 본문 2 (다른 내용)",
                  "--title", "OpenCode TUI 세션 요약")
    check("second call still exits 0 (never breaks chat path)",
          cp2.returncode == 0, (cp2.stderr or "")[:300])
    rows2 = [json.loads(l) for l in mem_jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    acts2 = [r for r in rows2 if r.get("kind") == "activity"]
    check("same-day same-title deduped", len(acts2) == 1, str(len(acts2)))

    # 빈 텍스트는 거부(적재 없음)
    cp3 = run_cli(env, "log-activity", "--title", "OpenCode TUI 세션 요약")
    check("empty text rejected", cp3.returncode == 2, str(cp3.returncode))

    print(f"\nALL {PASS} CHECKS PASSED (memory inject plugin)")


if __name__ == "__main__":
    main()
