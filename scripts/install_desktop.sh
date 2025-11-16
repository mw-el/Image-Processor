#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /absolute/path/to/launch-command"
  echo "Example: $0 '$PWD/.venv/bin/python -m src.app'"
  exit 1
fi

APP_CMD="$1"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"

mkdir -p "$DESKTOP_DIR" "$ICON_DIR"

cp assets/icons/app_icon.svg "$ICON_DIR/aa-image-processor.svg"
sed "s|AA_IMAGE_PROCESSOR_BIN|${APP_CMD}|" resources/desktop/aa-image-processor.desktop > "$DESKTOP_DIR/aa-image-processor.desktop"

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
echo "Desktop-Eintrag installiert. Bitte ggf. MIME-Zuweisung im Dateimanager setzen."
