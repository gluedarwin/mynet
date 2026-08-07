"""
Example MyNet server — demonstrates all new features.
Run:  ./run_server.sh
Open: mynet://localhost:7443/
"""

import os
import mynet

# Create public dir for static files
os.makedirs("public", exist_ok=True)

app = mynet.Server(
    port=7443,
    static_dir="public",    # ← static files from ./public/
    # token="mysecret123",  # ← uncomment for auth
)

HOME = """\
# Welcome to MyNet

This is a sample page on the MNET protocol.

---

## Server Features

- Static files (images, video, audio)
- Automatic gzip compression
- Response caching
- Range Request (partial downloads)
- Request logging
- File upload
- Token authentication
- WebSocket
- JSON API
- Custom headers

---

## Sample Pages

- [About MyNet](mynet://localhost:7443/about)
- [Tag Demo](mynet://localhost:7443/demo)
- [JSON API](mynet://localhost:7443/api)
- [Upload Page](mynet://localhost:7443/upload)
- [WebSocket Chat](mynet://localhost:7443/ws-chat)

---

### Media

Sample video:

```
[video: mynet://localhost:7443/sample.mp4]
```

Sample audio:

```
[audio: mynet://localhost:7443/sample.mp3]
```

---

```
pip install customtkinter
```
"""

ABOUT = """\
# About MyNet

MyNet is a lightweight, secure alternative to HTTPS.

## MNET Protocol

- TLS Encryption
- Lightweight request/response format
- Range Request support
- Gzip compression

## MN Language

Syntax similar to Python:

```
title: My Page

h1: Hello World

p: A paragraph

ul:
    - First item
    - Second item

hr:

link("mynet://localhost:7443/"): Home
```

- [Home](mynet://localhost:7443/)
"""

DEMO = """\
# Tag Demo

---

## Headings

# h1 Heading
## h2 Heading
### h3 Heading
#### h4 Heading

---

## Text

This is a normal paragraph.

**This text is bold.**

```
This is code
```

---

## Lists

### Unordered List
- Item 1
- Item 2
- Item 3

### Ordered List
1. First
2. Second
3. Third

---

## Links

- [Home](mynet://localhost:7443/)
- [About](mynet://localhost:7443/about)
"""

API = """\
# JSON API

This page is a simple JSON API.

```
GET /api/data → JSON
POST /api/data → JSON
```

To test:

```
curl -k mynet://localhost:7443/api/data
```

- [Home](mynet://localhost:7443/)
"""

UPLOAD_PAGE = """\
# File Upload

Use the Upload button in the toolbar.

Files are sent to the server.

- [Home](mynet://localhost:7443/)
"""

WS_CHAT = """\
# WebSocket Chat

This page supports WebSocket.

More features coming soon...

- [Home](mynet://localhost:7443/)
"""


# ── Routes ────────────────────────────────────────────────────────

@app.route("/")
def index(req):
    return mynet.parse_md(HOME)

@app.route("/about")
def about(req):
    return mynet.parse_md(ABOUT)

@app.route("/demo")
def demo(req):
    return mynet.parse_md(DEMO)

@app.route("/upload")
def upload(req):
    return mynet.parse_md(UPLOAD_PAGE)

@app.route("/ws-chat")
def ws_chat(req):
    return mynet.parse_md(WS_CHAT)


# ── JSON API ──────────────────────────────────────────────────────

@app.route("/api/data")
def api_data(req):
    return mynet.json_response({
        "status": "ok",
        "protocol": "MNET/1.0",
        "features": ["cache", "gzip", "range", "ws", "upload", "auth"],
    })


@app.route("/api/echo", methods=["POST"])
def api_echo(req):
    data = mynet.json_body(req)
    return mynet.json_response({"echo": data})


# ── WebSocket handler ─────────────────────────────────────────────

@app.ws("/ws")
def ws_handler(ws, addr):
    print(f"[WS] {addr} connected")
    try:
        while True:
            msg = ws.recv()
            if msg is None:
                break
            ws.send(f"echo: {msg}")
            print(f"[WS] {addr}: {msg}")
    except Exception:
        pass
    print(f"[WS] {addr} disconnected")


if __name__ == "__main__":
    app.start()
