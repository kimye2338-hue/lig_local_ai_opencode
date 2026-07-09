# OpenCodeLIG Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent repeat launcher/package mistakes by making release-critical assumptions executable checks.

**Architecture:** Add a small Python quality gate that runs static contract checks and selected existing tests. The gate must check the installed-package behavior surface, not just file presence, and it must produce a readable Markdown report under `agent_ops/results/quality_gate`.

**Tech Stack:** Python 3.11 stdlib, existing pytest tests, existing batch launchers.

## Global Constraints

- Do not expose or change gateway secrets.
- Do not delete `%USERPROFILE%\OpenCodeLIG_USERDATA`.
- `.bat` files must remain CRLF and include `chcp 65001`.
- `OPENCODE_PURE=1` must be forbidden.
- `.opencode\plugins`, `browser_cdp.py`, and original `opencode.json` must not be disabled or minimized.
- `최종_패치파일.bat` remains the single user-facing patch entry point.

---

### Task 1: Quality Gate Contract Tests

**Files:**
- Create: `workspace/tests/test_quality_gate.py`

**Interfaces:**
- Consumes: repository files under `workspace/`
- Produces: tests that fail until `agent_ops/quality_gate.py` exists and exposes `run_quality_gate()`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from agent_ops.quality_gate import run_quality_gate

def test_quality_gate_checks_runtime_contracts():
    result = run_quality_gate(Path(__file__).resolve().parents[1], run_commands=False)
    names = {check.name for check in result.checks}
    assert "launcher_fast_runtime" in names
    assert "launcher_direct_hamster" in names
    assert "ocd_project_dir_contract" in names
    assert "final_patch_self_contained" in names
    assert all(check.status == "PASS" for check in result.checks), result.to_markdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3.11 -m pytest workspace\tests\test_quality_gate.py -q`

Expected: FAIL because `agent_ops.quality_gate` does not exist.

- [ ] **Step 3: Implement the quality gate**

Create `workspace/agent_ops/quality_gate.py` with:

```python
@dataclass
class GateCheck:
    name: str
    status: str
    evidence: str

@dataclass
class GateResult:
    checks: list[GateCheck]
    report_path: Path | None
    def to_markdown(self) -> str: ...

def run_quality_gate(workspace: Path, run_commands: bool = True) -> GateResult: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3.11 -m pytest workspace\tests\test_quality_gate.py -q`

Expected: PASS.

### Task 2: Command-Line Gate and Report

**Files:**
- Modify: `workspace/agent_ops/quality_gate.py`
- Modify: `workspace/agent_ops/agentops.py`

**Interfaces:**
- Consumes: `run_quality_gate(workspace, run_commands=True)`
- Produces: `python agent_ops\quality_gate.py` and `python agent_ops\agentops.py quality-gate`

- [ ] **Step 1: Write the failing test**

Add a test that runs:

```python
subprocess.run([sys.executable, str(WS / "agent_ops" / "quality_gate.py"), "--no-commands"])
```

Expected: exit code 0 and Markdown report path printed.

- [ ] **Step 2: Implement CLI**

Add argparse options:

- `--workspace`
- `--no-commands`
- `--out`

- [ ] **Step 3: Wire agentops command**

Add a small command branch for `quality-gate` that calls the module.

- [ ] **Step 4: Verify**

Run:

```cmd
py -3.11 -m pytest workspace\tests\test_quality_gate.py -q
py -3.11 workspace\agent_ops\quality_gate.py --no-commands
```

### Task 3: Package and Documentation

**Files:**
- Modify: `workspace/docs/운영/WORK_LOG_20260709_HOTFIX.md`
- Modify: `workspace/patches/existing_install_hotfix_20260709.py`
- Regenerate: `최종_패치파일.bat`

**Interfaces:**
- Consumes: `quality_gate.py`
- Produces: final patch that includes the quality gate and work log instructions

- [ ] **Step 1: Add work log section**

Document that future release work must run:

```cmd
py -3.11 workspace\agent_ops\quality_gate.py
```

- [ ] **Step 2: Regenerate final patch BAT**

Embed the latest hotfix Python payload and preserve the existing embedded `mss` wheel.

- [ ] **Step 3: Verify final state**

Run:

```cmd
py -3.11 -m pytest workspace\tests\test_quality_gate.py workspace\tests\test_existing_install_hotfix.py workspace\tests\test_opencode_lig_plugin_runtime.py -q
py -3.11 -m py_compile workspace\agent_ops\quality_gate.py workspace\patches\existing_install_hotfix_20260709.py
py -3.11 workspace\agent_ops\quality_gate.py --no-commands
```
