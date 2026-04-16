#!/bin/bash
# Script lives at: Aria Bridge.app/Contents/MacOS/start.sh
# Package root is 3 levels up from there.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

PYTHON="$ROOT/venv/bin/python"
BACKEND="$ROOT/backend"
MODEL="$ROOT/models/model-gen.safetensors"
if [ ! -f "$PYTHON" ]; then
    osascript -e 'display dialog "Virtual environment not found.\nPlease run install.sh first." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

if [ ! -f "$MODEL" ]; then
    osascript -e 'display dialog "Model file not found.\nPlease download model-gen.safetensors from HuggingFace (eleutherai/aria) and place it in the models/ folder." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

cd "$BACKEND"
"$PYTHON" ableton_bridge.py \
  plugin \
  --feedback \
  --checkpoint "$MODEL"
