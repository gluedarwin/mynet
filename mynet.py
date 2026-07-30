"""
MNET — Lightweight secure protocol.
TLS-encrypted TCP with a minimal text-based request/response format.
Zero dependencies beyond the Python standard library.
"""

import ssl
import socket
import os
import subprocess
import threading
import time
import gzip
import hashlib
import json
import mimetypes
import re
from collections import OrderedDict
from functools import wraps
from urllib.parse import parse_qs, unquote

PROTOCOL = b"MNET/1.0"
CRLF = b"\r\n"
CRLF2 = b"\r\n\r\n"
BUFFER = 65536

# ── MIME types ────────────────────────────────────────────────────

MIME = {
    ".mn": "text/mn", ".html": "text/html", ".css": "text/css",
    ".js": "application/javascript", ".json": "application/json",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".svg": "image/svg+xml", ".ico": "image/x-icon",
    ".webp": "image/webp", ".mp4": "video/mp4", ".webm": "video/webm",
    ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".wav": "audio/wav",
    ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf",
    ".pdf": "application/pdf", ".txt": "text/plain",
}

MIME.update(mimetypes.types_map)

# ── certificate helpers ───────────────────────────────────────────

def generate_cert(cert_dir="certs"):
    cert = os.path.join(cert_dir, "cert.pem")
    key = os.path.join(cert_dir, "key.pem")
    if os.path.exists(cert) and os.path.exists(key):
        return cert, key
    os.makedirs(cert_dir, exist_ok=True)
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048",
         "-keyout", key, "-out", cert, "-days", "365", "-nodes",
         "-subj", "/CN=localhost"],
        check=True, capture_output=True,
    )
    return cert, key


def _server_ssl(cert_dir="certs"):
    cert, key = generate_cert(cert_dir)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    return ctx


def _client_ssl():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ── request / response ────────────────────────────────────────────

class Request:
    __slots__ = ("method", "path", "headers", "body", "query", "addr", "_route_params")

    def __init__(self, method="GET", path="/", headers=None, body=b""):
        self.method = method
        self.path = path
        self.headers = headers or {}
        self.body = body
        self.query = {}
        self.addr = ""
        self._route_params = {}
        self._parse_path()

    def _parse_path(self):
        if "?" in self.path:
            base, qs = self.path.split("?", 1)
            self.path = base
            self.query = {k: v[0] if len(v) == 1 else v
                          for k, v in parse_qs(qs).items()}

    def encode(self):
        lines = [PROTOCOL + b" " + self.method.encode() + b" " + self.path.encode()]
        for k, v in self.headers.items():
            lines.append(k.encode() + b": " + str(v).encode())
        if self.body:
            lines.append(b"Content-Length: " + str(len(self.body)).encode())
        return CRLF.join(lines) + CRLF2 + self.body

    @classmethod
    def decode(cls, raw):
        text = raw.decode(errors="replace")
        first, rest = text.split("\r\n", 1)
        parts = first.split(" ", 2)
        method = parts[1] if len(parts) > 1 else "GET"
        path = parts[2] if len(parts) > 2 else "/"
        headers = {}
        body = b""
        header_done = False
        body_lines = []
        for line in rest.split("\r\n"):
            if not header_done:
                if line == "":
                    header_done = True
                else:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        headers[k.strip()] = v.strip()
            else:
                body_lines.append(line)
        if body_lines:
            body = "\r\n".join(body_lines).encode()
        req = cls(method, path, headers, body)
        return req


class Response:
    __slots__ = ("status", "body", "headers")

    REASONS = {200: "OK", 206: "Partial Content", 301: "Moved",
               400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
               404: "Not Found", 416: "Range Not Satisfiable",
               500: "Error"}

    def __init__(self, status=200, body=b"", headers=None):
        self.status = status
        self.body = body if isinstance(body, bytes) else body.encode()
        self.headers = headers or {}

    def encode(self):
        reason = self.REASONS.get(self.status, "?")
        line = PROTOCOL + b" " + str(self.status).encode() + b" " + reason.encode()
        lines = [line]
        for k, v in self.headers.items():
            lines.append(k.encode() + b": " + str(v).encode())
        return CRLF.join(lines) + CRLF2 + self.body

    @classmethod
    def decode(cls, sock):
        hdr = b""
        while CRLF2 not in hdr:
            chunk = sock.recv(1)
            if not chunk:
                return None
            hdr += chunk
        header_raw, body_start = hdr.split(CRLF2, 1)
        lines = header_raw.decode().split("\r\n")
        parts = lines[0].split(" ", 2)
        status = int(parts[1]) if len(parts) > 1 else 200
        headers = {}
        content_length = 0
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip()
                headers[k] = v
                if k.lower() == "content-length":
                    content_length = int(v)
        body = body_start
        while len(body) < content_length:
            chunk = sock.recv(min(BUFFER, content_length - len(body)))
            if not chunk:
                break
            body += chunk
        return cls(status, body, headers)


# ── cache ─────────────────────────────────────────────────────────

class Cache:
    def __init__(self, max_size=256, ttl=300):
        self._data = OrderedDict()
        self._max = max_size
        self._ttl = ttl

    def get(self, key):
        if key in self._data:
            val, ts = self._data[key]
            if time.time() - ts < self._ttl:
                self._data.move_to_end(key)
                return val
            del self._data[key]
        return None

    def set(self, key, val):
        if key in self._data:
            del self._data[key]
        elif len(self._data) >= self._max:
            self._data.popitem(last=False)
        self._data[key] = (val, time.time())

    def clear(self):
        self._data.clear()


# ── middleware ─────────────────────────────────────────────────────

def compressiddleware(fn):
    @wraps(fn)
    def wrapper(req, *a, **kw):
        resp = fn(req, *a, **kw)
        accept = req.headers.get("Accept-Encoding", "")
        if "gzip" in accept and len(resp.body) > 100:
            compressed = gzip.compress(resp.body)
            resp.body = compressed
            resp.headers["Content-Encoding"] = "gzip"
            resp.headers["Content-Length"] = str(len(compressed))
        return resp
    return wrapper


def auth_middleware(token):
    def decorator(fn):
        @wraps(fn)
        def wrapper(req, *a, **kw):
            auth = req.headers.get("Authorization", "")
            if auth != f"Bearer {token}":
                return Response(401, b"Unauthorized", {"WWW-Authenticate": "Bearer"})
            return fn(req, *a, **kw)
        return wrapper
    return decorator


def log_middleware(fn):
    @wraps(fn)
    def wrapper(req, *a, **kw):
        t0 = time.time()
        resp = fn(req, *a, **kw)
        dt = (time.time() - t0) * 1000
        ts = time.strftime("%H:%M:%S")
        status = getattr(resp, 'status', '?')
        print(f"[{ts}] {req.method} {req.path} → {status} ({dt:.0f}ms)")
        return resp
    return wrapper


# ── server ────────────────────────────────────────────────────────

class Server:
    def __init__(self, host="0.0.0.0", port=7443, cert_dir="certs",
                 static_dir=None, token=None):
        self.host = host
        self.port = port
        self.cert_dir = cert_dir
        self.static_dir = static_dir
        self.token = token
        self.routes = {}
        self.cache = Cache()
        self.ws_handlers = {}
        self._log_lock = threading.Lock()

    def route(self, path, methods=None):
        def dec(f):
            self.routes[path] = (f, methods or ["GET", "POST"])
            return f
        return dec

    def ws(self, path):
        def dec(f):
            self.ws_handlers[path] = f
            return f
        return dec

    def _log(self, msg):
        with self._log_lock:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] {msg}")

    def start(self):
        ctx = _server_ssl(self.cert_dir)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen(32)
            with ctx.wrap_socket(s, server_side=True) as tls:
                self._log(f"MNET server listening on {self.host}:{self.port}")
                try:
                    while True:
                        cli, addr = tls.accept()
                        cli_addr = f"{addr[0]}:{addr[1]}"
                        t = threading.Thread(target=self._safe_handle,
                                             args=(cli, cli_addr), daemon=True)
                        t.start()
                except KeyboardInterrupt:
                    self._log("Server stopped.")

    def _safe_handle(self, cli, addr):
        try:
            self._handle(cli, addr)
        except Exception as e:
            self._log(f"[ERR] {addr} {e}")
        finally:
            cli.close()

    def _handle(self, cli, addr):
        raw = cli.recv(BUFFER)
        if not raw:
            return

        # Check for WebSocket upgrade
        text = raw.decode(errors="replace")
        if "Upgrade: websocket" in text or "upgrade: websocket" in text:
            self._handle_ws(cli, raw, addr)
            return

        req = Request.decode(raw)
        req.addr = addr

        # Route matching
        handler = None
        for pattern, (fn, methods) in self.routes.items():
            if self._match(pattern, req.path):
                if req.method in methods:
                    handler = fn
                    req._route_params = self._extract(pattern, req.path)
                    break

        # Static files fallback
        if handler is None and self.static_dir:
            handler = self._static_handler

        if handler:
            # Normalize handler output first
            def _norm(req):
                resp = handler(req)
                if isinstance(resp, str):
                    return Response(200, resp, {"Content-Type": "text/mn"})
                if isinstance(resp, bytes):
                    return Response(200, resp, {"Content-Type": "text/mn"})
                if isinstance(resp, Response):
                    return resp
                return Response(200, str(resp).encode(), {"Content-Type": "text/mn"})

            fn = _norm
            if self.token:
                fn = auth_middleware(self.token)(fn)
            fn = log_middleware(fn)
            fn = compressiddleware(fn)

            resp = fn(req)

            # Add default headers
            resp.headers.setdefault("Server", "MNET/1.0")
            resp.headers.setdefault("Content-Length", str(len(resp.body)))
            resp.headers.setdefault("Connection", "close")

            cli.sendall(resp.encode())
        else:
            body = b"404 Not Found"
            resp = Response(404, body, {
                "Content-Length": str(len(body)),
                "Content-Type": "text/plain"
            })
            cli.sendall(resp.encode())

    def _match(self, pattern, path):
        pattern_parts = pattern.strip("/").split("/")
        path_parts = path.strip("/").split("/")
        if len(pattern_parts) != len(path_parts):
            return False
        for pp, rp in zip(pattern_parts, path_parts):
            if pp.startswith("{") and pp.endswith("}"):
                continue
            if pp != rp:
                return False
        return True

    def _extract(self, pattern, path):
        params = {}
        pattern_parts = pattern.strip("/").split("/")
        path_parts = path.strip("/").split("/")
        for pp, rp in zip(pattern_parts, path_parts):
            if pp.startswith("{") and pp.endswith("}"):
                params[pp[1:-1]] = unquote(rp)
        return params

    def _static_handler(self, req):
        # Range request support
        file_path = os.path.join(self.static_dir, req.path.lstrip("/"))
        if not os.path.isfile(file_path):
            return Response(404, b"File not found")

        ext = os.path.splitext(file_path)[1].lower()
        content_type = MIME.get(ext, "application/octet-stream")
        file_size = os.path.getsize(file_path)

        # Range request
        range_header = req.headers.get("Range", "")
        if range_header:
            return self._range_response(file_path, content_type, file_size, range_header)

        with open(file_path, "rb") as f:
            data = f.read()

        return Response(200, data, {
            "Content-Type": content_type,
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        })

    def _range_response(self, file_path, content_type, file_size, range_header):
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not m:
            return Response(416, b"Invalid range")

        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else file_size - 1
        end = min(end, file_size - 1)

        if start >= file_size or start > end:
            return Response(416, b"Range not satisfiable")

        with open(file_path, "rb") as f:
            f.seek(start)
            data = f.read(end - start + 1)

        return Response(206, data, {
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
        })

    def _handle_ws(self, cli, raw, addr):
        """Minimal WebSocket handshake + echo."""
        text = raw.decode(errors="replace")
        key_match = re.search(r"Sec-WebSocket-Key:\s*(.+)", text)
        if not key_match:
            cli.close()
            return

        ws_key = key_match.group(1).strip()
        accept_key = hashlib.sha1(
            (ws_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
        ).digest()
        import base64
        accept_b64 = base64.b64encode(accept_key).decode()

        resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_b64}\r\n"
            "\r\n"
        )
        cli.sendall(resp.encode())

        path_match = re.search(r"GET\s+(.+?)\s+HTTP", text)
        ws_path = path_match.group(1) if path_match else "/"
        handler = self.ws_handlers.get(ws_path)

        if handler:
            try:
                handler(WsSocket(cli), addr)
            except Exception as e:
                self._log(f"[WS ERR] {e}")
        else:
            # Default echo
            try:
                ws = WsSocket(cli)
                while True:
                    msg = ws.recv()
                    if msg is None:
                        break
                    ws.send(msg)
            except Exception:
                pass
        cli.close()


# ── WebSocket helper ──────────────────────────────────────────────

class WsSocket:
    def __init__(self, sock):
        self.sock = sock

    def recv(self):
        header = self._recv_exact(2)
        if not header:
            return None
        opcode = header[0] & 0x0F
        masked = header[1] & 0x80
        length = header[1] & 0x7F

        if length == 126:
            ext = self._recv_exact(2)
            length = int.from_bytes(ext, "big")
        elif length == 127:
            ext = self._recv_exact(8)
            length = int.from_bytes(ext, "big")

        mask_key = self._recv_exact(4) if masked else None
        payload = self._recv_exact(length)

        if not payload:
            return None

        if masked and mask_key:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

        if opcode == 0x8:
            return None
        if opcode == 0x1:
            return payload.decode(errors="replace")
        return payload

    def send(self, data):
        if isinstance(data, str):
            data = data.encode()
        header = bytearray()
        header.append(0x81)
        length = len(data)
        if length < 126:
            header.append(length)
        elif length < 65536:
            header.append(126)
            header.extend(length.to_bytes(2, "big"))
        else:
            header.append(127)
            header.extend(length.to_bytes(8, "big"))
        self.sock.sendall(bytes(header) + data)

    def _recv_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data


# ── file upload helper ────────────────────────────────────────────

def parse_upload(body, boundary):
    """Parse multipart/form-data. Returns list of {name, filename, data}."""
    parts = []
    sep = ("--" + boundary).encode()
    chunks = body.split(sep)
    for chunk in chunks[1:]:
        if chunk.strip() == b"--" or not chunk.strip():
            continue
        if b"\r\n\r\n" in chunk:
            header_raw, data = chunk.split(b"\r\n\r\n", 1)
            if data.endswith(b"\r\n"):
                data = data[:-2]
            headers = header_raw.decode(errors="replace")
            name_m = re.search(r'name="([^"]+)"', headers)
            fn_m = re.search(r'filename="([^"]+)"', headers)
            parts.append({
                "name": name_m.group(1) if name_m else "",
                "filename": fn_m.group(1) if fn_m else "",
                "data": data,
            })
    return parts


# ── JSON helpers ──────────────────────────────────────────────────

def json_response(data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode()
    return Response(status, body, {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    })


def json_body(req):
    try:
        return json.loads(req.body) if req.body else {}
    except Exception:
        return {}


# ── client ────────────────────────────────────────────────────────

def fetch(host, path="/", port=7443, headers=None):
    """Fetch a resource from a MNET server. Returns a Response."""
    req = Request("GET", path, {"Host": host, **(headers or {})})
    ctx = _client_ssl()
    with socket.create_connection((host, port)) as raw:
        with ctx.wrap_socket(raw, server_hostname=host) as tls:
            tls.sendall(req.encode())
            return Response.decode(tls)


def post(host, path="/", data=b"", port=7443, headers=None):
    """POST data to a MNET server. Returns a Response."""
    h = {"Host": host, "Content-Length": str(len(data)), **(headers or {})}
    req = Request("POST", path, h, data)
    ctx = _client_ssl()
    with socket.create_connection((host, port)) as raw:
        with ctx.wrap_socket(raw, server_hostname=host) as tls:
            tls.sendall(req.encode())
            return Response.decode(tls)
