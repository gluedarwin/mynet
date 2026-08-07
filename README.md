# MyNet: Lightweight Secure Protocol with Markdown Support

## Overview

MyNet is a fully independent, lightweight, secure, and lean HTTPS replacement. **Zero dependencies** beyond the Python standard library.

The mynet:// protocol supports:

* **MNET/1.0** - A minimal text-based protocol over TLS
* **Markdown** - Modern, simple markup language (replacing MNML)
* **Customtkinter GUI** - Feature-rich browser (packaged as standalone)
* **All modern web features** - TLS, compression, caching, auth, WS, etc.

## Architecture

```
┌─────────────┐     MNET/1.0 + TLS     ┌─────────────────┐
│  Browser    │ ◄────────────────────► │  MyNet Server   │
│  (GUI)      │     mynet://host:port/  │  (mynet.py)     │
│             │                          │  Routes, Cache  │
│             │                          │  Auth, WS, etc. │
└─────────────┘                          └─────────────────┘
          │                                      │
          ▼                                      ▼
     ┌──────────┐                          ┌────────────┐
     │ Markdown │  Python-like syntax      │ Static     │
     │ Parser   │  → renders to widgets    │ File Server │
     │          │                          │ (range req) │
     └──────────┘                          └────────────┘
```

## What's Inside

### 1. `mynet.py` - The Protocol Engine

The core MNET/1.0 implementation with all features:

* **Protocol**: MNET/1.0 over TLS
* **Security**: SSL/TLS encryption, optional auth, rate limiting
* **Performance**: Automatic gzip compression, LRU cache
* **Features**: WebSocket, file upload, range requests, JSON API
* **Size**: ~26KB (including all features)

### 2. `mynet_main.py` - Command Line Interface

Standalone executable entry point with:

* **Server controls**: Start/stop, configuration
* **Certificate management**: Self-signed certs
* **File serving**: Direct .md file serving
* **Environment config**: Tokens, rate limits, ports

### 3. `browser.py` - GUI Browser

Feature-rich browser (packaged as standalone):

* **Tabbed browsing** (`Cmd+T`, `Cmd+W`, `Cmd+1..5`)
* **Navigation**: Back/forward/refresh
* **Security**: Auth token, bookmarks, history
* **Development**: Source viewer, API tester
* **Multimedia**: Video/audio playback with system players

### 4. `server.py` - Example Server

Demonstrates all MNET features:

* **Routes**: REST API endpoints
* **Static files**: Public directory serving
* **WebSocket**: Real-time communication
* **Authentication**: Token-based auth

## Usage

### Quick Start (Pre-packaged binaries)

```bash
# 1. Start the server (or use the standalone binary)
./run_server.sh

# 2. Use the browser (or use the standalone binary)
./run_browser.sh

# 3. Navigate to the site
mynet://localhost:7443/
```

### With Standalone Binaries

```bash
# Start server using packaged binary
./mynet

# Start browser using packaged binary  
./mynet-browser

# Navigate to the site
mynet://localhost:7443/
```

### Server Configuration

Environment variables for server customization:

```bash
# Authentication
export MNET_SECRET_KEY="your-token-here"

# Rate limiting
export MNET_RATE_LIMIT_REQUESTS=200
export MNET_RATE_LIMIT_WINDOW=1800

# Server settings
export MNET_HOST=0.0.0.0
export MNET_PORT=7443

# Request size limit
export MNET_MAX_REQUEST_SIZE=2097152
```

### API Examples

```python
import mynet

# Create server with auth
app = mynet.Server(port=7443, token="secret123")

# JSON API endpoint
@app.route("/api/data")
def api_data(req):
    return mynet.json_response({
        "status": "ok",
        "protocol": "MNET/1.0",
        "features": ["cache", "gzip", "range", "ws", "upload", "auth"]
    })

# WebSocket endpoint
@app.ws("/ws")
def ws_handler(ws, addr):
    msg = ws.recv()
    ws.send(f"Echo: {msg}")
```

### Client Examples

```python
import mynet

# GET request
resp = mynet.fetch("localhost", "/", 7443)
print(resp.body.decode())

# POST JSON data
resp = mynet.post(
    "localhost", "/api/echo", 
    '{"msg": "hello"}', 7443,
    headers={"Content-Type": "application/json"}
)
print(resp.body.decode())
```

## Packaging

MyNet is packaged using **PyInstaller** for:

* **Portability**: Works on macOS, Linux, Windows
* **Single file**: Console binary for the protocol
* **GUI binary**: Standalone browser without Python dependencies
* **Zero installation**: No external libraries required

## Markdown Support

MyNet uses **Markdown** (not MNML) for:

* **Syntax simplicity**: Modern, readable format
* **Ecosystem**: Compatible with GitHub, StackExchange, etc.
* **Tools**: Rich editor support everywhere

### Markdown Examples

```markdown
# Title

## Subtitle

This is a paragraph with **bold** and *italic* text.

### Lists

- Item 1
- Item 2
- Item 3

1. First item
2. Second item
3. Third item

### Links and Images

[Google](https://google.com)

![Logo](/path/to/logo.png)

### Code

`inline code`

```
multiline code
```

### Tables

| Name | Age | City |
|------|-----|------|
| Alice | 25 | New York |
| Bob | 30 | London |
```

## Features Comparison

| Feature | MNET/1.0 | HTTPS |
|---------|----------|-------|
| Header size | ~50 bytes | ~300+ bytes |
| Dependencies | Python stdlib only | OpenSSL, http library |
| Protocol | MNET/1.0 GET /\r\n... | HTTP/1.1 GET / HTTP/1.1\r\n... |
| Encryption | TLS (built-in) | TLS |
| Response | Status + headers + body | Complex headers + body |
| Lines of code | ~200 (protocol) | Thousands |

## Performance

* **Faster headers**: 6x smaller HTTP requests
* **Simpler stack**: No complex HTTP/2 negotiation
* **Lower memory**: Fewer dependencies
* **Quick setup**: Self-signed certs, no config files

## Installation

### From Source

```bash
cd mynet
python3 -m venv .venv
source .venv/bin/activate
pip install customtkinter
```

### Using Packaged Binaries

Download the latest release from GitHub and run:

```bash
# On Linux/macOS
chmod +x mynet
./mynet

chmod +x mynet-browser  
./mynet-browser
```

## License

MIT — do whatever you want with it.

## Contributing

1. Fork it
2. Commit your changes
3. Send a PR
4. Get merged or get wrecked

*Built with zero dependencies and maximum style. No bloat. No fluff. Just net.™*
