#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG="${1:-}"

if [[ "$#" -ne 1 || ! "${TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Usage: $0 vMAJOR.MINOR.PATCH" >&2
  exit 2
fi

VERSION="${TAG#v}"
ARCH="$(dpkg --print-architecture)"
if [[ "${ARCH}" != "amd64" ]]; then
  echo "amd64 package ကိုသာ build လုပ်နိုင်သည်။ လက်ရှိ architecture: ${ARCH}" >&2
  exit 1
fi

"${ROOT}/build_binary.sh" --no-install

PACKAGE_DIR="$(mktemp -d)"
trap 'rm -rf -- "${PACKAGE_DIR}"' EXIT
mkdir -p \
  "${PACKAGE_DIR}/DEBIAN" \
  "${PACKAGE_DIR}/usr/bin" \
  "${PACKAGE_DIR}/usr/share/applications" \
  "${PACKAGE_DIR}/usr/share/icons/hicolor/48x48/apps" \
  "${PACKAGE_DIR}/usr/share/icons/hicolor/128x128/apps" \
  "${PACKAGE_DIR}/usr/share/icons/hicolor/256x256/apps" \
  "${PACKAGE_DIR}/usr/share/icons/hicolor/512x512/apps"

install -m 755 "${ROOT}/dist/auto_copier" "${PACKAGE_DIR}/usr/bin/auto_copier"
install -m 644 "${ROOT}/assets/icon-48.png" \
  "${PACKAGE_DIR}/usr/share/icons/hicolor/48x48/apps/auto_copier.png"
install -m 644 "${ROOT}/assets/icon-128.png" \
  "${PACKAGE_DIR}/usr/share/icons/hicolor/128x128/apps/auto_copier.png"
install -m 644 "${ROOT}/assets/icon-256.png" \
  "${PACKAGE_DIR}/usr/share/icons/hicolor/256x256/apps/auto_copier.png"
install -m 644 "${ROOT}/assets/icon.png" \
  "${PACKAGE_DIR}/usr/share/icons/hicolor/512x512/apps/auto_copier.png"

cat > "${PACKAGE_DIR}/usr/share/applications/auto-copier.desktop" <<'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Auto Copier
GenericName=Password Archive Copier
Comment=Create an encrypted 7z archive and copy it
Exec=/usr/bin/auto_copier
Icon=auto_copier
Terminal=false
Categories=Utility;Archiving;
StartupNotify=true
StartupWMClass=autocopier
EOF

cat > "${PACKAGE_DIR}/DEBIAN/control" <<EOF
Package: auto-copier
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: ROM Robotics
Depends: p7zip-full | 7zip
Description: Encrypted 7z archive and copy utility
 Desktop application for creating password-protected archives and copying them.
EOF

chmod 644 \
  "${PACKAGE_DIR}/DEBIAN/control" \
  "${PACKAGE_DIR}/usr/share/applications/auto-copier.desktop"
find "${PACKAGE_DIR}" -type d -exec chmod 755 {} +
OUTPUT="${ROOT}/dist/auto-copier_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "${PACKAGE_DIR}" "${OUTPUT}"
echo "Built: ${OUTPUT}"
