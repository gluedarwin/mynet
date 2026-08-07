# MyNet Server

Welcome to MyNet!

This is a standalone mynet:// server with all the essential features you need.

## Features

* **TLS-encrypted** connections
* **Markdown** file serving
* **Rate limiting** to prevent abuse
* **Security headers** for enhanced protection
* **Authentication** support (optional)
* **Metrics endpoint** for monitoring

## Quick Start

1. Start the server: `./run_server.sh`
2. Access the site: `mynet://localhost:7443/`

## Usage

* Open `mynet://localhost:7443/` in the browser
* View API at `mynet://localhost:7443/api/data`
* Check server metrics at `mynet://localhost:7443/api/metrics`

## Getting Started

Run the server:
```bash
./run_server.sh
```

Or use the standalone binary:
```bash
./mynet
```

Visit: `mynet://localhost:7443/`
