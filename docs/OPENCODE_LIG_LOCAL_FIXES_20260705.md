# OpenCodeLIG local hotfix notes — 2026-07-05

This note records local company-PC issues found while testing the latest GitHub Actions artifact and the rules Claude Code / Fable / Codex must preserve in future patches.

## 1. Model/provider config can be missing after install

Symptom:
- `RUN_OPENCODE_LIG.bat` starts OpenCode, but the model/provider appears unset or unusable.
- Installed `opencode.json` may be too thin, for example only `{ "autoupdate": false }`.

Required behavior:
- The installer/repair script must write model/provider config to every config root used by the launcher:
  - `%USERPROFILE%\.config\opencode\opencode.json`
  - `%USERPROFILE%\OpenCodeLIG\userdata\config\opencode\opencode.json`
  - workspace-local config if the launcher uses `OPENCODE_CONFIG`.
- The launcher must load `%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env` into the process environment before OpenCode starts.
- `OPENCODE_CONFIG`, `OPENCODE_USERDATA`, and XDG paths must point to the same intended config/data/cache tree.

Recommended default coding route:
- `lig-qwen-coding/Qwen3.6-27B`

Useful alternates:
- `lig-exaone-coding/EXAONE-4.5-33B`
- `lig-gemma-it/gemma-4-31B-it`

Public repo rule:
- Do not commit real local credentials.
- Closed-network local repair files may preserve local credentials, but GitHub-tracked files must avoid them.

## 2. Spinner crash is not a model/API issue

Crash:

```text
[Reconciler] Unknown component type: spinner
```

Observed artifact:
- Latest tested Actions artifact: `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE`
- Payload exe SHA256 seen locally: `f011423a0f799c43440092bb35cbcafa2e6412e85ef4742b395931ea5659bf90`

Root cause found by inspecting the exe:
- OpenTUI component registry does not register `spinner`.
- The bundled TUI code still contains a direct `D("spinner")` component creation.
- Re-copying the same latest exe does not help, because the latest artifact itself still contains the crash path.

Temporary local hotfix:
- `patches/runtime-hotfixes/PATCH_OPENCODE_SPINNER_UNKNOWN_TYPE_V2.bat.txt`
- It patches the installed exe in place from:

```js
D("spinner")
```

to same-length valid JS:

```js
D("text"   )
```

Future build rule:
- Do not reintroduce direct `<spinner>` JSX or `D("spinner")` unless the offline OpenTUI renderer definitely registers a `spinner` component.
- Prefer a text fallback or a registered component.

## 3. Mojibake / foreign-looking output

Symptom example:

```text
C ����̺��� �������� �̸��� �����ϴ�.
```

Meaning:
- This is Korean Windows command output decoded/rendered with the wrong codepage.
- Usually CMD produced Korean text in CP949/EUC-KR but the TUI/process expected UTF-8, or the reverse.

Rules:
- BAT launchers should start with `chcp 65001 >nul`.
- Set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8`.
- Python subprocess calls that capture output must use `encoding="utf-8", errors="replace"`.
- Avoid relying on localized `dir` output for machine parsing. Prefer Python `Path.exists()`, JSON, or ASCII sentinel lines like `FOUND` / `NOT_FOUND`.

## 4. Agent stopped after `Read launch\chrome-debug.bat`

Observed behavior:
- In supervisor + auto mode, the agent says it will read `launch\chrome-debug.bat`, then stops or does not finish the actual answer.

Likely causes:
1. TUI spinner crash interrupted the render/tool loop.
2. The read/tool result was not fed back cleanly because of command output encoding noise.
3. Supervisor mode may stop at an intermediate diagnostic step when it thinks user action is required, especially for browser-debug prerequisites.

Required future behavior:
- After reading a file, continue to the next planned step unless a real blocker is found.
- When Chrome debug mode is required, verify it with machine-readable checks, not localized `dir` output.
- If blocked, say exactly what is missing, which file to run, and what output to paste back.
- Do not stop at “이제...” without the next command/result.

## 5. Do not repeat these mistakes

- Do not fix spinner by simply copying the same latest artifact exe.
- Do not count model settings fixed unless `opencode.json` contains provider/model routes.
- Do not create BAT files that generate Python via fragile `echo ...` lines containing parentheses. Use a hybrid BAT/Python file instead.
- Do not use PowerShell `ExecutionPolicy Bypass`, Base64 embedded payloads, or self-extracting BAT payloads.
- Do not parse localized Korean Windows `dir` output as a success condition; emit explicit ASCII sentinel lines.
