# mynet 🔱

**mynet** — A fully independent, lightweight, secure, and lean HTTPS replacement.
No bloat. No fluff. Three tools, zero dependencies beyond the Python standard library.

```
MNET  →  TLS + minimal text protocol (the replacement for HTTPS)
MNML  →  Python-like markup language (the replacement for HTML)
Browser → customtkinter GUI that speaks MNET and renders MNML
```

---

## TL;DR

```bash
# 1. Create a project
mkdir mynet && cd mynet

# 2. Start the server
./run_server.sh          # or: source .venv/bin/activate && python server.py

# 3. Open the browser
./run_browser.sh         # or: source .venv/bin/activate && python browser.py

# 4. Navigate to
#    mynet://localhost:7443/
```

---

## Architecture

```
┌─────────────┐     MNET/1.0 + TLS     ┌────────────────┐
│  Browser    │ ◄─────────────────────► │  Server        │
│  (GUI)      │     mynet://host:port/  │  (MynetServer) │
│  customtk-  │                          │                │
│  inter      │                          │  Routes, Cache │
│             │                          │  Auth, WS, etc │
└─────────────┘                          └────────────────┘
         │                                      │
         ▼                                      ▼
    ┌──────────┐                          ┌────────────┐
    │ MNML     │  Python-like syntax      │ Static     │
    │ Parser   │  → renders to widgets    │ File Server │
    │          │                          │ (range req) │
    └──────────┘                          └────────────┘
```

---

## What's Inside

### 1. `mynet.py` — The Protocol Engine

| Feature           | Details                                      |
|-------------------|----------------------------------------------|
| Protocol          | `MNET/1.0` over TLS                         |
| Encryption        | Python `ssl` module (no crypto hand-rolled) |
| Server            | Multi-threaded, concurrent connections      |
| Client            | `fetch()` / `post()` helper functions       |
| Cache             | In-memory LRU with TTL                      |
| Compression       | Automatic gzip for responses > 100 bytes    |
| Range Requests    | `bytes=0-499` partial downloads             |
| Static Files      | Serve any file type with auto MIME detection|
| Authentication    | Bearer token middleware                     |
| WebSocket         | Built-in WS upgrade handler + echo server   |
| File Upload       | multipart/form-data parsing                 |
| JSON API          | `json_response()` / `json_body()` helpers   |
| Logging           | Timestamped request log                     |
| Custom Headers    | Full control over response headers          |

### 2. `mn.py` — MNML Parser

| Tag      | Purpose                       | Example                                  |
|----------|-------------------------------|------------------------------------------|
| `title`  | Page title (browser window)   | `title: My Page`                         |
| `h1-h6`  | Headings                      | `h1: Main Heading`                       |
| `p`      | Paragraph                     | `p: Some text here`                      |
| `bold`   | Bold text                     | `bold: Important`                        |
| `italic` | Italic text                   | `italic: Emphasized`                     |
| `code`   | Inline code block             | `code: x = 42`                           |
| `pre`    | Preformatted block            | `pre:\n    indented text`                |
| `ul`     | Unordered list                | `ul:\n    - item1`                       |
| `ol`     | Ordered list                  | `ol:\n    - first`                       |
| `li`     | List item (auto-parsed)       | `- item`                                 |
| `link`   | Hyperlink                     | `link("https://example.com"): Click`     |
| `image`  | Image placeholder             | `image("pic.png")`                       |
| `video`  | Video element                 | `video("clip.mp4")`                      |
| `audio`  | Audio element                 | `audio("song.mp3")`                      |
| `table`  | Table with rows/cells         | `table:\n    row:\n        cell: A`       |
| `form`   | Form with inputs              | `form(action):\n    input(name="user")`   |
| `input`  | Form input field              | `input(type="text", placeholder="Name")` |
| `button` | Clickable button              | `button: Submit`                         |
| `hr`     | Horizontal rule               | `hr:`                                    |

**Syntax rules:**
- Indentation = nesting (like Python)
- No closing tags
- `tag(args): content` for tags with arguments
- `tag: content` for simple tags
- `- value` for list items
- `# comment` for comments

**Bonus:** `mn.to_html()` converts MNML to HTML string for export.

### 3. `browser.py` — The Browser

A feature-rich customtkinter GUI browser that speaks MNET and renders MNML natively.

**Features:**
- Tabbed browsing (`Cmd+T`, `Cmd+W`, `Cmd+1..5`)
- Back / Forward navigation
- Refresh (F5, `Cmd+R`)
- Zoom in/out (`Cmd+Plus`, `Cmd+Minus`)
- Dark / Light theme toggle
- Bookmarks management (★ button)
- Browsing history
- Find on page (`Cmd+F`)
- View source code (`📄` button)
- Save page as `.mn` file (`💾` button)
- Copy URL to clipboard (`📋URL`)
- Fullscreen mode (`⛶`, `Esc`)
- Authentication token input (`🔐`)
- File upload (`⬆ Upload`)
- JSON API tester (`📡 API Helper`)
- Video / Audio rendering with system player option
- Responsive MNML rendering (tables, forms, lists)

**Keyboard Shortcuts:**
| Shortcut       | Action              |
|----------------|---------------------|
| `Cmd+T`        | New tab             |
| `Cmd+W`        | Close tab           |
| `Cmd+R` / `F5` | Refresh             |
| `Cmd+L`        | Focus URL bar       |
| `Cmd+F`        | Find in page        |
| `Cmd+Plus`     | Zoom in             |
| `Cmd+Minus`    | Zoom out            |
| `Cmd+1..5`     | Switch tab          |
| `Esc`          | Exit fullscreen     |

---

## MNML vs HTML — Comparison

### HTML version
```html
<!DOCTYPE html>
<html>
<head><title>My Page</title></head>
<body>
  <h1>Hello World</h1>
  <p>This is a paragraph.</p>
  <ul>
    <li>Item 1</li>
    <li>Item 2</li>
  </ul>
  <a href="/about">About</a>
</body>
</html>
```

### MNML version
```mnml
title: My Page

h1: Hello World

p: This is a paragraph.

ul:
    - Item 1
    - Item 2

link("/about"): About
```

**Lines saved: 18 → 10 (−44%)**

---

## Project Structure

```
mynet/
├── mynet.py            # MNET protocol (server + client)
├── mn.py               # MNML parser + HTML converter
├── browser.py           # customtkinter browser GUI
├── server.py            # Example server with routes
├── run_server.sh        # Server launcher (venv-aware)
├── run_browser.sh       # Browser launcher (venv-aware)
├── .venv/               # Python 3.14 virtual environment
├── certs/               # TLS certificates (auto-generated)
├── public/              # Static files directory (for file serving)
├── MNML_TUTORIAL.md     # Full MNML syntax guide
├── README.md            # ← You're here
└── AGENTS.md            # Agent instructions (this file)
```

---

## API Reference

### Server

```python
import mynet

app = mynet.Server(port=7443, static_dir="public", token="secret")

@app.route("/")
def home(req):
    return "Hello World"

@app.route("/api.json")
def api(req):
    return mynet.json_response({"status": "ok", "data": [1, 2, 3]})

@app.route("/api/echo", methods=["POST"])
def echo(req):
    data = mynet.json_body(req)
    return mynet.json_response({"echo": data})

@app.ws("/ws")
def ws_handler(ws, addr):
    msg = ws.recv()
    ws.send(f"Echo: {msg}")

app.start()
```

### Client

```python
import mynet

# GET
resp = mynet.fetch("localhost", "/", 7443)
print(resp.body.decode())
print(resp.status)
print(resp.headers)

# POST JSON
resp = mynet.post("localhost", "/api/echo", json.dumps({"msg": "hi"}), 7443,
                  headers={"Content-Type": "application/json"})
```

### MNML Parser

```python
import mn

elements = mn.parse(source_text)
html_output = mn.to_html(elements)
```

---

## Setup

### Prerequisites
- macOS / Linux / Windows with Python 3.10+
- Homebrew (macOS) for TLS support

### Install

```bash
cd mynet
python3 -m venv .venv
source .venv/bin/activate
pip install customtkinter
```

### Run

```bash
# Terminal 1 — Server
./run_server.sh

# Terminal 2 — Browser
./run_browser.sh
```

Then open `mynet://localhost:7443/` in the browser.

---

## Why MNET?

| Metric        | HTTPS (HTTP/2 + TLS 1.3) | MNET/1.0         |
|---------------|---------------------------|-------------------|
| Header size   | ~300+ bytes per request   | ~50 bytes         |
| Dependencies  | OpenSSL, http library     | `ssl`, `socket`   |
| Protocol line | `GET / HTTP/1.1\r\n...`   | `MNET/1.0 GET /`  |
| Encryption    | TLS (mandatory)           | TLS (built-in)    |
| Response      | Complex headers + body    | Status + headers + body |
| Lines of code | Thousands                 | ~200 (protocol)   |

**Philosophy:** If it can be smaller, make it smaller. If it can be simpler, make it simpler. If it doesn't need a dependency, remove it.

---

## License

MIT — do whatever you want with it.

---

## Contributing

1. Fork it
2. Commit your changes
3. Send a PR
4. Get merged or get wrecked

---

*Built with zero dependencies and maximum style. No bloat. No fluff. Just net.™*
