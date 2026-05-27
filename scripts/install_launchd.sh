#!/bin/bash
# Install (or refresh) the launchd agent for daily schedule generation.
set -euo pipefail

PLIST_NAME="com.gregehrenberg.kalshi-daily-schedule"
SRC="$(cd "$(dirname "$0")" && pwd)/${PLIST_NAME}.plist"
DEST="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

# Unload if already loaded
launchctl bootout "gui/$(id -u)/${PLIST_NAME}" 2>/dev/null || true

cp "$SRC" "$DEST"
chmod 644 "$DEST"

launchctl bootstrap "gui/$(id -u)" "$DEST"
echo "Installed ${PLIST_NAME} — runs daily at 7:00 AM local time."
echo "To test now:  launchctl kickstart gui/$(id -u)/${PLIST_NAME}"
