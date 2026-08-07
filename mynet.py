"""
MNET — Lightweight secure protocol.
TLS-encrypted TCP with a minimal text-based request/response format.
Zero dependencies beyond the Python standard library.
"""

import ssl
import socket
import sys
import os
import subprocess
import threading
import time
import gzip
import hashlib
import json
import mimetypes
import re
import argparse
from collections import OrderedDict
from functools import wraps
from urllib.parse import parse_qs, unquote

PROTOCOL = b"MNET/1.0"
CRLF = b"\r\n"
CRLF2 = b"\r\n\r\n"
BUFFER = 65536

# ── Security constants ─────────────────────────────────────────────────

SECRET_KEY = os.environ.get("MNET_SECRET_KEY", "")
RATE_LIMIT_REQUESTS = int(os.environ.get("MNET_RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.environ.get("MNET_RATE_LIMIT_WINDOW", "900"))
MAX_REQUEST_SIZE = int(os.environ.get("MNET_MAX_REQUEST_SIZE", "1048576"))

# ── CORS headers ───────────────────────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
}

# ── Security headers ───────────────────────────────────────────────────

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

# ── rate limiting and session stores ───────────────────────────────────

_rate_limit_store = {}
_session_store = {}

# ── MIME types ────────────────────────────────────────────────────

MIME = {
    ".mn": "text/mn", ".html": "text/html", ".css": "text/css",
    ".js": "application/javascript", ".json": "application/json",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".svg": "image/svg+xml", ".ico": "image/x-icon",
    ".webp": "image/webp", ".mp4": "video/mp4", ".webm": "video/webm",
    ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".wav": "audio/wav",
    ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf",
    ".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown",
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


def _resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base = sys._MEIPASS
    except Exception:
        base = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base, relative_path)


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


# ── browser integration ─────────────────────────────────────────────────

BROWSER_SIZE_MAP = {"h1": 32, "h2": 26, "h3": 22, "h4": 18, "h5": 14, "h6": 12}

BROWSER_DATA_DIR = os.path.expanduser("~/.mynet")

def _browser_load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default or []


def _browser_save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class BrowserTab:
    __slots__ = ("url", "title", "source", "headers")

    def __init__(self, url="", title="New Tab", source="", headers=None):
        self.url = url
        self.title = title
        self.source = source
        self.headers = headers or {}


# ── markdown parser ─────────────────────────────────────────────────────

def parse_md(source):
    """Parse Markdown content into HTML."""
    if not source:
        return ""
    
    import html as html_module
    
    lines = source.split("\n")
    html_parts = []
    in_code_block = False
    code_lines = []
    in_list = False
    list_type = None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if not stripped:
            if in_code_block:
                code_lines.append(line)
            elif in_list:
                html_parts.append("</ul>" if list_type == "ul" else "</ol>")
                in_list = False
                list_type = None
            i += 1
            continue
        
        if stripped.startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_lines = []
            else:
                code = "\n".join(code_lines)
                html_parts.append(f"<pre><code>{html_module.escape(code)}</code></pre>")
                in_code_block = False
                code_lines = []
            i += 1
            continue
        
        if in_code_block:
            code_lines.append(line)
            i += 1
            continue
        
        h_match = re.match(r'^(#{1,6})\s+(.+)', stripped)
        if h_match:
            if in_list:
                html_parts.append("</ul>" if list_type == "ul" else "</ol>")
                in_list = False
                list_type = None
            level = len(h_match.group(1))
            content = h_match.group(2)
            html_parts.append(f"<h{level}>{html_module.escape(content)}</h{level}>")
            i += 1
            continue
        
        if stripped.startswith("> "):
            content = stripped[2:]
            html_parts.append(f"<blockquote>{html_module.escape(content)}</blockquote>")
            i += 1
            continue
        
        if stripped.startswith("- ") or stripped.startswith("* "):
            item = stripped[2:]
            if not in_list or list_type != "ul":
                if in_list:
                    html_parts.append("</ul>")
                html_parts.append("<ul>")
                in_list = True
                list_type = "ul"
            html_parts.append(f"<li>{item}</li>")
            i += 1
            continue
        
        num_match = re.match(r'^(\d+)\.\s+(.+)', stripped)
        if num_match:
            item = num_match.group(2)
            if not in_list or list_type != "ol":
                if in_list:
                    html_parts.append("</ol>")
                html_parts.append("<ol>")
                in_list = True
                list_type = "ol"
            html_parts.append(f"<li>{item}</li>")
            i += 1
            continue
        
        if stripped in ("---", "***", "___"):
            if in_list:
                html_parts.append("</ul>" if list_type == "ul" else "</ol>")
                in_list = False
                list_type = None
            html_parts.append("<hr>")
            i += 1
            continue
        
        content = stripped
        content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
        content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)
        
        link_match = re.match(r'\[([^\]]+)\]\(([^)]+)\)', content)
        if link_match:
            text = link_match.group(1)
            url = link_match.group(2)
            html_parts.append(f'<a href="{html_module.escape(url, quote=True)}">{html_module.escape(text)}</a>')
            i += 1
            continue
        
        img_match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', content)
        if img_match:
            alt = img_match.group(1)
            src = img_match.group(2)
            html_parts.append(f'<img src="{html_module.escape(src, quote=True)}" alt="{html_module.escape(alt)}">')
            i += 1
            continue
        
        if in_list:
            html_parts.append("</ul>" if list_type == "ul" else "</ol>")
            in_list = False
            list_type = None
        
        html_parts.append(f"<p>{content}</p>")
        i += 1
    
    if in_list:
        html_parts.append("</ul>" if list_type == "ul" else "</ol>")
    
    return "\n".join(html_parts)


def parse_md_dom(source):
    """Parse Markdown into DOM elements for browser rendering."""
    
    class Element:
        __slots__ = ("tag", "text", "children", "attrs")
        def __init__(self, tag="p", text="", children=None, attrs=None):
            self.tag = tag
            self.text = text
            self.children = children or []
            self.attrs = attrs or {}
        def append(self, child):
            self.children.append(child)

    if not source:
        return []
    
    elements = []
    lines = source.split("\n")
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if not stripped:
            i += 1
            continue
        
        h_match = re.match(r'^(#{1,6})\s+(.+)', stripped)
        if h_match:
            level = len(h_match.group(1))
            text = h_match.group(2)
            elements.append(Element(f"h{level}", text))
            i += 1
            continue
        
        if stripped.startswith("> "):
            content = stripped[2:]
            elements.append(Element("blockquote", content))
            i += 1
            continue
        
        if stripped.startswith("- ") or stripped.startswith("* "):
            list_el = Element("ul")
            while i < len(lines):
                l = lines[i]
                ls = l.strip()
                if (ls.startswith("- ") or ls.startswith("* ")):
                    item = ls[2:]
                    list_el.append(Element("li", item))
                    i += 1
                else:
                    break
            elements.append(list_el)
            continue
        
        num_match = re.match(r'^(\d+)\.\s+(.+)', stripped)
        if num_match:
            list_el = Element("ol")
            while i < len(lines):
                l = lines[i]
                ls = l.strip()
                nm = re.match(r'^(\d+)\.\s+(.+)', ls)
                if nm:
                    item = nm.group(2)
                    list_el.append(Element("li", item))
                    i += 1
                else:
                    break
            elements.append(list_el)
            continue
        
        if stripped in ("---", "***", "___"):
            elements.append(Element("hr"))
            i += 1
            continue
        
        link_match = re.match(r'^\[([^\]]+)\]\(([^)]+)\)', stripped)
        if link_match:
            text = link_match.group(1)
            href = link_match.group(2)
            elements.append(Element("link", text, attrs={"_0": href, "href": href}))
            i += 1
            continue
        
        img_match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', stripped)
        if img_match:
            alt = img_match.group(1)
            src = img_match.group(2)
            elements.append(Element("image", alt or "image", attrs={"_0": src, "src": src}))
            i += 1
            continue
        
        if stripped.startswith("```"):
            lang = stripped[3:].strip() if stripped[3:].strip() else "code"
            code_lines = []
            i += 1
            while i < len(lines):
                if lines[i].startswith("```"):
                    break
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            code_el = Element("code", "\n".join(code_lines))
            pre_el = Element("pre")
            pre_el.append(code_el)
            elements.append(pre_el)
            continue
        
        content = stripped
        bold_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
        italic_content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', bold_content)
        
        if "<strong>" in italic_content or "<em>" in italic_content:
            elements.append(Element("p", italic_content))
        else:
            elements.append(Element("p", content))
        i += 1
    
    return elements


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


def rate_limit_middleware(fn):
    """Rate limiting middleware - limits requests per IP."""
    @wraps(fn)
    def wrapper(req, *a, **kw):
        client_ip = req.addr.split(':')[0] if req.addr else 'unknown'
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW

        if client_ip not in _rate_limit_store:
            _rate_limit_store[client_ip] = []

        _rate_limit_store[client_ip] = [t for t in _rate_limit_store[client_ip] if t > window_start]

        if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
            retry_after = int(window_start + RATE_LIMIT_WINDOW - now)
            return Response(429, f"Rate limit exceeded. Try again in {retry_after} seconds.", {
                "Retry-After": str(retry_after),
                **CORS_HEADERS,
                **SECURITY_HEADERS,
            })

        _rate_limit_store[client_ip].append(now)
        return fn(req, *a, **kw)
    return wrapper


def security_middleware(fn):
    """Add security and CORS headers to responses."""
    @wraps(fn)
    def wrapper(req, *a, **kw):
        resp = fn(req, *a, **kw)
        if isinstance(resp, Response):
            headers = dict(resp.headers)
            headers.update(CORS_HEADERS)
            headers.update(SECURITY_HEADERS)
            if req.method == "OPTIONS":
                headers["Allow"] = "GET, POST, PUT, DELETE, OPTIONS"
            return Response(resp.status, resp.body, headers)
        return resp
    return wrapper


def auth_session_middleware():
    """Create authentication session middleware."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(req, *a, **kw):
            token = req.headers.get("Authorization", "")
            if SECRET_KEY:
                if not token.startswith("Bearer "):
                    return Response(401, "Authentication required", {
                        "WWW-Authenticate": "Bearer",
                        **CORS_HEADERS,
                        **SECURITY_HEADERS,
                    })
                token = token[7:]
                session_id = hashlib.sha256(f"{token}{SECRET_KEY}".encode()).hexdigest()
                if session_id not in _session_store:
                    return Response(401, "Invalid or expired token", {
                        **CORS_HEADERS,
                        **SECURITY_HEADERS,
                    })
                req.session = _session_store[session_id]
                req.session['last_access'] = time.time()
            return fn(req, *a, **kw)
        return wrapper
    return decorator


def metrics_middleware(fn):
    """Add request metrics tracking."""
    _metrics = {
        'requests_total': 0,
        'responses_2xx': 0,
        'responses_4xx': 0,
        'responses_5xx': 0,
        'start_time': time.time(),
    }

    @wraps(fn)
    def wrapper(req, *a, **kw):
        _metrics['requests_total'] += 1
        try:
            resp = fn(req, *a, **kw)
            status = getattr(resp, 'status', 200)
            if 200 <= status < 300:
                _metrics['responses_2xx'] += 1
            elif 400 <= status < 500:
                _metrics['responses_4xx'] += 1
            elif 500 <= status < 600:
                _metrics['responses_5xx'] += 1
            if isinstance(resp, Response):
                headers = dict(resp.headers)
                headers["X-Request-ID"] = hashlib.md5(f"{req.path}{time.time()}".encode()).hexdigest()[:8]
                headers.update(SECURITY_HEADERS)
                return Response(status, resp.body, headers)
            return resp
        except Exception as e:
            _metrics['responses_5xx'] += 1
            return Response(500, f"Internal server error: {str(e)}", {
                **CORS_HEADERS,
                **SECURITY_HEADERS,
            })

    def get_metrics():
        return {
            'uptime': time.time() - _metrics['start_time'],
            'requests_total': _metrics['requests_total'],
            'responses_2xx': _metrics['responses_2xx'],
            'responses_4xx': _metrics['responses_4xx'],
            'responses_5xx': _metrics['responses_5xx'],
            'rate_limit_entries': len(_rate_limit_store),
            'active_sessions': len(_session_store),
        }

    wrapper.get_metrics = get_metrics
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
        self._start_time = time.time()

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

    def metrics(self):
        """Return server metrics."""
        return {
            'uptime': time.time() - self._start_time,
            'routes': len(self.routes),
            'ws_handlers': len(self.ws_handlers),
            'cache_size': len(self.cache._data),
            'rate_limit_entries': len(_rate_limit_store),
            'active_sessions': len(_session_store),
        }

    def _log(self, msg):
        with self._log_lock:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] {msg}")

    def start(self):
        cert_dir = self.cert_dir
        if getattr(sys, "frozen", False):
            cert_dir = _resource_path(cert_dir)
        ctx = _server_ssl(cert_dir)
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
                    return Response(200, resp, {"Content-Type": "text/markdown"})
                if isinstance(resp, bytes):
                    return Response(200, resp, {"Content-Type": "text/markdown"})
                if isinstance(resp, Response):
                    return resp
                return Response(200, str(resp).encode(), {"Content-Type": "text/markdown"})

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
            resp.headers.update(CORS_HEADERS)
            resp.headers.update(SECURITY_HEADERS)

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

# ── browser run ───────────────────────────────────────────────────────

def _browser_run(markdown_file, port=7443, host="0.0.0.0", cert_dir="certs"):
    """Run the MNET server with browser integration."""
    if getattr(sys, "frozen", False):
        cert_dir = _resource_path(cert_dir)
    
    tabs_file = os.path.join(BROWSER_DATA_DIR, "tabs.json")
    history_file = os.path.join(BROWSER_DATA_DIR, "history.json")
    
    tabs = _browser_load_json(tabs_file, [])
    history = _browser_load_json(history_file, [])
    
    try:
        with open(markdown_file, "r", encoding="utf-8") as f:
            markdown_content = f.read()
    except FileNotFoundError:
        markdown_content = "# mynet\n\nMarkdown file not found.\n"
    
    html_content = parse_md(markdown_content)
    
    app = Server(host=host, port=port, cert_dir=cert_dir)
    
    @app.route("/")
    def index(req):
        return html_content
    
    @app.route("/api/tabs")
    def api_tabs(req):
        return json_response({"tabs": tabs, "history": history})
    
    @app.route("/api/tabs/add")
    def add_tab(req):
        if req.method == "POST":
            data = json_body(req)
            tab = BrowserTab(
                url=data.get("url", ""),
                title=data.get("title", "New Tab"),
                source=data.get("source", ""),
                headers=data.get("headers", {})
            )
            tabs.append({
                "url": tab.url,
                "title": tab.title,
                "source": tab.source,
                "headers": tab.headers,
            })
            _browser_save_json(tabs_file, tabs)
        return json_response({"tabs": tabs})
    
    @app.route("/api/metrics")
    def metrics_endpoint(req):
        return json_response(app.metrics())
    
    print(f"Serving {markdown_file} on https://{host}:{port}")
    print(f"Browse content available at: https://{host}:{port}/")
    app.start()


# ── CLI ───────────────────────────────────────────────────────────────

def main_cli():
    parser = argparse.ArgumentParser(
        prog="mynet",
        description="MNET — Lightweight secure protocol server with browser integration"
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Markdown file to serve (e.g., mynet index.md)"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", "-p", type=int, default=7443, help="Port (default: 7443)")
    parser.add_argument("--cert-dir", default="certs", help="Certificate directory")
    parser.add_argument("--browser", "-b", action="store_true", help="Enable browser mode")
    parser.add_argument("--token", default=None, help="Authentication token")
    parser.add_argument("--version", "-V", action="version", version="mynet 1.0")
    
    args = parser.parse_args()
    
    if args.file:
        markdown_file = args.file
        if not os.path.isabs(markdown_file):
            markdown_file = os.path.abspath(markdown_file)
        
        if not os.path.exists(markdown_file):
            print(f"Error: File not found: {markdown_file}")
            return 1
        
        if args.browser:
            _browser_run(markdown_file, port=args.port, host=args.host, cert_dir=args.cert_dir)
        else:
            serve_md(markdown_file, port=args.port, host=args.host, cert_dir=args.cert_dir)
    else:
        print("mynet — Lightweight secure protocol server")
        print(f"Use 'mynet <file>.md' to serve a markdown file")
        print(f"Use 'mynet --help' for options")
        return 0
    
    return 0


def serve_md(path, port=7443, host="0.0.0.0", cert_dir="certs"):
    """Serve a markdown file."""
    if getattr(sys, "frozen", False):
        cert_dir = _resource_path(cert_dir)
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
    except FileNotFoundError:
        markdown_content = "# File not found\n\n"
    
    html_content = parse_md(markdown_content)
    app = Server(host=host, port=port, cert_dir=cert_dir)
    
    @app.route("/")
    def index(req):
        return html_content
    
    @app.route("/api/metrics")
    def metrics_endpoint(req):
        return json_response(app.metrics())
    
    app.start()


if __name__ == "__main__":
    import sys
    sys.exit(main_cli())
