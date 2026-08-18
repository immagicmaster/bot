#!/usr/bin/env bash
set -e

LUNE_VERSION="0.10.4"

ROOT="$(pwd)"
LUNE_DIR="$ROOT/.lune"
BIN_DIR="$LUNE_DIR/bin"

mkdir -p "$BIN_DIR"

curl -L \
  "https://github.com/lune-org/lune/releases/download/v${LUNE_VERSION}/lune-${LUNE_VERSION}-linux-x86_64.zip" \
  -o "$LUNE_DIR/lune.zip"

python - <<'PY'
import zipfile
from pathlib import Path

zip_path = Path(".lune/lune.zip")
out_dir = Path(".lune/bin")

with zipfile.ZipFile(zip_path) as z:
    z.extractall(out_dir)
PY

LUNE_PATH="$(find "$BIN_DIR" -type f -name lune | head -n 1)"

if [ -z "$LUNE_PATH" ]; then
    echo "Lune executable not found"
    find "$LUNE_DIR" -type f
    exit 1
fi

chmod +x "$LUNE_PATH"

echo "Lune installed at:"
echo "$LUNE_PATH"

"$LUNE_PATH" --version