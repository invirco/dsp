#!/usr/bin/env bash
# Sync shared reference files from mx-app (source of truth) into this repo.
# Run manually when mx-app config files have changed.

set -e

APP_CONFIG="/home/peter/mx/_0/app-avalonia/config"
SHARED="$(dirname "$0")/shared"

echo "Syncing shared files from mx-app..."

cp "$APP_CONFIG/mx_master.csv" "$SHARED/mx_master.csv" && echo "  updated: mx_master.csv"

echo "Sync complete. Review changes with: git diff shared/"
