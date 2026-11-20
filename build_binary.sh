#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

INSTALL_AFTER_BUILD=1
if [[ "${1:-}" == "--no-install" && "$#" -eq 1 ]]; then
  INSTALL_AFTER_BUILD=0
elif [[ "$#" -ne 0 ]]; then
  echo "Usage: $0 [--no-install]" >&2
  exit 2
fi

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
if [[ "${INSTALL_AFTER_BUILD}" -eq 1 ]]; then
  "${ROOT}/install_auto_copier"
fi
