#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Aria Bridge Installer - macOS"
echo "This will set up Python and all required dependencies."
echo ""

# Find Python 3.11
PYTHON=""
for cmd in python3.11 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" --version 2>&1)
        if [[ "$VER" == *"3.11"* ]]; then
            PYTHON=$(command -v "$cmd")
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.11 not found."
    echo "Install it from https://www.python.org/downloads/ or with:"
    echo "  brew install python@3.11"
    exit 1
fi

echo "Using Python: $PYTHON ($("$PYTHON" --version))"
echo ""

"$PYTHON" -m venv "$ROOT/venv"
echo "Virtual environment created."
echo ""

"$ROOT/venv/bin/pip" install --upgrade pip --quiet

# Apple Silicon gets MLX support automatically via requirements.txt
"$ROOT/venv/bin/pip" install torch --quiet
"$ROOT/venv/bin/pip" install -r "$ROOT/backend/requirements.txt" --quiet

echo "All dependencies installed."
echo ""
echo "Installation complete!"
echo "Next steps:"
echo "  1. Download model-gen.safetensors from https://huggingface.co/eleutherai/aria"
echo "  2. Place it in the models/ folder"
echo "  3. Launch Aria Bridge.app"
