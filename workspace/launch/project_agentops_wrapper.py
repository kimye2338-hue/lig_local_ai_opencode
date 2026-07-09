# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def main() -> None:
    install_home = Path(os.environ.get("LIG_AGENTOPS_HOME", "")).resolve()
    if not install_home.exists():
        raise SystemExit("LIG_AGENTOPS_HOME is not set to the installed workspace")
    project_root = Path(os.environ.get("AGENTOPS_ROOT") or Path.cwd()).resolve()
    os.environ["AGENTOPS_ROOT"] = str(project_root)
    script_name = Path(__file__).name
    target = install_home / "agent_ops" / script_name
    if not target.exists():
        raise SystemExit(f"installed agent_ops script not found: {target}")
    project_path = str(project_root)
    sys.path[:] = [p for p in sys.path if p and str(Path(p).resolve()) != project_path]
    sys.path.insert(0, str(install_home))
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
