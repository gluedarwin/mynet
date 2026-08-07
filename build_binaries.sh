#!/bin/bash
# Build MyNet standalone binaries for cross-platform support
# Works on macOS, Linux x64, and Windows

set -e

echo "=== MyNet Standalone Binary Builder ==="
echo ""

# Check for PyInstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    python3 -m pip install pyinstaller
fi

# Check for PyQt6
if ! python3 -c "import PyQt6" 2>/dev/null; then
    echo "Installing PyQt6..."
    python3 -m pip install PyQt6
fi

echo ""
echo "=== Building mynet protocol server (single-file) ==="
python3 -m PyInstaller \
  --clean \
  --onefile \
  --name mynet \
  --add-data certs:certs \
  --add-data public:public \
  --add-data index.md:. \
  --hidden-import ssl \
  --hidden-import socket \
  --hidden-import threading \
  --hidden-import json \
  --hidden-import argparse \
  --hidden-import datetime \
  mynet.py

chmod +x dist/mynet
echo "✅ Server binary: dist/mynet ($(du -sh dist/mynet | cut -f1))"

echo ""
echo "=== Building mynet browser (GUI) ==="
python3 -m PyInstaller \
  --clean \
  --onefile \
  --name mynet-browser \
  --windowed \
  --hidden-import PyQt6 \
  --collect-all PyQt6 \
  browser.py

echo "✅ Browser binary: dist/mynet-browser/"

echo ""
echo "=== Build Complete ==="
echo ""
echo "Usage:"
echo "  ./dist/mynet                # Start server with index.md"
echo "  ./dist/mynet page.md        # Serve specific markdown file"
echo "  ./dist/mynet --port 8080    # Custom port"
cat << "USAGE"
  ./dist/mynet-browser/mynet-browser  # Start browser GUI
USAGE
echo ""
echo "Server: ./dist/mynet"
echo "Browser: ./dist/mynet-browser/mynet-browser"
echo ""
echo "Note: Browser uses --onedir format for Tkinter compatibility."
echo "      Server uses --onefile for easy distribution."
echo ""
echo "For Linux x64 deployment:"
echo "  1. Copy ./dist/mynet to target machine"
echo "  2. Create index.md in same directory"
echo "  3. Run: ./mynet index.md"
echo "  4. Access: mynet://localhost:7443/"
