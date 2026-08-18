#!/usr/bin/env bash
set -e

LUNE_VERSION="0.10.4"

curl -L \
  "https://github.com/lune-org/lune/releases/download/v${LUNE_VERSION}/lune-${LUNE_VERSION}-linux-x86_64.zip" \
  -o /tmp/lune.zip

mkdir -p /tmp/lune

python - <<'PY'
import zipfile

with zipfile.ZipFile("/tmp/lune.zip") as z:
    z.extractall("/tmp/lune")
PY

find /tmp/lune -type f -name lune -exec chmod +x {} \;
find /tmp/lune -type f -name lune -exec cp {} /usr/local/bin/lune \;

lune --version