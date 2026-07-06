# Runtime lessons — 2026-07-05

This document records user-confirmed runtime failures from the company Windows PC. Future Claude Code/Codex sessions must read this before changing the OpenCodeLIG installer, launcher, model config, or patched OpenCode binary.

## 1. Model config missing from latest Actions artifact

Observed symptom:

```text
RUN_OPENCODE_LIG.bat opens OpenCode, but model/provider selection is not configured.
```

Root cause:

- The latest offline package installed `RUN_OPENCODE_LIG.bat` and `opencode.exe`, but the effective `opencode.json` could be too thin, e.g. only `{ "autoupdate": false }`.
- A launcher alone is not enough. The installer must write a complete provider/model config to every config root used by the hardened launcher.

Required fix pattern:

- Write complete `opencode.json` with providers and `model`.
- Write to all effective roots:
  - `%USERPROFILE%\OpenCodeLIG\workspace\opencode.json`
  - `%USERPROFILE%\OpenCodeLIG_USERDATA\opencode_config\opencode.json`
  - `%USERPROFILE%\OpenCodeLIG\userdata\config\opencode\opencode.json`
  - `%USERPROFILE%\.config\opencode\opencode.json`
- `RUN_OPENCODE_LIG.bat` must load `%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env` before launching OpenCode.
- Do **not** commit real API keys. Local installers may preserve/reuse local secrets, but public repo files must stay secret-free.

Current public-safe hotfix script:

```text
release/hotfix/FIX_RUN_OPENCODE_LIG_MODEL_CONFIG_SAFE.bat.txt
```

## 2. Spinner crash remains in latest artifact exe

Observed crash URL contained:

```text
[Reconciler] Unknown component type: spinner
```

User confirmed:

```text
where opencode
=> C:\Users\74358\OpenCodeLIG\bin\opencode.exe

opencode --version
=> 0.0.0--202607050535
```

Therefore the issue is not PATH confusion.

Inspection of the latest Actions artifact showed:

- `payload/opencode.exe` SHA256: `f011423a0f799c43440092bb35cbcafa2e6412e85ef4742b395931ea5659bf90`
- The OpenTUI component registry does not register `spinner`.
- The bundled TUI code still contains exactly one unsafe direct component creation:

```js
D("spinner")
```

Runtime result:

```text
[Reconciler] Unknown component type: spinner
```

Required fix pattern:

- The proper source-level fix is to remove direct spinner render paths or register a renderer for spinner.
- Do not assume copying the latest artifact exe fixes this; the latest inspected exe itself still contains the unsafe string.
- Binary hotfix is acceptable as a temporary rescue only when it verifies exactly one occurrence:

```js
D("spinner")
```

replaced with same-length valid JS:

```js
D("text"   )
```

Current public hotfix script:

```text
release/hotfix/PATCH_OPENCODE_SPINNER_UNKNOWN_TYPE_V2.bat.txt
```

## 3. Never generate Python scripts with fragile BAT echo blocks

A previous hotfix attempted to create a temporary Python script using many `echo ...` lines. It failed because CMD consumed parentheses and redirection characters, producing invalid Python such as:

```python
target = Path(os.environ["TARGET"]
if count_old
if verify.count(old)
```

Required rule:

- For non-trivial BAT+Python hotfixes, prefer hybrid BAT/Python:

```bat
@python -x "%~f0" %* & pause & exit /b
# -*- coding: utf-8 -*-
# Python code here
```

or ship a separate `.py.txt` file.

Do not use large `echo (...)` blocks to generate Python code that contains parentheses, `>`, `<`, `%`, `!`, or quotes.

## 4. Mojibake / Korean text corruption in OpenCode terminal

Observed output:

```text
C ����̺��� �������� �̸��� �����ϴ�.
```

This is Korean CMD output mojibake. It is usually what happens when Korean CP949/OEM output from `dir` or CMD is interpreted/displayed as UTF-8, or when the terminal/codepage was not set consistently.

Required fix pattern:

- Launchers must set:

```bat
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
```

- Python subprocess capture must use:

```python
subprocess.run(..., text=True, encoding="utf-8", errors="replace")
```

- Agent instructions should prefer ASCII/PowerShell-free commands or prefix CMD work with `chcp 65001 >nul`.
- For file checks, prefer Python/pathlib probes over `dir` when Korean localized CMD output matters.

## 5. Agent stops after partial tool work

Observed pattern:

- Agent says it will inspect a file.
- It runs `dir` and `Read launch\chrome-debug.bat`.
- Then output stops around `이제...`.

Likely causes:

1. TUI crash path, especially spinner crash while rendering active work.
2. Supervisor mode being cautious and stopping at a boundary after inspecting prerequisites.
3. Tool/read step completed but model did not continue because the session crashed or got stuck in a UI render state.
4. The browser task was blocked because Chrome was not actually launched in debug mode.

Required mitigation:

- First fix spinner crash.
- Keep SAFE_PURE launcher available.
- For browser tasks, provide a single explicit workflow:
  1. run `launch\chrome-debug.bat`
  2. verify CDP port
  3. then inspect tabs
- For long tasks, tell the agent explicitly: `continue until blocked, and if blocked write exact blocker and next command`.

## 6. Public repo secret rule

The user may use internal keys on the closed company PC, but this repository is public. Therefore:

- Do not commit real API keys.
- Do not print real API keys in docs.
- Local installers/hotfixes may preserve an existing `%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env`.
- If a key is needed and no env file exists, prompt locally or create a placeholder.

## 7. Future patch checklist

Before declaring a package fixed:

- Verify effective `where opencode` path.
- Print `opencode --version`.
- Print `opencode.exe` SHA256.
- Check for unsafe `D("spinner")` in the final installed exe.
- Verify `opencode.json` contains provider/model, not only `autoupdate`.
- Verify `RUN_OPENCODE_LIG.bat` loads `lig-api.env`.
- Verify Korean output does not mojibake under the launcher.
- If using AUTO/Supervisor, confirm it finishes the requested task or writes an explicit blocker.
