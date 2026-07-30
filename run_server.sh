#!/bin/bash
# Run the MyNet server using the correct Python
cd "$(dirname "$0")"
source .venv/bin/activate
exec python server.py "$@"
