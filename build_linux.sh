#!/bin/bash
# Build MyNet standalone binaries for Linux x64

set -e

echo "=== MyNet Standalone Builder for Linux x64 ==="
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# Check for PyInstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "PyInstaller not found. Installing..."
    pip install pyinstaller
fi

echo ""
echo "=== Building mynet protocol server ==="
python3 -m PyInstaller --clean --onefile \
    --name mynet \
    --add-data certs:certs \
    --add-data public:public \
    --add-data index.md:. \
    mynet.py

echo ""
echo "=== Building mynet browser (GUI) ==="
# For browser, we need PyQt6
pip install PyQt6

python3 -m PyInstaller --clean --onefile \
    --name mynet-browser \
    --windowed \
    --add-data .:. \
    --hidden-import PyQt6 \
    --collect-all PyQt6 \
    browser.py

echo ""
echo "=== Build complete ==="
echo "Server binary: dist/mynet"
echo "Browser binary: dist/mynet-browser"

echo ""
echo "=== Testing mynet index.md functionality ==="
echo "After building, you can:"
echo "1. cd /any/directory"
echo "2. Create an index.md file"
echo "3. Run: ./mynet index.md"
echo "4. Access: mynet://localhost:7443/"
echo "5. Server will serve your index.md file"
echo ""
echo "You can also use environment variables for configuration:"
echo "export MNET_PORT=8080"
echo "export MNET_HOST=0.0.0.0"
echo "export MNET_SECRET_KEY=your-secret-token"
echo "export MNET_RATE_LIMIT_REQUESTS=200"

chmod +x dist/mynet dist/mynet-browser
echo ""
echo "Binaries are ready!"
