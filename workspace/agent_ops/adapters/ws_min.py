# -*- coding: utf-8 -*-
"""Minimal stdlib WebSocket client for local Chrome CDP.

Scope is intentionally narrow: ws://127.0.0.1 only, text JSON frames only,
no compression, no binary messages, no fragmentation. Unsupported protocol
features raise explicit errors instead of silently misbehaving.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
from typing import Any, Dict, Optional
from urllib.parse import urlparse

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WsError(Exception):
    """Base error for the minimal WebSocket client."""


class WsProtocolError(WsError):
    """Raised for malformed or unsupported WebSocket protocol behavior."""


class WsTimeout(WsError):
    """Raised when a receive operation times out."""


def _accept_for(key: str) -> str:
    digest = hashlib.sha1((key + GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


class WsClient:
    """Small RFC6455 client sufficient for local Chrome CDP JSON traffic."""

    def __init__(self, url: str, timeout: float = 10):
        parsed = urlparse(url)
        if parsed.scheme != "ws":
            raise ValueError("only ws:// URLs are supported")
        if parsed.hostname != "127.0.0.1":
            raise ValueError("only ws://127.0.0.1 loopback URLs are supported")
        if parsed.username or parsed.password or parsed.params or parsed.fragment:
            raise ValueError("user info, params, and fragments are not supported")
        self.url = url
        self.host = parsed.hostname
        self.port = parsed.port or 80
        self.path = parsed.path or "/"
        if parsed.query:
            self.path += "?" + parsed.query
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self.closed = False
        self._connect()

    def _connect(self) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        # sendall/_read_http_header 실패 경로에서도 소켓이 새지 않도록 성공 시에만 이관.
        try:
            sock.sendall(request.encode("ascii"))
            header = self._read_http_header(sock)
            status, headers = self._parse_http_header(header)
            if not status.startswith("HTTP/1.1 101 ") and status != "HTTP/1.1 101":
                raise WsProtocolError(f"websocket upgrade failed: {status}")
            if headers.get("upgrade", "").lower() != "websocket":
                raise WsProtocolError("missing Upgrade: websocket response")
            if "upgrade" not in headers.get("connection", "").lower():
                raise WsProtocolError("missing Connection: Upgrade response")
            if headers.get("sec-websocket-accept", "") != _accept_for(key):
                raise WsProtocolError("invalid Sec-WebSocket-Accept")
        except Exception:
            try:
                sock.close()
            except Exception:
                pass
            raise
        self.sock = sock

    def _read_http_header(self, sock: socket.socket) -> bytes:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > 65536:
                raise WsProtocolError("HTTP upgrade response too large")
        if b"\r\n\r\n" not in data:
            raise WsProtocolError("incomplete HTTP upgrade response")
        return data.split(b"\r\n\r\n", 1)[0]

    def _parse_http_header(self, data: bytes) -> tuple[str, Dict[str, str]]:
        text = data.decode("iso-8859-1")
        lines = text.split("\r\n")
        status = lines[0].strip()
        headers: Dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                key, val = line.split(":", 1)
                headers[key.strip().lower()] = val.strip()
        return status, headers

    def send_json(self, obj: Any) -> None:
        self._send_frame(0x1, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def recv_json(self, timeout: Optional[float] = None) -> Any:
        payload = self._recv_text(timeout=timeout)
        return json.loads(payload)

    def close(self) -> None:
        if self.closed:
            return
        try:
            if self.sock:
                self._send_frame(0x8, b"")
        except OSError:
            pass
        finally:
            self.closed = True
            if self.sock:
                self.sock.close()
                self.sock = None

    def __enter__(self) -> "WsClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _require_sock(self) -> socket.socket:
        if self.closed or self.sock is None:
            raise WsProtocolError("websocket is closed")
        return self.sock

    def _kill(self) -> None:
        """프레임 중간 오류로 desync 된 연결을 즉시 죽여 재사용을 막는다."""
        self.closed = True
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        sock = self._require_sock()
        if opcode not in (0x1, 0x8, 0x9, 0xA):
            raise WsProtocolError(f"unsupported outgoing opcode: {opcode}")
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length <= 125:
            header.append(0x80 | length)
        elif length <= 0xFFFF:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        sock.sendall(bytes(header) + mask + masked)

    def _recv_exact(self, n: int) -> bytes:
        sock = self._require_sock()
        data = b""
        while len(data) < n:
            try:
                chunk = sock.recv(n - len(data))
            except socket.timeout as exc:
                # 부분 수신 바이트를 버리고 나중에 같은 소켓에서 다시 recv 하면
                # 프레임 경계가 어긋나 이후 수신이 전부 깨진다 — 연결을 죽인다.
                self._kill()
                raise WsTimeout("websocket receive timed out") from exc
            if not chunk:
                self._kill()
                raise WsProtocolError("socket closed while reading frame")
            data += chunk
        return data

    def _recv_text(self, timeout: Optional[float] = None) -> str:
        sock = self._require_sock()
        old_timeout = sock.gettimeout()
        if timeout is not None:
            sock.settimeout(timeout)
        try:
            while True:
                opcode, payload = self._recv_frame()
                if opcode == 0x1:
                    return payload.decode("utf-8")
                if opcode == 0x8:
                    self._kill()
                    raise WsProtocolError("websocket closed by peer")
                if opcode == 0x9:
                    self._send_frame(0xA, payload)
                    continue
                if opcode == 0xA:
                    continue
                raise WsProtocolError(f"unsupported opcode received: {opcode}")
        except WsError:
            # 프레임 파싱 실패도 스트림 desync 를 뜻하므로 연결을 회복 불능으로 처리.
            self._kill()
            raise
        finally:
            if self.sock is sock:
                sock.settimeout(old_timeout)

    def _recv_frame(self) -> tuple[int, bytes]:
        first, second = self._recv_exact(2)
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if not fin:
            raise WsProtocolError("fragmented frames are not supported")
        if opcode == 0x2:
            raise WsProtocolError("binary frames are not supported")
        if opcode not in (0x1, 0x8, 0x9, 0xA):
            raise WsProtocolError(f"unsupported opcode received: {opcode}")
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length) if length else b""
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return opcode, payload
