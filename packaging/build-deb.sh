#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$ROOT_DIR/pyproject.toml" | head -n 1)"
ARCH="$(dpkg --print-architecture)"
BUILD_DIR="$ROOT_DIR/build/deb/presidentielle2027_${VERSION}_${ARCH}"
OUTPUT_DIR="$ROOT_DIR/dist"
APP_DIR="$BUILD_DIR/opt/presidentielle2027"

if [[ ! -x "$ROOT_DIR/.venv/bin/python3.10" ]]; then
    echo "Erreur: .venv Python 3.10 est requis pour créer le paquet hors-ligne." >&2
    exit 1
fi

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/DEBIAN" "$APP_DIR/src" "$APP_DIR/share" "$APP_DIR/venv/lib/python3.10"
mkdir -p "$BUILD_DIR/usr/bin" "$BUILD_DIR/usr/share/applications" "$BUILD_DIR/usr/share/icons/hicolor/scalable/apps" "$OUTPUT_DIR"

cp -a "$ROOT_DIR/src/presidentielle2027" "$APP_DIR/src/"
cp -a "$ROOT_DIR/data" "$APP_DIR/share/"
cp -a "$ROOT_DIR/scripts" "$APP_DIR/share/"
cp -a "$ROOT_DIR/make_wiki_datasets.py" "$APP_DIR/share/"
cp -a "$ROOT_DIR"/sondages_*_wikipedia_tables.csv "$APP_DIR/share/"

# L'environnement complet garantit une installation sans accès à PyPI. Les outils
# strictement réservés au développement et aux notebooks ne sont pas nécessaires.
cp -a "$ROOT_DIR/.venv/lib/python3.10/site-packages" "$APP_DIR/venv/lib/python3.10/"
mkdir -p "$APP_DIR/venv/bin"
ln -s /usr/bin/python3.10 "$APP_DIR/venv/bin/python"
ln -s python "$APP_DIR/venv/bin/python3"
ln -s python "$APP_DIR/venv/bin/python3.10"
cat > "$APP_DIR/venv/pyvenv.cfg" <<EOF
home = /usr/bin
include-system-site-packages = false
version = 3.10.12
EOF

install -m 0755 "$ROOT_DIR/packaging/presidentielle2027" "$BUILD_DIR/usr/bin/presidentielle2027"
install -m 0755 "$ROOT_DIR/packaging/presidentielle2027-dashboard" "$BUILD_DIR/usr/bin/presidentielle2027-dashboard"
install -m 0644 "$ROOT_DIR/packaging/presidentielle2027.desktop" "$BUILD_DIR/usr/share/applications/presidentielle2027.desktop"
install -m 0644 "$ROOT_DIR/src/presidentielle2027/dashboard/assets/favicon-neutral.svg" "$BUILD_DIR/usr/share/icons/hicolor/scalable/apps/presidentielle2027.svg"

INSTALLED_SIZE="$(du -sk "$BUILD_DIR" | cut -f1)"
cat > "$BUILD_DIR/DEBIAN/control" <<EOF
Package: presidentielle2027
Version: $VERSION
Section: science
Priority: optional
Architecture: $ARCH
Depends: python3.10, ca-certificates
Installed-Size: $INSTALLED_SIZE
Maintainer: Guillaume Boileau
Description: Tableau de bord des sondages de la présidentielle 2027
 Outil de collecte, normalisation, analyse et visualisation de sondages publics
 liés à l'élection présidentielle française de 2027.
EOF

find "$BUILD_DIR" -type d -exec chmod 0755 {} +
dpkg-deb --root-owner-group -Zxz --build "$BUILD_DIR" "$OUTPUT_DIR/presidentielle2027_${VERSION}_${ARCH}.deb"
echo "$OUTPUT_DIR/presidentielle2027_${VERSION}_${ARCH}.deb"
