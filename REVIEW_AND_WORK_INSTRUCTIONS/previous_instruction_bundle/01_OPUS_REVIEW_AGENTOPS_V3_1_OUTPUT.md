# Opus Senior Review — OpenCode AgentOps v3.1 (Co-Growth + UX snapshot)

Reviewer role: senior OpenCode / agentic-tooling / Windows-automation architect.
Scope: correctness, OpenCode compatibility, safety, parallelism, memory, installer, and user-visible product quality.
Target implementers: Sonnet / GPT-5 / GPT-5 mini / internal company LLM (weaker than Opus). Every fix below is written to be executed without guessing.

All OpenCode-specific claims in this review were verified against the **current official docs** (opencode.ai/docs, fetched at review time), not from memory. Where a claim still depends on your exact installed build, it is marked **VERIFY-ON-MACHINE** with the exact command to run.

---

## 0. Verified OpenCode facts this review relies on

These corrected several assumptions. Read them first — some "obvious bugs" are actually fine, and some "fine" code is actually broken.

| # | Fact (from official docs) | Consequence for this package |
|---|---|---|
| F1 | Plugin local dir is **`.opencode/plugins/`** (plural). | Your `.opencode/plugins/compaction-handoff.ts` path is **CORRECT**. Do not "fix" it to singular. |
| F2 | Compaction hook is `experimental.session.compacting`; inject via `output.context.push(...)` (additive) **or** `output.prompt = ...` (full replace). | Your hook is structurally valid. Setting `output.prompt` works but *replaces* the whole summary instruction. Prefer `output.context.push`. |
| F3 | `bash` permission **matches the parsed command string**; wildcards are *simple* (`*`=any run of chars, `?`=one). Rules evaluated in order, **last matching rule wins**. | Your autopilot deny rules DO fire, but only as start-anchored string globs. Compound/space-variant commands evade them. The Python guard is stronger but is **not** in the exec path. |
| F4 | The 15 permission keys are: read, edit, glob, grep, list, bash, task, external_directory, todowrite, question, webfetch, websearch, lsp, **doom_loop**, skill. | `doom_loop: deny` is **VALID**, not a dead key. `external_directory: deny` is valid. **There is no `write`/`apply_patch`/`patch` key** — all file writes gate under `edit`. |
| F5 | Command frontmatter keys include `agent`, `subtask`, `model`, `description`, `template`. | Your `subtask: false` + `agent: <name>` in command files is **VALID**. |
| F6 | `tool.execute.before(input, output)` fires before any tool runs; throwing an Error blocks it. For bash, `output.args.command` is the command; for `apply_patch`, check `input.tool === "apply_patch"` and use `output.args.patchText`. | **This is the correct home for the command guard.** It is the only way to truly intercept corrupted approval-window commands. |
| F7 | Local plugins that import npm packages need `.opencode/package.json` + Bun `bun install` at startup (online). Plugins with **zero imports** load with no install step. | On an offline 망분리 PC, the plugin MUST have **no npm imports**. Your current plugin imports only `fs` (Node built-in) — OK. Keep it that way. |
| F8 | Primary agents are cycled with **Tab** (or `switch_agent` keybind). There is **no built-in session-level permission-mode toggle** separate from agent. | Claude-Code-style mode cycling (plan/normal/auto) is **not** available without an OpenCode source patch or a plugin-driven approximation. |

---

## 1. Executive verdict

**Is v3.1 ready to install? — NO. Install is blocked by 4 P0 issues.**

The architecture is sound and genuinely thoughtful: durable state, interruption recovery, external-orchestrator separation, memory recall injection, and a strong command-corruption *detector*. The Python is clean and mostly cross-platform-aware (atomic writes, UTF-8 IO, ASCII BAT). The OpenCode frontmatter is **more correct than the prior limitations doc feared** (plugin path, `doom_loop`, `subtask`, command `agent` are all valid).

But four things will bite a real Windows internal-network user on day one:

- **P0-1 — `file_lock()` is broken on Windows.** `os.open(..., O_CREAT|O_EXCL|O_WRONLY)` works, but stale-lock recovery calls `os.kill(pid, 0)` to test liveness. On Windows, `os.kill` cannot send signal 0 to an arbitrary PID the way POSIX does; for a foreign PID it typically raises `OSError`/`PermissionError`, so `_pid_alive` returns the wrong answer and the queue lock can deadlock for 15 min or wrongly delete a live lock. The queue is the spine of the whole runtime.
- **P0-2 — The command guard is NOT in the execution path.** It's a manual CLI. The thing the user is most afraid of — a corrupted `cat > … << EOF` approval window auto-running — is only blocked by OpenCode's weaker permission globs, which the same prose-corrupted command can evade (compound commands, whitespace variants, non-listed extensions). The strong detector exists but never runs automatically.
- **P0-3 — Parallel orchestrator corrupts shared state and can double-run tasks.** `run_task()` runs in N threads and each calls `set_active_task()` + `update_checkpoint()`, which overwrite the *same* single files `ACTIVE_TASK.json` / `CHECKPOINT.json` with no lock → last-writer-wins garbage. Also `get_next_batch()` selects pending tasks but the "claim" (`mark_task_running`) happens later inside each worker, so overlapping batches/interruptions can dispatch the same task twice.
- **P0-4 — `is_configured()` blocks the company LLM gateway.** It requires a non-empty `api_key`. Network-separated internal gateways (your EXAONE/Qwen setup) frequently need **no key**. As written, every `llm_plan` task returns `LLM_NOT_CONFIGURED` on the exact environment this is built for. `chat()` also assumes a perfectly OpenAI-shaped `choices[0].message.content`, which the prompt itself warns may not hold.

Fix those four and it is installable. Everything else is P1/P2 hardening and UX.

---

## 2. P0 / P1 / P2 issue table

### P0 — must fix before install

| ID | File | Problem | Why it matters | Exact fix (summary; full patch in §3) |
|----|------|---------|----------------|----------------------------------------|
| P0-1 | `agent_ops/core.py` `_pid_alive`, `file_lock` | `os.kill(pid,0)` is unreliable on Windows; lock liveness check misfires → 15-min deadlocks or premature lock deletion. | Queue lock guards all task transitions. Wrong answer = stuck or corrupted queue. | Make `_pid_alive` Windows-aware (use `tasklist`/`ctypes.OpenProcess`), and make stale-lock fall back to **timestamp age** when liveness is unknowable. |
| P0-2 | `agent_ops/command_guard.py` (logic) + **new** `.opencode/plugins/command-guard.ts` | Guard logic is correct but only runs when manually invoked. Real exec path is OpenCode's permission globs, which corrupted compound commands can evade. | This is the user's #1 fear (corrupted approval windows auto-running). | Port the guard's block-rules into a `tool.execute.before` plugin that `throw`s on `bash` commands matching the bad patterns. Keep the Python guard as the shared rule source + CLI. |
| P0-3 | `agent_ops/orchestrator.py`, `agent_ops/queue_manager.py` | Threads write shared `ACTIVE_TASK.json`/`CHECKPOINT.json` with no lock; tasks claimed after selection → double-run + state corruption. | Parallel mode is advertised; this silently corrupts state and re-runs work. | Add an atomic **claim** step (`claim_task` under `task_queue` lock). In parallel mode, do **not** write single-file active-task/checkpoint per worker — write per-task result files and update checkpoint only from the main loop. |
| P0-4 | `agent_ops/llm_client.py` | `is_configured()` requires `api_key`; internal gateway often keyless. `chat()` assumes strict OpenAI response shape. | Disables the core co-growth feature on the exact target environment. | Treat `api_key` as optional when an env flag/sentinel is set; send `Authorization` only if a key exists; parse response defensively. |

### P1 — fix soon (correctness / safety / reliability)

| ID | File | Problem | Why it matters | Exact fix |
|----|------|---------|----------------|-----------|
| P1-1 | `agent_ops/queue_manager.py` `mark_task_failed` | Increments nothing; reads `attempt_count` that was already incremented in `mark_task_running`. Off-by-one: on `max_retries=3` it actually allows 3 attempts but the boundary is fragile and depends on call order. | Retry accounting is the difference between "stops sanely" and "retries forever / gives up early". | Make retry decision explicit and order-independent (compare `attempt_count >= max_retries`), and assert `mark_task_running` is the only place that increments. |
| P1-2 | `agent_ops/orchestrator.py` `run_loop_parallel` | A failed task is reset to `pending` (by retry logic) but the batch loop immediately re-selects it next tick with no backoff → tight failure spin. | Burns the internal LLM / CPU; floods logs. | Add per-task `next_retry_at` (timestamp) and skip until elapsed; exponential backoff. |
| P1-3 | `memory_manager.record_success_lesson` + `failures.log_failure` | **Every** success writes a "lesson" and **every** failure writes an `error_pattern` memory. Memory grows unbounded and recall gets noisy fast. | Co-growth becomes co-bloat; recall quality drops; compaction handoff grows. | Gate success-lessons (only record on non-trivial kinds or first-of-kind); dedupe error patterns by type+source within a window; cap memory with archival. |
| P1-4 | `agent_ops/core.py` `validate_written_file` / `safe_file_writer.validate` | `.bat`/`.cmd` ASCII check exists, but BATs ship as `.bat.txt`, so the ASCII gate never runs on the real artifact. | A non-ASCII BAT can slip through as `.bat.txt`, then break on rename. | Add `.bat.txt`/`.cmd.txt` to the ASCII-validated suffixes. |
| P1-5 | `.opencode/plugins/compaction-handoff.ts` | Uses `output.prompt` (full replace) and a **relative** path `agent_ops/state/COMPACT_HANDOFF.md`. If OpenCode's CWD ≠ project root, `readFileSync` silently fails (caught) → empty handoff. | Compaction is the headline durability feature; silent empty handoff defeats it. | Switch to `output.context.push`, resolve path from `directory`/`worktree` context, and log when the file is missing. |
| P1-6 | `agent_ops/safe_file_writer.py` writes `*.bak` beside target | `.bak` files land in the project tree; `opencode.json` watcher ignores `**/*.bak` (good) but they clutter and can be re-read. | Minor mess; can confuse the user and `read` tools. | Write backups under `agent_ops/archive/backups/` (the `core.backup_file` convention) instead of beside the file. |
| P1-7 | `agent_ops/agentops.py` `cmd_status` mutates state | `/status` performs interruption recovery + queue mutation as a side effect. A read-only "what's going on" command shouldn't change task states. | Surprising; a glance at status can silently flip active→pending. | Split: `status` is read-only; recovery happens in `init`/`resume`/orchestrator tick only. |

### P2 — polish / robustness / future-proofing

| ID | File | Problem | Fix |
|----|------|---------|-----|
| P2-1 | `command_guard.py` `SAFE_PREFIXES` | Allows `python agent_ops/agentops.py *` — but `agentops.py orchestrator --parallel` starts a long loop *inside* OpenCode bash, which the rules elsewhere forbid. | Exclude `orchestrator` from the safe-allow prefix; long loops must be launched by the external BAT only. |
| P2-2 | `llm_client.chat` | No retry/timeout-tier; a slow internal model just raises. | Add 1 retry + clearer `LLM_TIMEOUT` failure type. |
| P2-3 | `doctor.py` chromedriver candidates hardcode `Desktop/local_LLM/...` | Fragile personal path. | Move to config-only + env; keep one generic fallback. |
| P2-4 | All agents | No `agentops-autopilot` analog that is *read-only* for safe browsing. | Add a `plan`-like read-only primary for "look but don't touch". |
| P2-5 | `reporter.py` / `agentops.py` | Output is JSON-only; non-developer user sees walls of JSON. | Add Korean plain-text summaries (see UX §, P0 product items). |

---

## 3. Exact patch proposals

Conventions for the implementer: paths are project-root-relative. "Replace function X" means find `def X(` and replace the whole function body up to the next top-level `def`/`@`/EOF. Keep the file's existing imports unless the patch says to add one. After each Python edit run `python -m py_compile <file>`.

### Patch P0-1 — Windows-safe lock liveness (`agent_ops/core.py`)

`READY_FOR_SONNET/GPT5_IMPLEMENTATION`

**Target:** `_pid_alive`, `_lock_is_stale` in `agent_ops/core.py`.
**Current problem:** `os.kill(pid, 0)` is not a reliable liveness probe on Windows for foreign PIDs; it can raise and make a live lock look dead (premature unlink → two processes in the queue) or make a dead lock look alive (15-min deadlock).
**Desired behavior:** On Windows, probe liveness via the OS; if liveness can't be determined, decide staleness purely by timestamp age. Never delete a lock younger than `max_age_seconds` unless the owning PID is *provably* dead.

Replace `_pid_alive` with:

```python
def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # Windows: query the process list. Unknown -> assume alive (safe).
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                # Could be access-denied (alive) or gone. Fall back to tasklist.
                try:
                    out = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                        capture_output=True, text=True, timeout=5,
                    )
                    return str(pid) in (out.stdout or "")
                except Exception:
                    return True  # unknown -> assume alive (do not delete a maybe-live lock)
            try:
                exit_code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == STILL_ACTIVE
                return True
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return True  # unknown -> assume alive
    # POSIX
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False
    except Exception:
        return False
```

Replace `_lock_is_stale` with (only change: when PID liveness is *unknown/alive*, do NOT early-return stale; require timestamp age):

```python
def _lock_is_stale(lock_path: Path, max_age_seconds: int = 900) -> bool:
    try:
        text = read_text(lock_path).strip()
        parts = text.split()
        pid = int(parts[0]) if parts and parts[0].lstrip("-").isdigit() else -1
        timestamp = parts[1] if len(parts) > 1 else ""
        # Provably-dead PID -> stale immediately.
        if pid > 0 and not _pid_alive(pid):
            return True
        # Otherwise decide by age only.
        if timestamp:
            t = datetime.fromisoformat(timestamp)
            age = (datetime.now(t.tzinfo) - t).total_seconds()
            return age > max_age_seconds
        # No timestamp and PID alive/unknown -> not stale yet.
        return False
    except Exception:
        # Unreadable/malformed lock: only treat as stale if it is also old on disk.
        try:
            age = time.time() - lock_path.stat().st_mtime
            return age > max_age_seconds
        except Exception:
            return False
```

**Acceptance test (Windows CMD):**
```bat
py -3.11 -c "from agent_ops.core import _pid_alive,_lock_is_stale; import os; print('self alive', _pid_alive(os.getpid())); print('fake pid alive', _pid_alive(999999))"
```
**Expected:** `self alive True` and `fake pid alive False` (or `True` only if a real process happens to own 999999 — acceptable, it just means "don't delete").

---

### Patch P0-2 — Real command-corruption interception via plugin

`REQUIRES_OPENCODE_SOURCE_PATCH` is **NOT** needed — this is a plugin, `READY_FOR_SONNET/GPT5_IMPLEMENTATION`.

**Target:** new file `.opencode/plugins/command-guard.ts`. Shared rule source stays in `agent_ops/command_guard.py` (logic already verified correct: it blocks the exact corrupted `cat > … << 'EOF' … The content contains … Let's write…` sample with 7 reasons).
**Current problem:** the guard only runs when a human types `python agent_ops/command_guard.py check`. OpenCode's own bash permission globs are weaker (start-anchored, simple wildcards, only the listed file extensions), so a corrupted compound command can still reach the approval modal and be approved.
**Desired behavior:** before *any* bash command executes, run the same block-rules; if it matches, `throw` so OpenCode aborts the tool call and shows the reason. No npm imports (offline-safe, see F7).

Create `.opencode/plugins/command-guard.ts`:

```typescript
// AgentOps command guard — runs in OpenCode's tool execution path.
// No external imports (offline / 망분리 safe).

const PROSE_MARKERS = [
  "the content contains", "let's write", "let's create", "better to use",
  "actually the content", "json error", "manual formatting",
  "use echo for each part", "생략", "하려고", "설명", "대안", "생각",
]

const FAKE_TOOL_MARKERS = [
  'bash {"command"', "functions.bash(", "<tool_call>", '"name":"bash"', '"name": "bash"',
]

const WRITE_CODE = [
  /\bcat\s*>\s*[^&|;]+?\.(py|js|ts|tsx|jsx|bat|cmd|ps1|json|yaml|yml|md)\b/i,
  /\bcat\s+<<\s*['"]?[A-Za-z0-9_]+['"]?/i,
  /<<\s*['"]?EOF['"]?/i,
  /\becho\b.+>\s*[^&|;]+?\.(py|js|ts|tsx|jsx|bat|cmd|ps1|json|yaml|yml|md)\b/i,
  /\bprintf\b.+>\s*[^&|;]+?\.(py|js|ts|tsx|jsx|bat|cmd|ps1|json|yaml|yml|md)\b/i,
  /\bpython(?:3)?\s+-c\b/i,
  /\bpy\s+-3(?:\.\d+)?\s+-c\b/i,
]

const DANGEROUS = [
  /\brm\s+-rf\b/i, /\bdel\s+\/[qsf]\b/i, /\brmdir\s+\/s\b/i,
  /\bformat\s+[A-Za-z]:/i, /\bpowershell\b.+encodedcommand/i,
  /\bcurl\b.+\|\s*(bash|sh|python)/i, /\biwr\b.+\|\s*(iex|powershell)/i,
]

function reasonsFor(cmd: string): string[] {
  const lower = cmd.toLowerCase()
  const reasons: string[] = []
  for (const m of PROSE_MARKERS) if (lower.includes(m)) reasons.push(`prose/reasoning in command: ${m}`)
  for (const m of FAKE_TOOL_MARKERS) if (lower.includes(m.toLowerCase())) reasons.push(`fake tool-call text: ${m}`)
  for (const re of WRITE_CODE) if (re.test(cmd)) reasons.push("heredoc/cat/echo/printf/python -c writes a file; use write/apply_patch/safe_file_writer")
  for (const re of DANGEROUS) if (re.test(cmd)) reasons.push("dangerous destructive shell pattern")
  // unclosed heredoc: delimiter never appears alone on its own line
  const delims = [...cmd.matchAll(/<<\s*['"]?([A-Za-z0-9_]+)['"]?/g)].map(m => m[1])
  for (const d of delims) {
    const own = new RegExp(`(?:^|\\n)${d}\\s*(?:\\n|$)`)
    if (!own.test(cmd)) reasons.push(`heredoc delimiter ${d} not closed on its own line`)
  }
  if ((cmd.match(/"/g)?.length ?? 0) >= 6 && cmd.includes("<<")) reasons.push("many quotes inside heredoc; high escaping-failure risk")
  if (cmd.length > 4000) reasons.push("command too long; split into a real file + verification")
  return reasons
}

export const AgentOpsCommandGuard = async (_ctx: any) => ({
  "tool.execute.before": async (input: any, output: any) => {
    if (input?.tool !== "bash") return
    const cmd = String(output?.args?.command ?? "")
    const reasons = reasonsFor(cmd)
    if (reasons.length > 0) {
      throw new Error(
        "AgentOps command guard BLOCKED this command (corrupted/unsafe).\n- " +
        reasons.join("\n- ") +
        "\nUse OpenCode write / apply_patch, or: python agent_ops/safe_file_writer.py <target> --content-file <staging>."
      )
    }
  },
})
```

**Why a plugin and not just permission globs:** F3 confirms bash globs are start-anchored simple wildcards over the parsed command. `cd x && cat > a.py << EOF` does not start with `cat > `, and `printf ... > a.conf` uses an extension not in the deny list. The plugin runs a regex over the *entire* command and throws, which OpenCode honors (F6). Keep the autopilot deny rules too — defense in depth.

**Acceptance test:** create `.opencode/plugins/__guardtest.md` instructions telling the model to attempt `cd portal_research && cat > runner.py << 'EOF'\nx\nEOF`. Expected: OpenCode reports the thrown guard error and does NOT run it. Negative test: `git status` runs normally.
(Programmatic check of the *rules* is the Python CLI — both share semantics:)
```bat
py -3.11 agent_ops\command_guard.py check "cd x && cat > a.py << 'EOF'"
```
**Expected:** JSON with `"decision": "block"` and at least one reason.

---

### Patch P0-3 — Parallel-safe task claiming + no shared single-file writes from workers

`READY_FOR_SONNET/GPT5_IMPLEMENTATION`

**Targets:** `agent_ops/queue_manager.py` (add `claim_task`), `agent_ops/orchestrator.py` (`run_task`, `run_loop_parallel`).
**Current problem:** (a) batch is selected, then each worker marks running later → the same pending task can be dispatched twice; (b) every worker writes shared `ACTIVE_TASK.json`/`CHECKPOINT.json` with no lock → corruption.
**Desired behavior:** a single atomic compare-and-set claims a task (pending→active) under the `task_queue` lock; only a successful claim runs; workers never touch the single shared active-task/checkpoint files — the main loop updates checkpoint once per tick.

Add to `agent_ops/queue_manager.py`:

```python
def claim_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Atomically move a task pending->active. Returns the task if WE claimed it, else None."""
    with file_lock("task_queue"):
        tasks = load_tasks()
        for idx, task in enumerate(tasks):
            if task.get("task_id") == task_id:
                if task.get("status") != "pending":
                    return None  # someone else took it / not runnable
                attempts = int(task.get("attempt_count") or 0) + 1
                task["status"] = "active"
                task["attempt_count"] = attempts
                task["claimed_at"] = now()
                task["updated_at"] = now()
                tasks[idx] = normalize_task(task)
                save_tasks(tasks)
                return tasks[idx]
        return None
```

In `agent_ops/orchestrator.py`, add a thread-safe variant of the worker that claims first and does not write shared single-file state. Add this function and use it from `run_loop_parallel`:

```python
import threading
_CKPT_LOCK = threading.Lock()

def run_task_parallel(task: Dict[str, Any]) -> Dict[str, Any]:
    from .queue_manager import claim_task, mark_task_done, mark_task_failed
    claimed = claim_task(task["task_id"])
    if not claimed:
        return {"ok": True, "status": "skipped_not_claimed", "task_id": task.get("task_id")}
    task = claimed
    try:
        result = execute_task(task)
        if result.get("ok"):
            mark_task_done(task, result)
            append_done(f"Task done: {task.get('task_id')} {task.get('title')}")
            try:
                record_success_lesson(task, result.get("result", {}))
            except Exception as exc:
                append_jsonl(LOGS / "memory_errors.jsonl", {"timestamp": now(), "error": repr(exc)})
            return {"ok": True, "status": "done", "task": task, "result": result}
        failure = log_failure(str(result.get("error", result)), source="orchestrator", task_id=task.get("task_id", ""))
        mark_task_failed(task, str(result.get("error", result)), failure.get("type", "UNKNOWN"))
        return {"ok": False, "status": "failed", "task": task, "failure": failure}
    except Exception as exc:
        failure = log_failure(repr(exc), source="orchestrator_exception", task_id=task.get("task_id", ""))
        mark_task_failed(task, repr(exc), failure.get("type", "UNKNOWN"))
        return {"ok": False, "status": "exception", "task": task, "failure": failure}
```

Then in `run_loop_parallel`, change the worker submit line from `pool.submit(run_task, task)` to `pool.submit(run_task_parallel, task)`, and **after** the `as_completed` loop, update checkpoint once under the lock:

```python
        with _CKPT_LOCK:
            update_checkpoint("orchestrator parallel batch complete")
```

(Remove the per-worker `set_active_task`/`update_checkpoint` calls from the parallel path; `run_task_parallel` above already omits them. `mark_task_done`/`mark_task_failed`/`claim_task` are all under `file_lock("task_queue")`, so the JSONL queue stays consistent.)

**Acceptance test (Windows):** enqueue 6 trivial tasks, run parallel with workers=3:
```bat
for /L %i in (1,1,6) do py -3.11 agent_ops\agentops.py enqueue "noop %i" --kind memorycheck --priority 5
py -3.11 agent_ops\agentops.py orchestrator --parallel --workers 3 --interval 5
:: let it idle one cycle, then Ctrl-C, then:
py -3.11 agent_ops\agentops.py status
```
**Expected:** each task ends in `done` exactly once (no task with `attempt_count > 1` from double-dispatch); `ACTIVE_TASK.json` is not corrupted; counts in status show 6 done.

---

### Patch P0-4 — Keyless internal-gateway support + defensive response parsing (`agent_ops/llm_client.py`)

`READY_FOR_SONNET/GPT5_IMPLEMENTATION`

**Target:** `is_configured`, `chat` in `agent_ops/llm_client.py`.
**Current problem:** internal 망분리 gateways often need no API key; requiring one disables `llm_plan` entirely. Also `obj["choices"][0]["message"]["content"]` throws on any non-OpenAI-shaped response, which the prompt warns is likely.
**Desired behavior:** if `AGENTOPS_LLM_NO_AUTH=1` (or config `"no_auth": true`), treat config as valid without a key and omit the `Authorization` header; parse the response across the common shapes and never KeyError.

Replace both functions:

```python
def is_configured() -> bool:
    cfg = load_llm_config()
    if not cfg["base_url"] or not cfg["model"]:
        return False
    no_auth = os.environ.get("AGENTOPS_LLM_NO_AUTH", "").strip() in {"1", "true", "yes"} \
        or bool(read_json(CONFIG / "llm_config.json", {}).get("no_auth"))
    return bool(cfg["api_key"]) or no_auth

def chat(messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
    cfg = load_llm_config()
    if not is_configured():
        raise RuntimeError("LLM not configured: set AGENTOPS_LLM_BASE_URL/MODEL (+API_KEY or AGENTOPS_LLM_NO_AUTH=1)")
    url = cfg["base_url"].rstrip("/")
    if not url.endswith("/chat/completions"):
        url = url + "/chat/completions"
    payload = {"model": cfg["model"], "messages": messages, "temperature": temperature}
    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = "Bearer " + cfg["api_key"]
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as r:
            body = r.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(f"LLM request failed: {exc!r}")
    try:
        obj = json.loads(body)
    except Exception:
        return body  # some gateways return raw text
    # OpenAI shape
    try:
        choice = obj["choices"][0]
        msg = choice.get("message") or {}
        if isinstance(msg.get("content"), str):
            return msg["content"]
        if isinstance(choice.get("text"), str):  # legacy completion shape
            return choice["text"]
    except Exception:
        pass
    # Other common shapes
    for key in ("content", "output", "response", "text"):
        if isinstance(obj.get(key), str):
            return obj[key]
    return json.dumps(obj, ensure_ascii=False)  # last resort: don't crash
```

**Acceptance test (no real server needed — just the config gate):**
```bat
set AGENTOPS_LLM_BASE_URL=http://127.0.0.1:1/v1
set AGENTOPS_LLM_MODEL=EXAONE-4.5-33B
set AGENTOPS_LLM_NO_AUTH=1
py -3.11 -c "from agent_ops.llm_client import is_configured; print('configured', is_configured())"
```
**Expected:** `configured True` (previously `False` because no api_key).

---

### Patch P1-1 — Order-independent retry accounting (`agent_ops/queue_manager.py`)

`READY_FOR_SONNET/GPT5_IMPLEMENTATION`

Replace `mark_task_failed`:

```python
def mark_task_failed(task: Dict[str, Any], reason: str, failure_type: str = "UNKNOWN") -> Dict[str, Any]:
    # attempt_count is incremented ONLY by mark_task_running / claim_task.
    attempts = int(task.get("attempt_count") or 0)
    max_retries = int(task.get("max_retries") or DEFAULT_MAX_RETRIES)
    if attempts >= max_retries:
        append_blocker(f"Task failed permanently after {attempts}/{max_retries}: {task.get('task_id')} {task.get('title')} / {failure_type}: {reason}")
        return update_task(task["task_id"], status="failed", last_failure_type=failure_type, blocked_reason=reason) or task
    # schedule a backoff retry (see P1-2)
    import datetime as _dt
    delay = min(600, 15 * (2 ** max(0, attempts - 1)))
    next_at = (_dt.datetime.now().astimezone() + _dt.timedelta(seconds=delay)).isoformat(timespec="seconds")
    return update_task(task["task_id"], status="pending", last_failure_type=failure_type, blocked_reason=reason, next_retry_at=next_at) or task
```

### Patch P1-2 — Retry backoff honored by selection (`agent_ops/queue_manager.py`)

In `get_next_task` and `get_next_batch`, change the candidate filter to skip tasks whose `next_retry_at` is in the future:

```python
def _retry_ready(t: Dict[str, Any]) -> bool:
    nra = t.get("next_retry_at")
    if not nra:
        return True
    try:
        import datetime as _dt
        return _dt.datetime.fromisoformat(str(nra)) <= _dt.datetime.now(_dt.datetime.fromisoformat(str(nra)).tzinfo)
    except Exception:
        return True
```
Then in both selectors replace `t.get("status") == "pending" and dependencies_done(t, tasks)` with
`t.get("status") == "pending" and _retry_ready(t) and dependencies_done(t, tasks)`.

### Patch P1-3 — Memory anti-bloat (`agent_ops/memory_manager.py`, `agent_ops/failures.py`)

`READY_FOR_SONNET/GPT5_IMPLEMENTATION`

(a) In `record_success_lesson`, only record for non-trivial kinds and only once per (kind+title) per day:

```python
def record_success_lesson(task: Dict[str, Any], result: Dict[str, Any]) -> None:
    kind = task.get("kind", "task")
    if kind in {"memorycheck", "report", "verify", "doctor", "reflect"}:
        return  # routine maintenance success is not a lesson
    title = f"Successful task pattern: {kind}"
    today = now()[:10]
    for r in load_memory(status="active"):
        if r.get("title") == title and str(r.get("created_at", ""))[:10] == today:
            return  # already captured today
    body = f"Task `{task.get('task_id')}` ({kind}) succeeded: {task.get('title')}."
    add_memory_event("lesson", title, body, status="active", priority="normal", source="task_success", tags=extract_keywords(task.get("title", "")))
```

(b) In `failures.log_failure`, dedupe error-pattern memory by type within the last N entries instead of always adding:

```python
    # before add_memory_event(...), check recent duplicates:
    recent_types = [r.get("type") for r in tail_jsonl(LOGS / "failure_log.jsonl", 10) if isinstance(r, dict)]
    if recent_types.count(ftype) <= 1:
        add_memory_event(kind="error_pattern", title=f"Failure pattern {ftype}", body=..., ...)
```

(c) Add a hard cap + archive to `add_memory_event` (after `rows.append(item)`):

```python
        MAX_ACTIVE = 500
        active_rows = [r for r in rows if r.get("status") == "active"]
        if len(active_rows) > MAX_ACTIVE:
            overflow = sorted(active_rows, key=lambda r: str(r.get("created_at", "")))[:len(active_rows) - MAX_ACTIVE]
            ids = {r["id"] for r in overflow}
            for r in rows:
                if r.get("id") in ids:
                    r["status"] = "deprecated"
                    r["deprecated_reason"] = "memory cap exceeded; auto-archived"
```

### Patch P1-4 — Validate `.bat.txt` ASCII (`agent_ops/core.py` + `safe_file_writer.py`)

In `validate_written_file` and `safe_file_writer.validate`, change the BAT check to also catch the distributed form:

```python
    name_lower = path.name.lower()
    if path.suffix.lower() in {".bat", ".cmd"} or name_lower.endswith(".bat.txt") or name_lower.endswith(".cmd.txt"):
        try:
            path.read_text(encoding="ascii")
        except Exception:
            info["ok"] = False
            info["errors"].append("bat_cmd_must_be_ascii")
```

### Patch P1-5 — Compaction plugin: additive context + robust path

`READY_FOR_SONNET/GPT5_IMPLEMENTATION` (replace `.opencode/plugins/compaction-handoff.ts`)

```typescript
import { readFileSync } from "fs"
import { join } from "path"

export const CompactionHandoff = async (ctx: any) => ({
  "experimental.session.compacting": async (_input: any, output: any) => {
    const base = ctx?.directory || ctx?.worktree?.path || process.cwd()
    let handoff = ""
    let missing = false
    try {
      handoff = readFileSync(join(base, "agent_ops/state/COMPACT_HANDOFF.md"), "utf-8")
    } catch {
      missing = true
    }
    const block = [
      "## AgentOps durable handoff (preserve across compaction)",
      "After compaction, FIRST read: agent_ops/state/COMPACT_HANDOFF.md, RESUME_PLAN.md, ACTIVE_TASK.json, CHECKPOINT.json.",
      "Items under next_step/queue are PLANNED, not approved. No risk:review_required action without explicit current-session user approval.",
      missing ? "(COMPACT_HANDOFF.md not found at session start — run `python agent_ops/agentops.py checkpoint` early.)" : handoff,
    ].join("\n")
    if (Array.isArray(output?.context)) {
      output.context.push(block)   // additive: preferred (F2)
    } else {
      output.prompt = (output.prompt ? output.prompt + "\n\n" : "") + block
    }
  },
})
```
Why additive: `output.prompt` *replaces* the default summary instruction (F2). Pushing context keeps OpenCode's own summarization and adds your durable block.

### Patch P1-7 — Make `/status` read-only (`agent_ops/agentops.py`)

Move the recovery side effects out of `cmd_status`. Replace the top of `cmd_status` so it only *reports* interruption, and create the recovery inside `cmd_resume`/`init`/orchestrator only:

```python
def cmd_status(args):
    interruption = detect_interruption()   # report only; do NOT consume/recover here
    heartbeat("status")
    data = {
        "timestamp": now(),
        "stop_requested": is_stop_requested(),
        "interruption": interruption,
        "queue": queue_summary(),
        "checkpoint": read_json(STATE / "CHECKPOINT.json", {}),
        "active_task": read_json(STATE / "ACTIVE_TASK.json", {}),
    }
    atomic_write_text(REPORTS / "STATUS.md", "# AgentOps Status\n\n```json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```\n")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0
```
(`cmd_resume` already calls `consume_interruption` + `recover_interrupted_active_tasks` — keep it there.)

---

## 4. Answers to the critical review questions (A–H)

### A. Official OpenCode compatibility — verified

- **`permission:` syntax — VALID.** Object + shorthand both accepted; per-agent merges over global, agent wins (F3, F4).
- **`bash:` glob/precedence — WORKS but weaker than assumed.** Last-matching-rule-wins; your autopilot puts `"*": ask` first then specific allows then specific denies — ordering is correct. BUT simple wildcards + start-anchored parsed-command matching means `"cat > *"`/`"* << *"`/`"*<<*EOF*"` only catch the simple forms. **They are real but not sufficient** → P0-2 plugin is required.
- **`"cat > *": deny` / `"* << *": deny` effective? — Partially.** Effective for commands that *are* `cat > file …` / `… << …` as parsed; evaded by compound commands and spacing. Keep them; add the plugin.
- **`doom_loop: deny` — VALID, not dead (F4).** It fires when the same tool call repeats 3× with identical input; `deny` blocks the loop. Good to keep on autopilot. (Consider `ask` instead of `deny` so the user can override a legitimate repeat.)
- **`subtask: true/false` — VALID command frontmatter (F5).** Your `subtask: false` is correct (runs in the main session, not as a detached subtask).
- **Does `.opencode/plugins/compaction-handoff.ts` load automatically? — YES** if the build supports plugins; plural `plugins/` dir is correct (F1). **VERIFY-ON-MACHINE:** `opencode --version` then check plugin loads (see test plan T7). With zero npm imports it needs no Bun install (F7) — offline-safe.
- **Deprecated `tools:`/nonexistent `patch` tool left? — NO `tools:` frontmatter present** (grep-confirmed). The verifier correctly scans for `patch:`/`tools:`; the real tool is `apply_patch` and writes gate under `edit` (F4). One nit: verifier flags `permission:` missing on `agentops-explorer.md` etc.; confirm each agent has a permission block (they do).
- **Is `agentops-autopilot` primary mode likely to work? — YES as an agent**, but it is NOT a "permission mode" — it's a separate persona you Tab to (F8). It works; it just isn't the Claude-Code toggle the user wants (see C).

### B. Command approval-window corruption — does the guard actually prevent auto-run?

- **Today: NO (not automatically).** The Python guard *detects* the corruption perfectly (verified: the exact sample → `block`, 7 reasons; evasions `cd x && cat>runner.py` and `printf > x.py` also → `block`). But nothing calls it before execution. The only automatic barrier is the autopilot's permission globs, which are weaker.
- **Can it be bypassed via permission matching? — Yes**, by compound/spacing variants and non-listed extensions (`.conf`, `.txt`, `.sh`).
- **Should it be in the bash execution path? — YES.** That is exactly what F6 enables. → Patch P0-2 `tool.execute.before` plugin that `throw`s. This is the single most important safety upgrade in this review.
- **Can OpenCode core be patched for a pre-exec sanitizer? — Not necessary.** The plugin hook *is* the supported pre-exec interception point. A core patch would be redundant and a maintenance burden on an offline PC.
- **Exact approach:** ship `.opencode/plugins/command-guard.ts` (P0-2). Keep `command_guard.py` as the shared rule definition + manual CLI + CI check. Optionally generate the TS rule arrays from the Python lists during install to keep them in sync (P2 nicety).

### C. Claude-Code-like permission UX (mode = plan | normal | auto, hotkey, indicator)

**Verified constraint (F8):** OpenCode has primary-agent cycling on **Tab**, but **no built-in session-level permission-mode toggle independent of agent.** So a true Shift+Tab "cycle permission mode while keeping persona" does **not** exist today.

Two implementable options, in order of effort:

**Option C1 (recommended now) — Three primary agents as "modes" + a status line. `READY_FOR_SONNET`.**
Treat mode as persona since that's what OpenCode supports:
- `agentops-plan` (new, read-only: `edit: deny`, `bash: ask`, no write) = **plan**
- `agentops-supervisor` (existing) = **normal**
- `agentops-autopilot` (existing, guarded) = **auto**

Cycle with **Tab** (built-in). Add a visible indicator by writing the current agent to `agent_ops/state/MODE.txt` from a tiny `event`/`session` plugin hook and surfacing it in `/status`. This is not a perfect Claude-Code clone, but it is robust, offline-safe, and zero-core-patch.

**Option C2 (true toggle) — OpenCode source patch. `REQUIRES_OPENCODE_SOURCE_PATCH` / `NEEDS_OPUS_LEVEL_DESIGN`.**
Only if C1 is insufficient. Conceptual design (must be verified against the build's source layout first — see "what to verify"):
- **State model:** add `session.permissionMode ∈ {plan, normal, auto}` to session state, default `normal`. Persist per session.
- **Keybind/action:** register a `cycle_permission_mode` action bound to e.g. `shift+tab` (confirm it isn't already bound to agent cycle; if it is, pick `ctrl+m`). Action advances the enum and emits a TUI toast + status-bar segment.
- **Permission resolver change:** in the function that resolves a permission decision for a tool call, consult `permissionMode` *before* the per-agent/global rules:
  - `plan` → force `edit`/`bash(write-ish)` to `deny`, everything else `ask`.
  - `normal` → use the existing agent/global rules unchanged.
  - `auto` → upgrade `ask`→`allow` for project-local `edit`/safe `bash`, but **never** override an explicit `deny` and never relax `external_directory`/risky portal rules.
- **Backward compatibility:** when no mode is set or the patch is absent, behavior is identical to today (`normal`). Gate the whole feature behind a config flag `experimental_permission_mode: true`.
- **What must be verified first (and how):** clone the installed version's source; find (a) where keybinds/actions are registered (search the TUI package for the agent-cycle action), (b) the permission resolver entry point (search for where `"ask"|"allow"|"deny"` is computed for a tool). Confirm the resolver is a single chokepoint; if decisions are scattered, C2 is too invasive → stay on C1.

`DO_NOT_IMPLEMENT_YET` for C2 unless the user explicitly wants to maintain a forked OpenCode on the offline PC.

### D. Context preservation / compaction / restart

- **Interruption recovery complete? — Mostly.** Stale-heartbeat detection + active→pending recovery works. Gaps: (1) recovery side effects fire from `/status` (P1-7); (2) `detect_interruption` only triggers for a fixed status set — add `"checkpoint"` to the watched set, since a crash right after a checkpoint leaves status=`checkpoint` and would be missed.
- **Active tasks safely recovered to pending? — Yes**, both via `consume_interruption` (the single ACTIVE_TASK) and `recover_interrupted_active_tasks` (queue sweep). With P0-3's `claim_task`, this is now race-safe.
- **Checkpoint slim enough? — Yes.** `CHECKPOINT.json` stores summaries, not full payloads. Good. Watch `RESUME_PLAN.md`/`COMPACT_HANDOFF.md` growth only if active-task payloads get large; truncate payload in the handoff render if needed.
- **Does compaction hook enforce handoff? — Yes once P1-5 lands** (additive context, robust path). Today it can silently inject empty handoff if CWD≠root.
- **Fallback if plugin hook unsupported?** The `AGENTS.md` block (installer-added) instructs the model to read the handoff files unconditionally at session start — that is the always-on fallback (it's loaded into the system prompt, per the same mechanism other OpenCode memory plugins rely on). Keep both.
- **Tests:** T6, T7 below.

### E. Co-growth / memory

- **Recall scoring useful enough? — Adequate, not great.** Keyword substring + source/priority boosts. Weaknesses: substring matching (`"cat"` matches "concatenate"), no recency decay, no failure→success pairing. → P1-3 stops the bloat; add recency weighting: `score += 1 if created within 7 days`.
- **Injected in the right place? — Yes**, into the `llm_plan` *system* prompt before the user content. Good.
- **Avoids compaction bloat? — Only after P1-3.** Today unbounded.
- **Success-lesson noise? — Yes, significant** (every success). P1-3 gates it.
- **Improve without external packages?** Add (a) recency decay, (b) dedup by normalized title (already partially in `propose_memory_update` — promote it to write-time), (c) a tiny TF-style weight: rarer keywords score higher. All pure-Python.
- **Reflection (repeated failures → generalized rule)?** You already have `classify_failure_with_history` → `REPEATED_FAILURE`. Add a `reflect` task that, when it sees ≥3 of one `ftype`, writes a single high-priority `lesson` ("When X fails repeatedly, do Y") and marks the individual error_patterns `resolved`. Schedule `reflect` from the orchestrator every N idle ticks.

### F. External orchestrator / parallelism

- **Status transitions safe? — After P0-3, yes.** Before: no.
- **Active tasks race? — Yes, fixed by `claim_task`.**
- **Write/repair truly serialized? — Mostly.** `_is_parallel_safe` excludes `safe_write`/`repair`/`memory_apply` kinds and `agentops-repair` owner from *joining a batch with others*. But the first task in a batch is always admitted even if write-ish — confirm a write task never runs concurrently with another write task. With `claim_task` + the `touches` filter this holds; tighten by also serializing when `risk == "review_required"` (already done).
- **`touches` sufficient? — For declared paths, yes; it's advisory.** If a task forgets to declare `touches`, two tasks can edit the same file. Mitigation: default write-ish tasks to `touches: ["*"]` (forces serial) unless explicitly narrowed.
- **Stale lock recovery safe on Windows? — Only after P0-1.**
- **Remaining zombie cases:** process killed *between* `claim_task` (active) and `mark_task_done` → task stuck `active`. Covered by interruption sweep on next start. Add a watchdog: tasks `active` with `claimed_at` older than `max_age` are swept to pending by `recover_interrupted_active_tasks` (extend it to check `claimed_at`).

### G. Portal automation safety

Current `safety.py` is a keyword classifier over element text — a fine *gate*, not a *runner*. It correctly biases to `review_required` for unknown elements and blocks the Korean/English risky verbs (삭제/저장/제출/승인/업로드/다운로드/…). Architecture to build (P2, design now):
- **Attach-only to existing Chrome** via CDP `--remote-debugging-port=9222`; never launch a login flow. (doctor already probes 9222.)
- **No cookie/storage/token extraction** — forbid CDP `Network.getAllCookies`, `Storage.*`, `Runtime.evaluate` returning document.cookie. Whitelist only `Page.captureScreenshot`, `DOM.getDocument`, `DOM.getOuterHTML`.
- **Snapshot** HTML + screenshot to `portal_research/html_snapshots/` and `/screenshots/` (dirs already created in `ensure_dirs`).
- **Classify clickables** → `clickable_elements.jsonl` → `safety.scan_jsonl_file` (already wired as `safety_scan` task kind).
- **Quarantine risky actions:** any element classified `blocked`/`review_required` is recorded, never auto-clicked.
- **Evidence/reports:** `SAFETY_SCAN_REPORT.md` (exists).
- **Hard rule:** approve/submit/send/delete/upload/download require explicit current-session user approval — enforce in the *runner*, not just the classifier, and log every blocked attempt as `RISKY_ACTION_BLOCKED`.
`NEEDS_OPUS_LEVEL_DESIGN` for the CDP runner itself; safety classifier is `READY`.

### H. Installer and deployment

- **`merge_opencode` safe? — Mostly yes.** It backs up, preserves unknown keys, sets `$schema`, merges `instructions` uniquely, and **correctly strips `.agent-memory*` from instructions** (the explicit requirement). Good.
- **Preserves existing config? — Yes** (dict merge, `setdefault`). One risk: it force-sets a global `permission` block with `edit: ask, bash: ask` etc. — if the user already had a stricter/looser global permission, `setdefault` preserves theirs (good), but document that mode behavior depends on it.
- **Avoids adding `.agent-memory` to instructions? — Yes** (`merge_unique` filters `startswith(".agent-memory")`).
- **Installs command guard/autopilot too? — Only if they're in the payload dir.** The installer copies from `agentops_v3_1_payload/`. **This package ships `current_source/`, not `agentops_v3_1_payload/`** — so as-shipped the installer can't find the payload (it prints `[ERROR] agentops_v3_1_payload not found`). For the real distribution, ensure the payload directory is named/located as the installer expects, OR change the installer to also probe `current_source/`. → fix: add `for cand in ("agentops_v3_1_payload","current_source"): ...` to the payload search.
- **Critically:** the installer copies files but does NOT include the new `.opencode/plugins/command-guard.ts` (P0-2) unless you add it to the payload. Add it.
- **Safer single-file installer:** avoid BAT base64 entirely. Ship a `.py.txt` (rename to `.py`) plus a 3-line `.bat.txt` that only does `py -3.11 INSTALL_*.py`. No base64 marker extraction = no marker bugs. That is already the direction of `installers_light/` — keep it; drop the heavy one-file BAT permanently.

---

## 5. Test plan (Windows internal-network PC)

Run from project root. `py -3.11` shown; substitute `python` if that's your launcher.

| ID | Test | Command | Expected |
|----|------|---------|----------|
| T1 | Bad command guard (corrupted sample) | `py -3.11 agent_ops\command_guard.py check "cat > a.py << 'EOF'` `(then) The content contains..."` | JSON `"decision": "block"`, reasons include prose marker + heredoc. |
| T2 | Safe command allow | `py -3.11 agent_ops\command_guard.py check "python agent_ops/agentops.py status"` | `"decision": "allow"`. |
| T3 | Normal command asks (not blocked) | `py -3.11 agent_ops\command_guard.py check "node build.js"` | `"decision": "ask"`. |
| T4 | safe_file_writer validation | create `staging.txt` with `print(1)` then `py -3.11 agent_ops\safe_file_writer.py out\demo.py --content-file staging.txt` | JSON `"ok": true`, `py_compile_returncode: 0`, file at `out\demo.py`. |
| T4b | safe_file_writer rejects bad python | staging with `def(:` then same | `"ok": false`, `py_compile_failed`, exit 40. |
| T5 | Stale heartbeat recovery | edit `agent_ops\state\RUN_STATE.json` set `status:"running"`, `last_heartbeat` to 1 hour ago; then `py -3.11 agent_ops\agentops.py resume` | Output shows "INTERRUPTED RUN RECOVERED"; any `active` task → `pending`. |
| T6 | Memory recall injection | `py -3.11 agent_ops\agentops.py remember "always keep BAT ASCII"` then `py -3.11 agent_ops\agentops.py recall BAT ASCII` | Recall lists the user instruction with high priority. |
| T7 | Parallel touches conflict | enqueue 2 tasks with same `--touches src/x.py`, run `orchestrator --parallel --workers 3` one tick | Only ONE of the two runs in the same batch; both eventually `done` once. |
| T8 | Compaction handoff | trigger compaction in OpenCode (long session) OR inspect: `py -3.11 agent_ops\agentops.py checkpoint --note test` then open `agent_ops\state\COMPACT_HANDOFF.md` | File contains run state + active task + "PLANNED, not approved" safety line. |
| T9 | Plugin guard live | in OpenCode autopilot, ask it to run `cd portal_research && cat > r.py << 'EOF'` | OpenCode shows thrown guard error; command does NOT run. **VERIFY-ON-MACHINE.** |
| T10 | Keyless LLM gate | `set AGENTOPS_LLM_NO_AUTH=1` + base_url + model, then `py -3.11 -c "from agent_ops.llm_client import is_configured; print(is_configured())"` | `True`. |
| T11 | Full verify | `py -3.11 agent_ops\agentops.py verify` | `"ok": true` (after `init` so `.agent-memory/memory.jsonl` exists). |

**Pre-req for T11:** run `py -3.11 agent_ops\agentops.py init` first — `verify()` requires `.agent-memory/memory.jsonl`, which `init`→`ensure_memory()` creates. (The installer runs `init` before `verify` for this reason; preserve that order.)

---

## 6. User-visible improvement roadmap (ranked by expected user impact)

For a non-developer on a Windows 망분리 PC, "feels helpful" beats "architecturally elegant." Ranked by perceived usefulness:

| Rank | Improvement | User benefit | Difficulty | Risk | Files / layer | AgentOps vs core | Priority |
|------|-------------|--------------|------------|------|---------------|------------------|----------|
| 1 | **`tool.execute.before` command guard plugin** (P0-2) | Corrupted approval windows can never auto-run — kills the #1 pain | Low | Low | `.opencode/plugins/command-guard.ts` | AgentOps layer | **P0** |
| 2 | **Simplified command surface**: `/start`, `/work`, `/fix`, `/status`, `/remember` as the *only* visible commands; rest hidden | Stops the "13 confusing commands" problem | Low | Low | new `.opencode/commands/*.md` that wrap existing | AgentOps | **P0** |
| 3 | **Korean plain-text status** (not JSON) | User actually understands what's happening | Low | Low | `agentops.py` add `status --ko`; reporter | AgentOps | **P0** |
| 4 | **Local mini dashboard HTML** generated from state files (open in browser) | Sees current task / queue / last changes / why-stopped at a glance | Med | Low | new `agent_ops/dashboard.py` → `agent_ops/reports/dashboard.html` | AgentOps | P1 |
| 5 | **Friendly failure report** (root cause + exact next step + "safe rollback available") instead of traceback | Recovers without fear | Med | Low | `failures.make_selfheal_plan` → Korean renderer | AgentOps | P1 |
| 6 | **"What changed / what I fixed automatically" summary** after each work session | Feels like real progress, not just plans | Med | Low | `reporter.py` diff of DONE_LOG since last run | AgentOps | P1 |
| 7 | **Keyless internal-gateway support** (P0-4) | The whole co-growth/LLM feature actually works on his PC | Low | Low | `llm_client.py` | AgentOps | **P0** |
| 8 | **One-click doctor/fix runner** (`RUN_AGENTOPS_FIX.bat.txt` → doctor+selfheal+verify) | Self-service recovery, no command memorization | Low | Low | new BAT + `agentops.py fix` | AgentOps | P1 |
| 9 | **Restart-resume bootstrap**: `/start` auto-runs resume+status+recommended next action | Removes "what do I type when I open this?" | Low | Low | `.opencode/commands/start.md` | AgentOps | P1 |
| 10 | **Mode indicator** (plan/normal/auto) written to state + shown in `/status` (C1) | Knows how much autonomy is active | Low | Low | small plugin + `agentops.py` | AgentOps | P1 |
| 11 | **Reflection task** (repeated failures → one generalized rule; archive the noise) | System visibly gets smarter; memory stays clean | Med | Low | `memory_manager`, `orchestrator` reflect kind | AgentOps | P1 |
| 12 | **Agent activity timeline** (append-only human-readable log of what ran) | Trust: sees it actually worked | Low | Low | `reporter.py` render of `done_log.jsonl` | AgentOps | P2 |
| 13 | **Task queue visualizer** (readable table, not JSONL) | Understands what's pending/blocked | Low | Low | dashboard.py | AgentOps | P2 |
| 14 | **"Approve only this action" safe workflow** for portal | Can permit one risky click without opening the floodgates | Med | Med | portal runner + classifier | AgentOps | P2 |
| 15 | **Portal snapshot viewer** (index.html of screenshots+HTML) | Reviews collected evidence easily | Med | Low | dashboard.py | AgentOps | P2 |
| 16 | **Memory quality review with approval** (stale/duplicate cleanup proposes, user confirms) | Memory stays trustworthy | Med | Low | `memory_manager.propose_memory_update` | AgentOps | P2 |
| 17 | **Before/after reliability metrics** (failures per session trend) | Sees it improving over time | Med | Low | reporter + logs | AgentOps | P2 |
| 18 | **Korean path / space-in-path hardening audit** | No mysterious breakage on his actual paths | Low | Low | review all `Path` joins (already mostly OK) | AgentOps | P1 |
| 19 | **True permission-mode hotkey (Shift+Tab)** (C2) | The exact Claude-Code feel he asked for | High | High | OpenCode source fork | **core patch** | P2 |
| 20 | **Generate TS guard rules from Python** at install (keep them in sync) | One source of truth for block rules | Med | Low | installer | AgentOps | P2 |

**Command simplification (concrete proposal, P0 item #2):**
- `/start` → resume + status + recommended next action (read-only, Korean summary)
- `/work <goal>` → guarded autopilot execution of one bounded goal
- `/fix` → selfheal + repair + verify
- `/status` → Korean plain-text status (read-only)
- `/remember <note>` → save correction/preference
- Keep `/continue`, `/autopilot`, `/doctor`, `/verify`, `/safecreate`, `/lintcmd`, `/memorycheck`, `/recall`, `/enqueue`, `/checkpoint`, `/resume`, `/orchestrator` as **advanced/hidden** (still work, just not the front door). Don't delete — power user (you) still wants them.

---

## 7. Conceptual architecture vs actionable patches (separation)

**Immediately actionable (this backlog):** P0-1..4, P1-1..7, command simplification, Korean status, dashboard, keyless LLM. All AgentOps-layer, no fork.

**Conceptual / design-first (do not code yet):**
- C2 true permission-mode toggle (needs source spike first).
- Full CDP portal runner with action quarantine (needs a safe-by-construction design + your sign-off).
- Generating TS guard from Python (nice-to-have sync mechanism).

---

## 8. Implementation handoff for lower-capability models

Execute phases in order. Do not skip Phase 0. After every code change, run the listed validation and stop if it fails.

### Phase 0 — must-fix blockers before install

```text
Task ID: P0-1-winlock
Priority: P0
Can be implemented by: Sonnet / GPT-5
Files to edit: agent_ops/core.py
Files to avoid editing: any .opencode/*, queue_manager.py
Goal: Make lock liveness/staleness correct on Windows so the task-queue lock can't deadlock or be deleted while live.
Exact steps:
  1. Replace function _pid_alive with the version in review §3 Patch P0-1.
  2. Replace function _lock_is_stale with the version in §3 Patch P0-1.
  3. Do not change file_lock().
Code changes: see §3 Patch P0-1 (copy verbatim).
Validation commands:
  py -3.11 -m py_compile agent_ops/core.py
  py -3.11 -c "from agent_ops.core import _pid_alive; import os; print(_pid_alive(os.getpid()), _pid_alive(999999))"
Expected validation result: compiles; prints "True False" (second value may be True only if PID 999999 really exists).
Rollback plan: restore agent_ops/core.py from .agentops_backup or git.
Risks: ctypes import on non-Windows is skipped by os.name guard; POSIX path unchanged.
```

```text
Task ID: P0-2-guard-plugin
Priority: P0
Can be implemented by: Sonnet / GPT-5
Files to edit: create .opencode/plugins/command-guard.ts ; add it to installer payload list
Files to avoid editing: command_guard.py (logic already correct), other plugins
Goal: Block corrupted/unsafe bash commands in OpenCode's real execution path (not just the manual CLI).
Exact steps:
  1. Create .opencode/plugins/command-guard.ts with the exact content in §3 Patch P0-2.
  2. Ensure NO npm imports are added (offline PC).
  3. If using the installer, add this file to the payload so it ships.
Code changes: see §3 Patch P0-2 (copy verbatim).
Validation commands:
  (rule parity check) py -3.11 agent_ops/command_guard.py check "cd x && cat > a.py << 'EOF'"
  (live, on machine) In OpenCode autopilot, attempt: cd portal_research && cat > r.py << 'EOF'
Expected validation result: CLI prints "decision":"block"; OpenCode shows the thrown guard error and does NOT execute.
Rollback plan: delete .opencode/plugins/command-guard.ts (autopilot deny globs remain as fallback).
Risks: if the build doesn't load plugins, this no-ops silently — confirm with T9. Falls back to permission globs.
```

```text
Task ID: P0-3-parallel-claim
Priority: P0
Can be implemented by: Sonnet / GPT-5
Files to edit: agent_ops/queue_manager.py, agent_ops/orchestrator.py
Files to avoid editing: state_manager.py
Goal: Stop double-running tasks and stop shared-state corruption in parallel mode.
Exact steps:
  1. Add claim_task() to queue_manager.py (§3 Patch P0-3).
  2. Add run_task_parallel() and _CKPT_LOCK to orchestrator.py (§3 Patch P0-3).
  3. In run_loop_parallel, submit run_task_parallel (not run_task); after as_completed, update_checkpoint once under _CKPT_LOCK.
  4. Remove per-worker set_active_task/update_checkpoint from the parallel path.
Code changes: see §3 Patch P0-3.
Validation commands:
  py -3.11 -m py_compile agent_ops/queue_manager.py agent_ops/orchestrator.py
  (T7) enqueue 6 trivial memorycheck tasks; run orchestrator --parallel --workers 3 --interval 5; Ctrl-C; status
Expected validation result: compiles; each task done exactly once; no attempt_count>1 from double-dispatch; ACTIVE_TASK.json valid JSON.
Rollback plan: restore both files from backup; parallel mode reverts to (buggy) prior behavior — prefer running serial orchestrator until fixed.
Risks: serial path (run_task) unchanged; only parallel path altered.
```

```text
Task ID: P0-4-keyless-llm
Priority: P0
Can be implemented by: Sonnet / GPT-5 / GPT-5 mini
Files to edit: agent_ops/llm_client.py
Files to avoid editing: orchestrator.py
Goal: Let the keyless internal gateway work, and never crash on non-OpenAI responses.
Exact steps:
  1. Replace is_configured() and chat() with §3 Patch P0-4 versions.
Code changes: see §3 Patch P0-4.
Validation commands:
  py -3.11 -m py_compile agent_ops/llm_client.py
  set AGENTOPS_LLM_NO_AUTH=1 & set AGENTOPS_LLM_BASE_URL=http://127.0.0.1:1/v1 & set AGENTOPS_LLM_MODEL=test & py -3.11 -c "from agent_ops.llm_client import is_configured; print(is_configured())"
Expected validation result: compiles; prints True.
Rollback plan: restore llm_client.py.
Risks: none; key is still used when present.
```

### Phase 1 — safe AgentOps-layer improvements

```text
Task ID: P1-retry-and-bloat
Priority: P1
Can be implemented by: Sonnet / GPT-5
Files to edit: agent_ops/queue_manager.py, agent_ops/memory_manager.py, agent_ops/failures.py, agent_ops/core.py
Files to avoid editing: .opencode/*
Goal: Order-independent retries with backoff; stop memory bloat; validate .bat.txt ASCII.
Exact steps:
  1. Replace mark_task_failed (§3 P1-1) and add _retry_ready + selector change (§3 P1-2).
  2. Replace record_success_lesson and gate error-pattern memory + add MAX_ACTIVE cap (§3 P1-3).
  3. Extend ASCII validation to .bat.txt/.cmd.txt (§3 P1-4) in core.validate_written_file and safe_file_writer.validate.
Validation commands:
  py -3.11 -m py_compile agent_ops/queue_manager.py agent_ops/memory_manager.py agent_ops/failures.py agent_ops/core.py
  py -3.11 agent_ops/agentops.py init && py -3.11 agent_ops/agentops.py memorycheck
Expected validation result: compiles; memorycheck runs; repeated successes do not add duplicate lessons.
Rollback plan: restore the four files.
Risks: low; behavior is additive/limiting.
```

```text
Task ID: P1-compaction-and-status
Priority: P1
Can be implemented by: Sonnet / GPT-5
Files to edit: .opencode/plugins/compaction-handoff.ts, agent_ops/agentops.py
Files to avoid editing: state_manager.py write helpers
Goal: Additive, path-robust compaction injection; make /status read-only.
Exact steps:
  1. Replace compaction-handoff.ts with §3 Patch P1-5.
  2. Replace cmd_status with §3 Patch P1-7 (remove recovery side effects).
Validation commands:
  py -3.11 -m py_compile agent_ops/agentops.py
  py -3.11 agent_ops/agentops.py status   (run twice; confirm an 'active' task is NOT flipped to pending)
Expected validation result: status is read-only; COMPACT_HANDOFF.md still populated by checkpoint/resume.
Rollback plan: restore both files.
Risks: ensure recovery still happens in resume/init (it does).
```

### Phase 2 — user-visible UX improvements

```text
Task ID: P2-simplify-commands-and-korean-status
Priority: P1 (UX-critical)
Can be implemented by: Sonnet / GPT-5
Files to edit: create .opencode/commands/start.md, work.md, fix.md ; add `status --ko` + `fix` subcommands to agent_ops/agentops.py ; new agent_ops/render_ko.py
Files to avoid editing: existing command files (keep them as advanced)
Goal: Front-door commands /start /work /fix /status(/remember) with Korean plain-text output.
Exact steps:
  1. /start.md (agent: agentops-supervisor) → body runs: python agent_ops/agentops.py resume then status --ko.
  2. /work.md (agent: agentops-autopilot) → guarded execution of $ARGUMENTS (reuse autopilot.md body).
  3. /fix.md (agent: agentops-repair) → python agent_ops/agentops.py selfheal then verify.
  4. Add cmd for `status --ko`: render the same data as Korean sentences (queue counts, active task title, stop flag, last note).
  5. Add `fix` subcommand = selfheal + verify.
Validation commands:
  py -3.11 -m py_compile agent_ops/agentops.py
  py -3.11 agent_ops/agentops.py status --ko
Expected validation result: prints a short Korean status paragraph, no raw JSON.
Rollback plan: delete new command files and revert agentops.py.
Risks: low; purely additive.
```

```text
Task ID: P2-dashboard
Priority: P2
Can be implemented by: Sonnet / GPT-5
Files to edit: create agent_ops/dashboard.py ; add `dashboard` subcommand
Files to avoid editing: core state files
Goal: Single local HTML dashboard from state files (current task, queue table, recent done, recent failures, why-stopped).
Exact steps:
  1. dashboard.py reads RUN_STATE/CHECKPOINT/ACTIVE_TASK/TASK_QUEUE/done_log/failure_log and writes agent_ops/reports/dashboard.html (no external CDN; inline CSS).
  2. Add `dashboard` subcommand that writes the file and prints its path.
Validation commands:
  py -3.11 agent_ops/agentops.py init && py -3.11 agent_ops/agentops.py dashboard
Expected validation result: agent_ops/reports/dashboard.html exists and opens in a browser.
Rollback plan: delete dashboard.py and the subcommand.
Risks: none; read-only render.
```

### Phase 3 — OpenCode source-level changes

```text
Task ID: P3-permission-mode-toggle
Priority: P2
Can be implemented by: Opus only (design) then a strong engineer
Files to edit: forked OpenCode source (keybind/action registry + permission resolver) — TBD after source spike
Files to avoid editing: AgentOps layer
Goal: True plan/normal/auto session permission mode with Shift+Tab + status indicator (C2).
Exact steps:
  1. SPIKE FIRST: locate keybind/action registration and the single permission-resolution chokepoint; confirm it's centralized.
  2. Add session.permissionMode state (default normal); add cycle action + indicator; resolver consults mode before agent/global rules; never override deny / external_directory.
  3. Gate behind experimental_permission_mode flag; default off = identical to today.
Validation commands: build OpenCode; toggle modes; confirm plan denies edits, auto allows project-local edits, deny still wins.
Expected validation result: mode cycles, indicator shows, backward compatible.
Rollback plan: don't ship the fork; stay on Option C1 (three primary agents).
Risks: HIGH — maintaining a fork on an offline PC. Only do if C1 is insufficient.
```

### Phase 4 — optional advanced improvements

```text
Task ID: P4-portal-runner
Priority: P2
Can be implemented by: Opus (design) + Sonnet (impl)
Files to edit: create portal_research/scripts/portal_runner.py (attach-only CDP), reuse safety.py
Files to avoid editing: anything that could automate login/OTP
Goal: Attach-only Chrome snapshotter with action quarantine; never click risky actions.
Exact steps (design): attach to 127.0.0.1:9222; whitelist Page.captureScreenshot/DOM.getDocument/DOM.getOuterHTML; forbid cookie/storage/eval; write snapshots; classify clickables via safety.classify_action; quarantine blocked/review_required; require explicit current-session approval for any risky click; log RISKY_ACTION_BLOCKED.
Validation commands: run against a known authenticated tab; confirm screenshots/HTML saved and zero risky clicks.
Expected validation result: evidence collected; risky actions logged-not-clicked.
Rollback plan: delete the runner; classifier remains.
Risks: MUST NOT extract credentials/cookies/tokens; review before enabling.
```

```text
Task ID: P4-reflection-task
Priority: P2
Can be implemented by: Sonnet / GPT-5
Files to edit: agent_ops/memory_manager.py, agent_ops/orchestrator.py
Goal: Turn ≥3 repeats of one failure type into a single generalized high-priority lesson; archive the noisy individual error_patterns.
Exact steps: add reflect logic that scans failure_log, detects ftype with count>=3, writes one lesson, marks matching error_patterns resolved; schedule from orchestrator every N idle ticks.
Validation commands: simulate 3 identical log-failure calls; run reflect; confirm one new lesson + error_patterns marked resolved.
Expected validation result: memory consolidates instead of accumulating.
Rollback plan: remove reflect scheduling.
Risks: low.
```

---

## 9. Lower-model execution prompt (copy-paste ready)

Paste this directly into Sonnet / GPT-5 / your internal LLM to implement the highest-priority safe changes. It is self-contained.

```text
You are implementing fixes to the OpenCode AgentOps v3.1 codebase on a Windows 10 internal-network PC (Python 3.11, offline, no external downloads). Work ONLY in the project root. Do NOT use heredoc/cat/long echo/python -c to create files — use your editor's file-write tool. After EVERY file change, run the validation command and STOP if it fails; report the failure instead of guessing.

Implement these tasks IN THIS EXACT ORDER. The full patch text for each is in the review document section noted. Copy the provided code verbatim.

EDIT ORDER:
1) agent_ops/core.py — replace _pid_alive and _lock_is_stale (review §3 P0-1).
   VALIDATE: py -3.11 -m py_compile agent_ops/core.py
   STOP-IF: compile error.

2) agent_ops/llm_client.py — replace is_configured and chat (review §3 P0-4).
   VALIDATE: py -3.11 -m py_compile agent_ops/llm_client.py
   STOP-IF: compile error.

3) agent_ops/queue_manager.py — add claim_task; replace mark_task_failed; add _retry_ready and update the two candidate filters (review §3 P0-3 + P1-1 + P1-2).
   VALIDATE: py -3.11 -m py_compile agent_ops/queue_manager.py
   STOP-IF: compile error.

4) agent_ops/orchestrator.py — add _CKPT_LOCK and run_task_parallel; in run_loop_parallel submit run_task_parallel and update_checkpoint once under the lock after as_completed (review §3 P0-3).
   VALIDATE: py -3.11 -m py_compile agent_ops/orchestrator.py
   STOP-IF: compile error.

5) Create .opencode/plugins/command-guard.ts with the exact content in review §3 P0-2. NO npm imports.
   VALIDATE: py -3.11 agent_ops/command_guard.py check "cd x && cat > a.py << 'EOF'"
   EXPECT: JSON containing "decision": "block".
   STOP-IF: decision is not "block".

6) agent_ops/memory_manager.py — replace record_success_lesson; add MAX_ACTIVE cap in add_memory_event (review §3 P1-3).
   agent_ops/failures.py — dedupe error_pattern memory by recent type (review §3 P1-3).
   VALIDATE: py -3.11 -m py_compile agent_ops/memory_manager.py agent_ops/failures.py
   STOP-IF: compile error.

7) agent_ops/core.py AND agent_ops/safe_file_writer.py — extend ASCII validation to .bat.txt/.cmd.txt (review §3 P1-4).
   VALIDATE: py -3.11 -m py_compile agent_ops/core.py agent_ops/safe_file_writer.py
   STOP-IF: compile error.

8) .opencode/plugins/compaction-handoff.ts — replace with review §3 P1-5 (additive context + robust path).
   agent_ops/agentops.py — replace cmd_status to be read-only (review §3 P1-7).
   VALIDATE: py -3.11 -m py_compile agent_ops/agentops.py
   STOP-IF: compile error.

FINAL FULL CHECK (run all):
  py -3.11 agent_ops/agentops.py init
  py -3.11 agent_ops/agentops.py verify
  py -3.11 agent_ops/command_guard.py check "python agent_ops/agentops.py status"   (EXPECT decision allow)
  py -3.11 agent_ops/command_guard.py check "node build.js"                          (EXPECT decision ask)

STOP CONDITIONS (report and halt; do not continue):
- Any py_compile failure.
- T1 corrupted-sample check does not return "block".
- verify returns ok:false for any reason other than a missing optional file you can create with `init`.
- You are tempted to use cat/heredoc/python -c to write a file — STOP and use the editor write tool instead.

DO NOT:
- Edit anything under .opencode/agents/ (the permission frontmatter is already correct).
- Rename .opencode/plugins/ (plural is correct).
- Add npm imports to any .ts plugin.
- Implement the permission-mode toggle (Phase 3) — that requires an OpenCode source fork and is out of scope for this pass.
```

---

## 10. One-paragraph bottom line

This is a strong v3.1 with a correct mental model and a genuinely good command-corruption detector — but the detector isn't wired into the path that matters, the Windows lock probe is unsafe, parallel mode corrupts shared state, and the LLM gate locks out the exact keyless internal gateway it was built for. Land the four P0 patches (Windows lock, guard-as-plugin, parallel claim, keyless LLM) and it's installable; layer the P1 fixes and the command-simplification + Korean-status UX, and it will actually *feel* like the persistent local assistant the user is asking for. Defer the true Shift+Tab permission-mode toggle and the CDP portal runner until after a source spike and an explicit go-ahead, respectively.
