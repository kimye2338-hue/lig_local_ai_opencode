# -*- coding: utf-8 -*-
"""Probe scripts: environment/gateway fact collection must be safe to upload.

Run: py -3.11 tests\\test_probes.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WS_TEMPLATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS_TEMPLATE))

from agent_ops.probe_env import run_probe, _mask_path  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="probe_test_"))

    # --- env probe: runs on this PC, JSON-serializable, privacy-safe ---
    report = run_probe()
    check("env probe returns required sections",
          all(k in report for k in ("os", "python", "apps", "office_macro_security")),
          str(sorted(report)))
    text = json.dumps(report, ensure_ascii=False)
    import getpass
    import platform
    check("env probe omits hostname and username",
          platform.node() not in text and getpass.getuser() not in text)
    check("home paths are masked to %USERPROFILE%",
          _mask_path(str(Path.home() / "x")) == "%USERPROFILE%\\x")

    # --- env probe CLI writes files where PROBE_OUT_DIR points ---
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                "PROBE_OUT_DIR": str(tmp)})
    r = subprocess.run(["py", "-3.11", str(WS_TEMPLATE / "agent_ops" / "probe_env.py")],
                       env=env, capture_output=True, timeout=120)
    check("env probe CLI exits 0 and writes json+md",
          r.returncode == 0 and list(tmp.glob("probe_env_*.json"))
          and list(tmp.glob("probe_env_*.md")),
          r.stderr.decode("utf-8", errors="replace"))

    # --- gateway probe: without config it must guide and exit 2, no file ---
    env2 = dict(env)
    env2["LIG_API_ENV_FILE"] = str(tmp / "no_such.env")
    env2.pop("LIG_PROVIDER_PROFILE", None)
    r2 = subprocess.run(["py", "-3.11", str(WS_TEMPLATE / "agent_ops" / "probe_gateway.py")],
                        env=env2, capture_output=True, timeout=120)
    check("gateway probe without config exits 2 with guidance",
          r2.returncode == 2 and "LIG_GATEWAY_BASE_URL" in r2.stderr.decode("utf-8", errors="replace"),
          r2.stderr.decode("utf-8", errors="replace")[:300])
    check("gateway probe without config writes no result file",
          not list(tmp.glob("probe_gateway_*.json")))

    # --- gateway probe masking: fake env with fake secret must be masked ---
    fake_env = tmp / "fake.env"
    fake_env.write_text("LIG_GATEWAY_BASE_URL=http://fakehost.example:8000\n"
                        "LIG_API_KEY=FAKESECRET1234\n", encoding="utf-8")
    env3 = dict(env)
    env3["LIG_API_ENV_FILE"] = str(fake_env)
    r3 = subprocess.run(["py", "-3.11", str(WS_TEMPLATE / "agent_ops" / "probe_gateway.py")],
                        env=env3, capture_output=True, timeout=180)
    out3 = r3.stdout.decode("utf-8", errors="replace")
    gw_files = list(tmp.glob("probe_gateway_*.json"))
    check("gateway probe with unreachable fake host still completes (errors recorded)",
          r3.returncode == 0 and gw_files, r3.stderr.decode("utf-8", errors="replace")[:300])
    body = gw_files[0].read_text(encoding="utf-8")
    check("result masks api key and host",
          "FAKESECRET1234" not in body and "fakehost.example" not in body
          and "<GATEWAY>" in body, body[:300])
    check("stdout also masked", "FAKESECRET1234" not in out3)

    # --- gateway 404 -> discovery mode probes path variants, still masked ---
    import http.server
    import threading

    class _H404(http.server.BaseHTTPRequestHandler):
        def _reply(self):
            body = b'{"detail": "Not Found", "hint": "try /v1/chat/completions"}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._reply()

        def do_POST(self):
            self._reply()

        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H404)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    fake404 = tmp / "fake404.env"
    fake404.write_text(f"LIG_GATEWAY_BASE_URL=http://127.0.0.1:{port}/gw\n"
                       "LIG_API_KEY=FAKEKEY9999\n", encoding="utf-8")
    out_dir2 = tmp / "gw404"
    env4 = dict(env)
    env4.update({"LIG_API_ENV_FILE": str(fake404), "PROBE_OUT_DIR": str(out_dir2)})
    env4.pop("LIG_PROVIDER_PROFILE", None)
    r4 = subprocess.run(["py", "-3.11", str(WS_TEMPLATE / "agent_ops" / "probe_gateway.py")],
                        env=env4, capture_output=True, timeout=180)
    srv.shutdown()
    gw404_files = list(out_dir2.glob("probe_gateway_*.json"))
    check("404 gateway still completes and writes a result",
          r4.returncode == 0 and gw404_files,
          r4.stderr.decode("utf-8", errors="replace")[:300])
    body4 = gw404_files[0].read_text(encoding="utf-8")
    check("404 response body is captured (route hints preserved)",
          '"http_status": 404' in body4 and "try /v1/chat/completions" in body4, body4[:400])
    check("discovery mode lists path variants",
          '"discovery"' in body4 and body4.count("chat/completions") >= 3
          and '"discovery_hint"' in body4, body4[:400])
    check("discovery output masks key and host",
          "FAKEKEY9999" not in body4 and f"127.0.0.1:{port}" not in body4)

    print(f"\nALL {PASS} CHECKS PASSED (probes)")


if __name__ == "__main__":
    main()
