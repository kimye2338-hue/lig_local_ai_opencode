# -*- coding: utf-8 -*-
"""Loopback tests for the stdlib-only minimal WebSocket client.

Run: py -3.11 tests\test_ws_min.py
"""
from __future__ import annotations

import base64
import hashlib
import importlib
import json
import socket
import struct
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_ops.adapters.ws_min import WsClient, WsProtocolError, WsTimeout  # noqa: E402

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def accept_for(key: str) -> str:
    digest = hashlib.sha1((key + GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def recv_until(conn: socket.socket, marker: bytes) -> bytes:
    data = b""
    while marker not in data:
        chunk = conn.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def parse_headers(raw: bytes) -> Dict[str, str]:
    text = raw.decode("iso-8859-1", errors="replace")
    headers: Dict[str, str] = {}
    for line in text.split("\r\n")[1:]:
        if ":" in line:
            key, val = line.split(":", 1)
            headers[key.strip().lower()] = val.strip()
    return headers


def send_frame(conn: socket.socket, opcode: int, payload: bytes = b"", fin: bool = True) -> None:
    first = (0x80 if fin else 0) | opcode
    header = bytearray([first])
    length = len(payload)
    if length <= 125:
        header.append(length)
    elif length <= 0xFFFF:
        header.append(126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", length))
    conn.sendall(bytes(header) + payload)


def recv_frame(conn: socket.socket) -> tuple[int, bytes, bool]:
    first, second = recv_exact(conn, 2)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", recv_exact(conn, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", recv_exact(conn, 8))[0]
    mask = recv_exact(conn, 4) if masked else b""
    payload = recv_exact(conn, length) if length else b""
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return opcode, payload, masked


def recv_exact(conn: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            raise RuntimeError("socket closed")
        data += chunk
    return data


class MiniServer:
    def __init__(self, handler: Callable[[socket.socket], None], bad_accept: bool = False):
        self.handler = handler
        self.bad_accept = bad_accept
        self.ready = threading.Event()
        self.done = threading.Event()
        self.error: Optional[BaseException] = None
        self.port = 0
        self.thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> "MiniServer":
        self.thread.start()
        self.ready.wait(5)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.thread.join(5)
        check("server thread completed", not self.thread.is_alive())
        if self.error:
            raise self.error

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/devtools/page/1"

    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind(("127.0.0.1", 0))
                srv.listen(1)
                self.port = srv.getsockname()[1]
                self.ready.set()
                conn, _ = srv.accept()
                with conn:
                    conn.settimeout(5)
                    headers = parse_headers(recv_until(conn, b"\r\n\r\n"))
                    key = headers.get("sec-websocket-key", "")
                    accept = "bad-accept" if self.bad_accept else accept_for(key)
                    response = (
                        "HTTP/1.1 101 Switching Protocols\r\n"
                        "Upgrade: websocket\r\n"
                        "Connection: Upgrade\r\n"
                        f"Sec-WebSocket-Accept: {accept}\r\n"
                        "\r\n"
                    )
                    conn.sendall(response.encode("ascii"))
                    if not self.bad_accept:
                        self.handler(conn)
        except BaseException as exc:
            self.error = exc
        finally:
            self.done.set()


def echo_handler(conn: socket.socket) -> None:
    opcode, payload, masked = recv_frame(conn)
    check("client frame is masked", masked)
    check("server received text frame", opcode == 0x1)
    send_frame(conn, 0x1, payload)
    opcode, _, _ = recv_frame(conn)
    check("server received close frame", opcode == 0x8)
    send_frame(conn, 0x8)


def ping_then_echo_handler(conn: socket.socket) -> None:
    opcode, text_payload, masked = recv_frame(conn)
    check("client frame is masked", masked)
    check("server received text frame", opcode == 0x1)
    send_frame(conn, 0x9, b"are-you-there")
    opcode, payload, _ = recv_frame(conn)
    check("client replies pong", opcode == 0xA and payload == b"are-you-there")
    send_frame(conn, 0x1, text_payload)
    opcode, _, _ = recv_frame(conn)
    check("server received close frame", opcode == 0x8)
    send_frame(conn, 0x8)


def quiet_handler(conn: socket.socket) -> None:
    conn.settimeout(2)
    opcode, _, _ = recv_frame(conn)
    check("quiet server received text frame", opcode == 0x1)
    try:
        recv_frame(conn)
    except Exception:
        return


def binary_handler(conn: socket.socket) -> None:
    send_frame(conn, 0x2, b"not-supported")


def fragmented_handler(conn: socket.socket) -> None:
    send_frame(conn, 0x1, b"fragment", fin=False)


def roundtrip(payload: Any) -> Any:
    with MiniServer(echo_handler) as server:
        client = WsClient(server.url, timeout=3)
        client.send_json({"payload": payload})
        got = client.recv_json(timeout=3)
        client.close()
    return got["payload"]


def main() -> None:
    ws_min = importlib.import_module("agent_ops.adapters.ws_min")
    imported = set(getattr(ws_min, "__dict__", {}))
    banned = {"websocket", "websockets", "requests", "httpx"}
    check("no external websocket packages imported", not (imported & banned), str(imported & banned))

    check("short payload roundtrip", roundtrip("short") == "short")
    check("126-length payload roundtrip", roundtrip("x" * 200) == "x" * 200)
    long_payload = "z" * 70000
    check("127-length payload roundtrip", roundtrip(long_payload) == long_payload)
    check("korean payload roundtrip", roundtrip("한글 WebSocket 왕복") == "한글 WebSocket 왕복")

    with MiniServer(ping_then_echo_handler) as server:
        client = WsClient(server.url, timeout=3)
        client.send_json({"hello": "ping"})
        check("ping/pong then JSON", client.recv_json(timeout=3)["hello"] == "ping")
        client.close()

    with MiniServer(quiet_handler) as server:
        client = WsClient(server.url, timeout=3)
        client.send_json({"wait": True})
        try:
            client.recv_json(timeout=0.2)
            check("timeout raises", False)
        except WsTimeout:
            check("timeout raises", True)
        client.close()

    with MiniServer(binary_handler) as server:
        client = WsClient(server.url, timeout=3)
        try:
            client.recv_json(timeout=3)
            check("binary frame rejected", False)
        except WsProtocolError:
            check("binary frame rejected", True)
        client.close()

    with MiniServer(fragmented_handler) as server:
        client = WsClient(server.url, timeout=3)
        try:
            client.recv_json(timeout=3)
            check("fragmented frame rejected", False)
        except WsProtocolError:
            check("fragmented frame rejected", True)
        client.close()

    with MiniServer(lambda _conn: None, bad_accept=True) as server:
        try:
            WsClient(server.url, timeout=3)
            check("bad accept rejected", False)
        except WsProtocolError as exc:
            check("bad accept rejected", "Accept" in str(exc))

    for bad_url in ("wss://127.0.0.1:1/x", "ws://localhost:1/x"):
        try:
            WsClient(bad_url, timeout=0.1)
            check(f"unsupported URL rejected {bad_url}", False)
        except ValueError:
            check(f"unsupported URL rejected {bad_url}", True)

    print(f"\nALL {PASS} CHECKS PASSED (minimal websocket client)")


if __name__ == "__main__":
    main()
