#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo "=== SmartEV — Local startup ==="

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.9+ and re-run."
  exit 1
fi

cd "$BACKEND_DIR"

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

echo ""
echo "  SmartEV is starting at http://localhost:8000"
echo "  Landing page : http://localhost:8000/"
echo "  Dashboard    : http://localhost:8000/dashboard"
echo "  API docs     : http://localhost:8000/api/docs"
echo "  Press Ctrl+C to stop."
echo ""

python main.py
