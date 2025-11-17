#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /absolute/path/to/launch-command"
  echo "Example: $0 '$PWD/.venv/bin/python -m src.app'"
  exit 1
fi

APP_CMD="$1"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
ICON_SRC="$APP_DIR/image_processor.png"
ICON_TARGET="$ICON_DIR/aa-image-processor.png"

mkdir -p "$DESKTOP_DIR" "$ICON_DIR"

cp "$ICON_SRC" "$ICON_TARGET"
sed \
  -e "s|AA_IMAGE_PROCESSOR_BIN|${APP_CMD}|" \
  -e "s|AA_IMAGE_PROCESSOR_ICON|${ICON_TARGET}|" \
  -e "s|AA_IMAGE_PROCESSOR_APPDIR|${APP_DIR}|" \
  "$APP_DIR/resources/desktop/aa-image-processor.desktop" > "$DESKTOP_DIR/aa-image-processor.desktop"

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
echo "Desktop-Eintrag installiert. Bitte ggf. MIME-Zuweisung im Dateimanager setzen."
