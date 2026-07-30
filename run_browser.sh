#!/bin/bash
# Run the MyNet browser using the correct Python
cd "$(dirname "$0")"
source .venv/bin/activate
exec python browser.py "$@"
