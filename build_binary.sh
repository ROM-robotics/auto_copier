#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

.venv/bin/pip install --upgrade pip
.venv/bin/pip install "pyinstaller>=6.0"

.venv/bin/pyinstaller \
  --noconfirm \
  --clean \
  --onefile \
  --windowed \
  --name auto_copier \
  --add-data "assets:assets" \
  auto_copier.py

echo "Built: ${ROOT}/dist/auto_copier"
"${ROOT}/install_auto_copier"
